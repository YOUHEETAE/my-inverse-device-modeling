from __future__ import annotations

import argparse
import csv
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from env_config import build_runtime_env, resolve_python_exe  # type: ignore[import-not-found]


@dataclass
class DopingRow:
    run_id: str
    bulk_doping: str
    source_doping: str
    drain_doping: str


@dataclass
class GeometryRow:
    run_id: str
    gate_width: str
    oxide_thickness: str


def _resolve_defaults(script_file: Path) -> tuple[Path, Path, Path, Path, Path, str, Path]:
    root = script_file.resolve().parents[1]
    runs_dir = root / "runs"
    base_dir = root / "base_case"
    geometry_config = root / "config" / "test_geometry.csv"
    doping_config = root / "config" / "test_doping.csv"
    status_csv = root / "dataset" / "run_status.csv"
    structure_glob = "L*"
    work_root = root / "runs" / "_tmp_work"
    return runs_dir, base_dir, geometry_config, doping_config, status_csv, structure_glob, work_root


def _parse_args() -> argparse.Namespace:
    (
        runs_dir,
        base_dir,
        geometry_config,
        doping_config,
        status_csv,
        structure_glob,
        work_root,
    ) = _resolve_defaults(Path(__file__))

    parser = argparse.ArgumentParser(
        description=(
            "Execute DEVSIM runs using structures under runs/ and doping rows "
            "from a config CSV."
        )
    )
    parser.add_argument("--runs-dir", type=Path, default=runs_dir)
    parser.add_argument("--base-dir", type=Path, default=base_dir)
    parser.add_argument("--geometry-config", type=Path, default=geometry_config)
    parser.add_argument("--doping-config", type=Path, default=doping_config)
    parser.add_argument(
        "--curves-dir",
        type=Path,
        default=doping_config.parents[1] / "dataset",
    )
    parser.add_argument(
        "--final-fields-dir",
        type=Path,
        default=doping_config.parents[1] / "dataset" / "final_fields",
        help="Directory for final DEVSIM field dumps such as *_final.dat",
    )
    parser.add_argument("--python-exe", type=str, default=resolve_python_exe())
    parser.add_argument("--structure-glob", type=str, default=structure_glob)
    parser.add_argument("--work-root", type=Path, default=work_root)
    parser.add_argument("--status-csv", type=Path, default=status_csv)
    parser.add_argument(
        "--keep-work",
        action="store_true",
        help="Keep per-run work directories and artifacts under work-root",
    )
    parser.add_argument(
        "--continue-on-error",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Continue remaining runs even if one run fails (default: true)",
    )
    return parser.parse_args()


def _list_structures(runs_dir: Path, pattern: str) -> list[Path]:
    out: list[Path] = []
    for p in sorted(runs_dir.glob(pattern)):
        if not p.is_dir():
            continue
        if (p / "gmsh_mos2d.geo").exists() and (p / "gmsh_mos2d.msh").exists():
            out.append(p)
    if not out:
        raise FileNotFoundError(
            f"No structure folders found in {runs_dir} with pattern '{pattern}'"
        )
    return out


def _load_doping_rows(config_csv: Path) -> list[DopingRow]:
    rows: list[DopingRow] = []
    with config_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"run_id", "bulk_doping", "source_doping", "drain_doping"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError(
                f"Doping config format invalid: {config_csv}. "
                "Required columns: run_id, bulk_doping, source_doping, drain_doping"
            )

        for line_no, row in enumerate(reader, start=2):
            run_id = (row.get("run_id") or "").strip()
            bulk = (row.get("bulk_doping") or "").strip()
            source = (row.get("source_doping") or "").strip()
            drain = (row.get("drain_doping") or "").strip()
            if not run_id or not bulk or not source or not drain:
                raise ValueError(
                    f"Missing value at {config_csv}:{line_no} "
                    "(run_id, bulk_doping, source_doping, drain_doping)"
                )
            rows.append(
                DopingRow(
                    run_id=run_id,
                    bulk_doping=bulk,
                    source_doping=source,
                    drain_doping=drain,
                )
            )

    if not rows:
        raise ValueError(f"No rows found in doping config: {config_csv}")
    return rows


