from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


HERE = Path(__file__).resolve().parent
TCAD_ROOT = HERE.parents[3]
DATA_EXTRACTION_ROOT = TCAD_ROOT / "data_extraction"
BASE_CASE_DIR = DATA_EXTRACTION_ROOT / "base_case"
SCRIPTS_DIR = DATA_EXTRACTION_ROOT / "scripts"
DEFAULT_OUTPUT_DIR = HERE / "generated"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from env_config import build_runtime_env, resolve_gmsh_exe, resolve_python_exe


STRUCTURE_ID = "L300T20"
GATE_WIDTH_CM = "3.0e-5"
OXIDE_THICKNESS_CM = "2.0e-6"
BULK_DOPING = "1.0e16"
SOURCE_DOPING = "1.0e20"
DRAIN_DOPING = "1.0e20"


@dataclass(frozen=True)
class Case:
    key: str
    label: str
    run_id: str
    ldd_doping: str


CASES = (
    Case("ldd0", "Without LDD", "B1e16SD1e20LDD0", "0.0"),
    Case("ldd1e18", "With LDD", "B1e16SD1e20LDD1e18", "1.0e18"),
)


def _replace_assignment(text: str, name: str, value: str) -> str:
    pattern = re.compile(
        rf"^(\s*{re.escape(name)}\s*=\s*)([^;\n#]+)(\s*;?\s*)$",
        re.MULTILINE,
    )
    replaced, count = pattern.subn(rf"\g<1>{value}\g<3>", text, count=1)
    if count != 1:
        raise ValueError(f"Could not patch parameter '{name}'")
    return replaced


def _patched_geometry() -> str:
    text = (BASE_CASE_DIR / "gmsh_mos2d.geo").read_text(encoding="utf-8")
    text = _replace_assignment(text, "gate_width", GATE_WIDTH_CM)
    text = _replace_assignment(text, "oxide_thickness", OXIDE_THICKNESS_CM)
    return text


def _patched_device(case: Case) -> str:
    text = (BASE_CASE_DIR / "gmsh_mos2d_create.py").read_text(encoding="utf-8")
    replacements = {
        "gate_width": GATE_WIDTH_CM,
        "oxide_thickness": OXIDE_THICKNESS_CM,
        "bulk_doping": BULK_DOPING,
        "source_doping": SOURCE_DOPING,
        "drain_doping": DRAIN_DOPING,
        "LDD_doping": case.ldd_doping,
    }
    for name, value in replacements.items():
        text = _replace_assignment(text, name, value)
    return text


def _patched_runtime_setup() -> str:
    text = (BASE_CASE_DIR / "runtime_setup.py").read_text(encoding="utf-8")
    marker = "    return this_file.parent"
    if marker not in text:
        raise ValueError("Could not patch runtime_setup.py")
    config_path = repr(str(DATA_EXTRACTION_ROOT / "config"))
    insertion = (
        f"    chapter_config_dir = Path({config_path})\n"
        "    chapter_config_str = str(chapter_config_dir)\n"
        "    if chapter_config_str in sys.path:\n"
        "        sys.path.remove(chapter_config_str)\n"
        "    sys.path.insert(0, chapter_config_str)\n\n"
        f"{marker}"
    )
    return text.replace(marker, insertion, 1)


def _run_command(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    log_prefix: Path,
) -> subprocess.CompletedProcess[str]:
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed = time.perf_counter() - started
    log_prefix.parent.mkdir(parents=True, exist_ok=True)
    log_prefix.with_suffix(".stdout.log").write_text(
        completed.stdout, encoding="utf-8", errors="replace"
    )
    log_prefix.with_suffix(".stderr.log").write_text(
        completed.stderr, encoding="utf-8", errors="replace"
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed ({completed.returncode}) after {elapsed:.1f} s:\n"
            f"{' '.join(command)}\n"
            f"See {log_prefix.with_suffix('.stderr.log')}"
        )
    return completed