def _load_geometry_rows(config_csv: Path) -> dict[str, GeometryRow]:
    rows: dict[str, GeometryRow] = {}
    with config_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"run_id", "gate_width", "oxide_thickness"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError(
                f"Geometry config format invalid: {config_csv}. "
                "Required columns: run_id, gate_width, oxide_thickness"
            )

        for line_no, row in enumerate(reader, start=2):
            run_id = (row.get("run_id") or "").strip()
            gate_width = (row.get("gate_width") or "").strip()
            oxide_thickness = (row.get("oxide_thickness") or "").strip()
            if not run_id or not gate_width or not oxide_thickness:
                raise ValueError(
                    f"Missing value at {config_csv}:{line_no} "
                    "(run_id, gate_width, oxide_thickness)"
                )
            rows[run_id] = GeometryRow(
                run_id=run_id,
                gate_width=gate_width,
                oxide_thickness=oxide_thickness,
            )

    if not rows:
        raise ValueError(f"No rows found in geometry config: {config_csv}")
    return rows


def _replace_param(text: str, name: str, value: str) -> str:
    pattern = re.compile(rf"^(\s*{re.escape(name)}\s*=\s*)([^#\n]+)$", re.MULTILINE)
    replaced, count = pattern.subn(rf"\g<1>{value}", text, count=1)
    if count != 1:
        raise ValueError(f"Failed to replace parameter: {name}")
    return replaced


def _patch_doping(create_file: Path, row: DopingRow) -> None:
    text = create_file.read_text(encoding="utf-8")
    text = _replace_param(text, "bulk_doping", row.bulk_doping)
    text = _replace_param(text, "source_doping", row.source_doping)
    text = _replace_param(text, "drain_doping", row.drain_doping)
    create_file.write_text(text, encoding="utf-8")


def _patch_geometry(create_file: Path, row: GeometryRow) -> None:
    text = create_file.read_text(encoding="utf-8")
    text = _replace_param(text, "gate_width", row.gate_width)
    text = _replace_param(text, "oxide_thickness", row.oxide_thickness)
    create_file.write_text(text, encoding="utf-8")


def _copy_base_files(base_dir: Path, work_dir: Path) -> None:
    for name in ("gmsh_mos2d.py", "gmsh_mos2d_create.py", "runtime_setup.py"):
        src = base_dir / name
        if not src.exists():
            raise FileNotFoundError(f"Base file not found: {src}")
        shutil.copy2(src, work_dir / name)


def _copy_structure_files(structure_dir: Path, work_dir: Path) -> None:
    for name in ("gmsh_mos2d.geo", "gmsh_mos2d.msh"):
        src = structure_dir / name
        if not src.exists():
            raise FileNotFoundError(f"Structure file not found: {src}")
        shutil.copy2(src, work_dir / name)


def _extract_ivpoint_count(stdout_text: str) -> int:
    return sum(1 for line in stdout_text.splitlines() if line.startswith("IVPOINT"))


def _parse_ivpoints(stdout_text: str) -> dict[str, list[tuple[float, float, float]]]:
    points: dict[str, list[tuple[float, float, float]]] = {}
    for raw in stdout_text.splitlines():
        line = raw.strip()
        if not line.startswith("IVPOINT"):
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        tag = parts[1]
        try:
            gate_v = float(parts[2])
            drain_v = float(parts[3])
            drain_i = float(parts[4])
        except ValueError:
            continue
        points.setdefault(tag, []).append((gate_v, drain_v, drain_i))
    return points


def _write_curve_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_status_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "structure_id",
                "doping_run_id",
                "gate_width",
                "oxide_thickness",
                "bulk_doping",
                "source_doping",
                "drain_doping",
                "status",
                "return_code",
                "elapsed_sec",
                "ivpoint_count",
                "idvd_csv",
                "idvg_csv",
                "idvd_points",
                "idvg_points",
                "stdout_log",
                "stderr_log",
                "work_dir",
                "final_dat",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _format_doping_label(value: str) -> str:
    token = value.strip().lower().replace("+", "")
    token = token.replace(".0e", "e")
    token = token.replace(".", "p")
    out = []
    for ch in token:
        if ch.isalnum():
            out.append(ch)
    return "".join(out) or "NA"


def _curve_name_stem(structure_id: str, row: DopingRow) -> str:
    bulk = _format_doping_label(row.bulk_doping)
    source = _format_doping_label(row.source_doping)
    drain = _format_doping_label(row.drain_doping)
    if source == drain:
        return f"{structure_id}B{bulk}SD{source}"
    return f"{structure_id}B{bulk}S{source}D{drain}"


def _write_iv_curves(
    structure_id: str,
    row: DopingRow,
    curves_dir: Path,
    points: dict[str, list[tuple[float, float, float]]],
) -> tuple[Path, Path, int, int]:
    idvd_rows: list[dict[str, str]] = []
    idvg_rows: list[dict[str, str]] = []

    for tag, vals in points.items():
        if tag.startswith("IDVD"):
            sorted_vals = sorted(vals, key=lambda t: t[1])
            for gate_v, drain_v, drain_i in sorted_vals:
                idvd_rows.append(
                    {
                        "structure_id": structure_id,
                        "doping_run_id": row.run_id,
                        "curve_tag": tag,
                        "gate_v": f"{gate_v:.12e}",
                        "drain_v": f"{drain_v:.12e}",
                        "drain_current": f"{drain_i:.12e}",
                    }
                )
        elif tag.startswith("IDVG"):
            sorted_vals = sorted(vals, key=lambda t: t[0])
            for gate_v, drain_v, drain_i in sorted_vals:
                idvg_rows.append(
                    {
                        "structure_id": structure_id,
                        "doping_run_id": row.run_id,
                        "curve_tag": tag,
                        "gate_v": f"{gate_v:.12e}",
                        "drain_v": f"{drain_v:.12e}",
                        "drain_current": f"{drain_i:.12e}",
                    }
                )

    naming = _curve_name_stem(structure_id, row)
    idvd_csv = curves_dir / f"{naming}_IdVd.csv"
    idvg_csv = curves_dir / f"{naming}_IdVg.csv"

    _write_curve_csv(
        idvd_csv,
        ["structure_id", "doping_run_id", "curve_tag", "gate_v", "drain_v", "drain_current"],
        idvd_rows,
    )
    _write_curve_csv(
        idvg_csv,
        ["structure_id", "doping_run_id", "curve_tag", "gate_v", "drain_v", "drain_current"],
        idvg_rows,
    )

    return idvd_csv, idvg_csv, len(idvd_rows), len(idvg_rows)


def _copy_final_dat(
    structure_id: str,
    row: DopingRow,
    work_dir: Path,
    final_fields_dir: Path,
) -> Path:
    src = work_dir / "gmsh_mos2d_dd.dat"
    if not src.exists():
        return Path("")

    final_fields_dir.mkdir(parents=True, exist_ok=True)
    naming = _curve_name_stem(structure_id, row)
    dst = final_fields_dir / f"{naming}_final.dat"
    shutil.copy2(src, dst)
    return dst


def _run_one(
    structure_dir: Path,
    row: DopingRow,
    geometry: GeometryRow,
    base_dir: Path,
    python_exe: str,
    work_root: Path,
    curves_dir: Path,
    final_fields_dir: Path,
    keep_work: bool,
) -> dict[str, str]:
    structure_id = structure_dir.name
    work_dir = work_root / structure_id / row.run_id
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    _copy_base_files(base_dir, work_dir)
    _copy_structure_files(structure_dir, work_dir)
    _patch_geometry(work_dir / "gmsh_mos2d_create.py", geometry)
    _patch_doping(work_dir / "gmsh_mos2d_create.py", row)

    started = time.time()
    completed = subprocess.run(
        [python_exe, "gmsh_mos2d.py"],
        cwd=str(work_dir),
        capture_output=True,
        text=True,
        env=build_runtime_env(),
    )
    elapsed = time.time() - started

    logs_dir = structure_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    stdout_log = logs_dir / f"{row.run_id}.stdout.log"
    stderr_log = logs_dir / f"{row.run_id}.stderr.log"
    stdout_log.write_text(completed.stdout, encoding="utf-8")
    stderr_log.write_text(completed.stderr, encoding="utf-8")

    iv_points = _parse_ivpoints(completed.stdout)
    idvd_csv, idvg_csv, idvd_points, idvg_points = _write_iv_curves(
        structure_id=structure_id,
        row=row,
        curves_dir=curves_dir,
        points=iv_points,
    )
    final_dat = _copy_final_dat(
        structure_id=structure_id,
        row=row,
        work_dir=work_dir,
        final_fields_dir=final_fields_dir,
    )

    result = {
        "structure_id": structure_id,
        "doping_run_id": row.run_id,
        "gate_width": geometry.gate_width,
        "oxide_thickness": geometry.oxide_thickness,
        "bulk_doping": row.bulk_doping,
        "source_doping": row.source_doping,
        "drain_doping": row.drain_doping,
        "status": "ok" if completed.returncode == 0 else "failed",
        "return_code": str(completed.returncode),
        "elapsed_sec": f"{elapsed:.3f}",
        "ivpoint_count": str(_extract_ivpoint_count(completed.stdout)),
        "idvd_csv": str(idvd_csv),
        "idvg_csv": str(idvg_csv),
        "idvd_points": str(idvd_points),
        "idvg_points": str(idvg_points),
        "stdout_log": str(stdout_log),
        "stderr_log": str(stderr_log),
        "work_dir": str(work_dir),
        "final_dat": str(final_dat),
    }

    if not keep_work:
        shutil.rmtree(work_dir, ignore_errors=True)

    return result