def _ensure_mesh(
    output_dir: Path,
    *,
    gmsh_exe: str | None,
    python_exe: str,
    env: dict[str, str],
    force: bool,
) -> Path:
    mesh_dir = output_dir / "mesh" / STRUCTURE_ID
    geo_path = mesh_dir / "gmsh_mos2d.geo"
    msh_path = mesh_dir / "gmsh_mos2d.msh"
    if msh_path.exists() and not force:
        return msh_path

    mesh_dir.mkdir(parents=True, exist_ok=True)
    geo_path.write_text(_patched_geometry(), encoding="utf-8")
    cli_error: Exception | None = None
    if gmsh_exe:
        try:
            _run_command(
                [gmsh_exe, str(geo_path), "-2", "-format", "msh2", "-o", str(msh_path)],
                cwd=mesh_dir,
                env=env,
                log_prefix=output_dir / "logs" / "gmsh_cli",
            )
        except RuntimeError as exc:
            cli_error = exc

    if not msh_path.exists() or msh_path.stat().st_size == 0:
        try:
            _run_command(
                [
                    python_exe,
                    str(HERE / "generate_mesh.py"),
                    str(geo_path),
                    str(msh_path),
                ],
                cwd=mesh_dir,
                env=env,
                log_prefix=output_dir / "logs" / "gmsh_python",
            )
        except RuntimeError as api_error:
            cli_message = f"\nGmsh CLI failure:\n{cli_error}" if cli_error else ""
            raise RuntimeError(
                f"Both Gmsh mesh-generation methods failed.{cli_message}\n"
                f"Python Gmsh API failure:\n{api_error}"
            ) from api_error
    if not msh_path.exists() or msh_path.stat().st_size == 0:
        raise RuntimeError(f"Gmsh did not create a usable mesh: {msh_path}")
    return msh_path


def _prepare_work_dir(case: Case, mesh_path: Path, output_dir: Path) -> Path:
    work_dir = output_dir / "runs" / case.key
    work_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BASE_CASE_DIR / "gmsh_mos2d.py", work_dir / "gmsh_mos2d.py")
    (work_dir / "runtime_setup.py").write_text(
        _patched_runtime_setup(), encoding="utf-8"
    )
    shutil.copy2(mesh_path, work_dir / "gmsh_mos2d.msh")
    (work_dir / "gmsh_mos2d.geo").write_text(_patched_geometry(), encoding="utf-8")
    (work_dir / "gmsh_mos2d_create.py").write_text(
        _patched_device(case), encoding="utf-8"
    )
    return work_dir


def parse_ivpoints(text: str) -> dict[str, list[tuple[float, float, float]]]:
    points: dict[str, list[tuple[float, float, float]]] = {}
    for raw_line in text.splitlines():
        parts = raw_line.strip().split()
        if len(parts) < 5 or parts[0] != "IVPOINT":
            continue
        try:
            point = (float(parts[2]), float(parts[3]), float(parts[4]))
        except ValueError:
            continue
        points.setdefault(parts[1], []).append(point)
    return points