def main() -> None:
    args = _parse_args()

    runs_dir = args.runs_dir.resolve()
    base_dir = args.base_dir.resolve()
    geometry_config = args.geometry_config.resolve()
    doping_config = args.doping_config.resolve()
    work_root = args.work_root.resolve()
    curves_dir = args.curves_dir.resolve()
    final_fields_dir = args.final_fields_dir.resolve()
    status_csv = args.status_csv.resolve()
    python_exe = resolve_python_exe(args.python_exe)

    if not runs_dir.exists():
        raise FileNotFoundError(f"Runs directory not found: {runs_dir}")
    if not base_dir.exists():
        raise FileNotFoundError(f"Base directory not found: {base_dir}")
    if not geometry_config.exists():
        raise FileNotFoundError(f"Geometry config not found: {geometry_config}")
    if not doping_config.exists():
        raise FileNotFoundError(f"Doping config not found: {doping_config}")

    work_root.mkdir(parents=True, exist_ok=True)
    curves_dir.mkdir(parents=True, exist_ok=True)
    final_fields_dir.mkdir(parents=True, exist_ok=True)

    structures = _list_structures(runs_dir, args.structure_glob)
    geometry_rows = _load_geometry_rows(geometry_config)
    rows = _load_doping_rows(doping_config)
    total_runs = len(structures) * len(rows)
    results: list[dict[str, str]] = []
    run_index = 0

    for structure_dir in structures:
        geometry = geometry_rows.get(structure_dir.name)
        if geometry is None:
            raise ValueError(
                f"Geometry config does not contain run_id '{structure_dir.name}': {geometry_config}"
            )
        for row in rows:
            run_index += 1
            label = f"{structure_dir.name}/{row.run_id}"
            print(
                f"[RUN {run_index}/{total_runs}] {label} "
                f"B={row.bulk_doping} S={row.source_doping} D={row.drain_doping}",
                flush=True,
            )
            try:
                result = _run_one(
                    structure_dir=structure_dir,
                    row=row,
                    geometry=geometry,
                    base_dir=base_dir,
                    python_exe=python_exe,
                    work_root=work_root,
                    curves_dir=curves_dir,
                    final_fields_dir=final_fields_dir,
                    keep_work=args.keep_work,
                )
                results.append(result)
                _write_status_csv(status_csv, results)
                print(
                    f"[DONE {run_index}/{total_runs}] {label} "
                    f"status={result['status']} "
                    f"elapsed={result['elapsed_sec']}s "
                    f"idvd_points={result['idvd_points']} "
                    f"idvg_points={result['idvg_points']}",
                    flush=True,
                )
                if result["status"] != "ok" and not args.continue_on_error:
                    raise SystemExit(f"DEVSIM failed for {label}")
            except Exception as exc:
                failed = {
                    "structure_id": structure_dir.name,
                    "doping_run_id": row.run_id,
                    "gate_width": geometry.gate_width,
                    "oxide_thickness": geometry.oxide_thickness,
                    "bulk_doping": row.bulk_doping,
                    "source_doping": row.source_doping,
                    "drain_doping": row.drain_doping,
                    "status": "failed",
                    "return_code": "",
                    "elapsed_sec": "",
                    "ivpoint_count": "",
                    "idvd_csv": "",
                    "idvg_csv": "",
                    "idvd_points": "",
                    "idvg_points": "",
                    "stdout_log": "",
                    "stderr_log": "",
                    "work_dir": "",
                    "final_dat": "",
                }
                results.append(failed)
                _write_status_csv(status_csv, results)
                print(f"[ERROR {run_index}/{total_runs}] {label}: {exc}", flush=True)
                if not args.continue_on_error:
                    raise

    print(f"\nCSV files written in: {curves_dir}")
    print(f"Final field dumps written in: {final_fields_dir}")
    print(f"Run status written: {status_csv}")


if __name__ == "__main__":
    main()