def _write_curve_csv(
    path: Path,
    case: Case,
    points: dict[str, list[tuple[float, float, float]]],
    prefix: str,
) -> int:
    rows: list[dict[str, str]] = []
    for tag, values in points.items():
        if not tag.startswith(prefix):
            continue
        sort_index = 1 if prefix == "IDVD" else 0
        for gate_v, drain_v, drain_i in sorted(values, key=lambda item: item[sort_index]):
            rows.append(
                {
                    "structure_id": STRUCTURE_ID,
                    "doping_run_id": case.run_id,
                    "case": case.key,
                    "curve_tag": tag,
                    "gate_v": f"{gate_v:.12e}",
                    "drain_v": f"{drain_v:.12e}",
                    "drain_current_a_per_cm": f"{drain_i:.12e}",
                }
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "structure_id",
                "doping_run_id",
                "case",
                "curve_tag",
                "gate_v",
                "drain_v",
                "drain_current_a_per_cm",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def _result_paths(case: Case, output_dir: Path) -> tuple[Path, Path, Path]:
    stem = f"{STRUCTURE_ID}{case.run_id}"
    dataset_dir = output_dir / "dataset"
    return (
        dataset_dir / f"{stem}_IdVd.csv",
        dataset_dir / f"{stem}_IdVg.csv",
        dataset_dir / "final_fields" / f"{stem}_Vg3p0_Vd3p0.dat",
    )


def _case_complete(case: Case, output_dir: Path) -> bool:
    return all(path.exists() and path.stat().st_size > 0 for path in _result_paths(case, output_dir))


def _run_case(
    case: Case,
    *,
    mesh_path: Path,
    output_dir: Path,
    python_exe: str,
    env: dict[str, str],
    force: bool,
) -> dict[str, object]:
    idvd_path, idvg_path, field_path = _result_paths(case, output_dir)
    if _case_complete(case, output_dir) and not force:
        return {"case": case.key, "status": "skipped", "reason": "outputs exist"}

    work_dir = _prepare_work_dir(case, mesh_path, output_dir)
    started = time.perf_counter()
    completed = _run_command(
        [python_exe, "gmsh_mos2d.py"],
        cwd=work_dir,
        env=env,
        log_prefix=output_dir / "logs" / case.key,
    )
    points = parse_ivpoints(completed.stdout)
    idvd_count = _write_curve_csv(idvd_path, case, points, "IDVD")
    idvg_count = _write_curve_csv(idvg_path, case, points, "IDVG")

    source_field = work_dir / "gmsh_mos2d_dd.dat"
    if not source_field.exists():
        raise RuntimeError(f"DEVSIM completed but field dump is missing: {source_field}")
    field_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_field, field_path)

    return {
        "case": case.key,
        "label": case.label,
        "status": "ok",
        "ldd_doping_cm-3": case.ldd_doping,
        "idvd_points": idvd_count,
        "idvg_points": idvg_count,
        "elapsed_s": round(time.perf_counter() - started, 3),
        "idvd_csv": str(idvd_path),
        "idvg_csv": str(idvg_path),
        "field_dat": str(field_path),
    }


def run_comparison(
    *,
    selected_case: str = "all",
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    python_exe: str | None = None,
    gmsh_exe: str | None = None,
    force: bool = False,
) -> list[dict[str, object]]:
    output_dir = output_dir.resolve()
    resolved_python = resolve_python_exe(python_exe)
    resolved_gmsh = resolve_gmsh_exe(gmsh_exe)
    env = build_runtime_env(resolved_gmsh or None)
    mesh_path = _ensure_mesh(
        output_dir,
        gmsh_exe=resolved_gmsh or None,
        python_exe=resolved_python,
        env=env,
        force=force,
    )
    selected = CASES if selected_case == "all" else tuple(
        case for case in CASES if case.key == selected_case
    )
    results = [
        _run_case(
            case,
            mesh_path=mesh_path,
            output_dir=output_dir,
            python_exe=resolved_python,
            env=env,
            force=force,
        )
        for case in selected
    ]
    summary_path = output_dir / "comparison_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(
            {
                "structure": {
                    "gate_length_nm": 300,
                    "oxide_thickness_nm": 20,
                    "bulk_doping_cm-3": 1e16,
                    "source_drain_doping_cm-3": 1e20,
                },
                "results": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return results


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Chapter 4 LDD=0 versus LDD=1e18 DEVSIM comparison."
    )
    parser.add_argument(
        "--case", choices=("all", *(case.key for case in CASES)), default="all"
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--python-exe")
    parser.add_argument("--gmsh-exe")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        results = run_comparison(
            selected_case=args.case,
            output_dir=args.output_dir,
            python_exe=args.python_exe,
            gmsh_exe=args.gmsh_exe,
            force=args.force,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for result in results:
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
