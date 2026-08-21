from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import math
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from ai.curve_model.inference import (  # noqa: E402
    FinalCurvePredictor,
    device_features,
    extract_electrical_parameters,
)
from ai.field_map_model.inference import (  # noqa: E402
    FieldMapPredictor,
    generate_gmsh_mesh,
)


@dataclass(frozen=True)
class Condition:
    case_id: str
    structure_id: str
    doping_run_id: str
    L: float
    T: float
    B: float
    SD: float
    LDD: float

    def feature_strings(self) -> dict[str, str]:
        return {
            name: format(getattr(self, name), ".15g")
            for name in ("L", "T", "B", "SD", "LDD")
        }


def _case_key(row: dict[str, str]) -> str:
    return f"{row['structure_id']}|{row['doping_run_id']}"


def _condition(row: dict[str, str]) -> Condition:
    return Condition(
        case_id=_case_key(row),
        structure_id=row["structure_id"],
        doping_run_id=row["doping_run_id"],
        L=float(row["gate_width"]) * 1.0e7,
        T=float(row["oxide_thickness"]) * 1.0e7,
        B=float(row["bulk_doping"]),
        SD=float(row["source_doping"]),
        LDD=float(row["LDD_doping"]),
    )


def load_accepted_conditions(
    status_csv: Path,
    retry_status_csv: Path | None,
) -> list[Condition]:
    rows: dict[str, dict[str, str]] = {}
    for path in (status_csv, retry_status_csv):
        if path is None:
            continue
        with Path(path).open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                if row.get("status") == "ok":
                    rows[_case_key(row)] = row
    return [_condition(rows[key]) for key in sorted(rows)]


def nearest_rank(values: Iterable[float], percentile: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("Cannot summarize an empty timing sequence")
    if not 0.0 < percentile <= 1.0:
        raise ValueError("percentile must be in (0, 1]")
    index = math.ceil(percentile * len(ordered)) - 1
    return ordered[index]


def summarize(values: Iterable[float]) -> dict[str, float | int]:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("Cannot summarize an empty timing sequence")
    return {
        "samples": len(ordered),
        "min_ms": ordered[0],
        "median_ms": statistics.median(ordered),
        "mean_ms": statistics.fmean(ordered),
        "p90_ms": nearest_rank(ordered, 0.90),
        "p95_ms": nearest_rank(ordered, 0.95),
        "max_ms": ordered[-1],
    }


def _measure_batch(
    operation: Callable[[], Any],
    batch_size: int,
) -> tuple[Any, float]:
    started = time.perf_counter_ns()
    result = None
    for _ in range(batch_size):
        result = operation()
    elapsed_ms = (time.perf_counter_ns() - started) / 1.0e6 / batch_size
    return result, elapsed_ms


def _validate_outputs(idvd: Any, idvg: Any, field: Any, parameters: dict[str, float]) -> None:
    if idvd.currents.shape != (2, 101) or len(idvd.grid) != 101:
        raise ValueError(f"Unexpected Id-Vd shape: {idvd.currents.shape}")
    if idvg.currents.shape != (2, 135) or len(idvg.grid) != 135:
        raise ValueError(f"Unexpected Id-Vg shape: {idvg.currents.shape}")
    arrays = [idvd.currents, idvg.currents, field.net_doping]
    arrays.extend(field.node_fields.values())
    arrays.extend(field.element_fields.values())
    if not all(np.isfinite(np.asarray(values)).all() for values in arrays):
        raise ValueError("Curve or field prediction contains a non-finite value")
    if not parameters or not all(math.isfinite(float(value)) for value in parameters.values()):
        raise ValueError("Electrical parameter extraction contains a non-finite value")


def _select_representatives(
    conditions: list[Condition],
    curve_predictor: FinalCurvePredictor,
) -> list[tuple[str, Condition]]:
    targets = {
        "short": (100.0, 5.0, 1.0e16, 1.0e20, 1.0e18),
        "default": (200.0, 20.0, 1.0e16, 1.0e20, 1.0e18),
        "long": (1600.0, 50.0, 1.0e16, 1.0e20, 1.0e18),
    }

    def distance(condition: Condition, target: tuple[float, ...]) -> float:
        values = (condition.L, condition.T, condition.B, condition.SD, condition.LDD)
        return sum((math.log10(value) - math.log10(goal)) ** 2 for value, goal in zip(values, target))

    selected: list[tuple[str, Condition]] = []
    used: set[str] = set()
    for label, target in targets.items():
        exact_geometry = [
            condition
            for condition in conditions
            if math.isclose(condition.L, target[0])
            and math.isclose(condition.T, target[1])
        ]
        candidates = exact_geometry or conditions
        for condition in sorted(candidates, key=lambda item: distance(item, target)):
            if condition.case_id in used:
                continue
            try:
                extract_electrical_parameters(*_predict_curves(curve_predictor, condition))
            except (FloatingPointError, ValueError):
                continue
            selected.append((label, condition))
            used.add(condition.case_id)
            break
        else:
            raise ValueError(f"No representative with valid parameter extraction for {label}")
    return selected


def _predict_curves(curve_predictor: FinalCurvePredictor, condition: Condition) -> tuple[Any, Any]:
    features = device_features(condition.feature_strings())
    return (
        curve_predictor.predict("idvd", features),
        curve_predictor.predict("idvg", features),
    )


def _predict_field(field_predictor: FieldMapPredictor, mesh: Any, condition: Condition) -> Any:
    return field_predictor.predict(
        mesh,
        condition.L,
        condition.T,
        condition.B,
        condition.SD,
        condition.LDD,
    )


def _time_representative(
    *,
    label: str,
    condition: Condition,
    curve_predictor: FinalCurvePredictor,
    field_predictor: FieldMapPredictor,
    geo_template: Path,
    warmup: int,
    repeats: int,
    batch_size: int,
) -> list[dict[str, Any]]:
    prepared_mesh = generate_gmsh_mesh(condition.L, condition.T, geo_template)
    for _ in range(warmup):
        idvd, idvg = _predict_curves(curve_predictor, condition)
        field = _predict_field(field_predictor, prepared_mesh, condition)
        parameters = extract_electrical_parameters(idvd, idvg)
        _validate_outputs(idvd, idvg, field, parameters)

    rows: list[dict[str, Any]] = []
    for repeat in range(1, repeats + 1):
        (idvd, idvg), curve_ms = _measure_batch(
            lambda: _predict_curves(curve_predictor, condition), batch_size
        )
        field, field_ms = _measure_batch(
            lambda: _predict_field(field_predictor, prepared_mesh, condition), batch_size
        )
        parameters, parameter_ms = _measure_batch(
            lambda: extract_electrical_parameters(idvd, idvg), batch_size
        )

        def simulation_to_result() -> tuple[Any, Any, Any]:
            curves = _predict_curves(curve_predictor, condition)
            prediction = _predict_field(field_predictor, prepared_mesh, condition)
            return curves[0], curves[1], prediction

        (sim_idvd, sim_idvg, sim_field), simulation_ms = _measure_batch(
            simulation_to_result, batch_size
        )

        mesh, mesh_ms = _measure_batch(
            lambda: generate_gmsh_mesh(condition.L, condition.T, geo_template), 1
        )

        def end_to_end() -> tuple[Any, Any, Any, dict[str, float]]:
            current_mesh = generate_gmsh_mesh(condition.L, condition.T, geo_template)
            curves = _predict_curves(curve_predictor, condition)
            prediction = _predict_field(field_predictor, current_mesh, condition)
            extracted = extract_electrical_parameters(*curves)
            return curves[0], curves[1], prediction, extracted

        (e2e_idvd, e2e_idvg, e2e_field, e2e_parameters), e2e_ms = _measure_batch(
            end_to_end, 1
        )
        _validate_outputs(sim_idvd, sim_idvg, sim_field, parameters)
        _validate_outputs(e2e_idvd, e2e_idvg, e2e_field, e2e_parameters)
        if len(mesh.node_xy_nm) == 0 or len(mesh.triangles) == 0:
            raise ValueError("Generated mesh is empty")

        common = {
            "scope": "representative_repeat",
            "label": label,
            "case_id": condition.case_id,
            "repeat": repeat,
            "L_nm": condition.L,
            "T_nm": condition.T,
            "B_cm3": condition.B,
            "SD_cm3": condition.SD,
            "LDD_cm3": condition.LDD,
            "mesh_nodes": len(prepared_mesh.node_xy_nm),
            "mesh_elements": len(prepared_mesh.triangles),
            "valid": True,
        }
        for metric, value in (
            ("curve", curve_ms),
            ("field_prepared_mesh", field_ms),
            ("parameter_extraction", parameter_ms),
            ("simulation_to_result", simulation_ms),
            ("mesh_generation", mesh_ms),
            ("user_end_to_end", e2e_ms),
        ):
            rows.append({**common, "metric": metric, "elapsed_ms": value})
    return rows


def _time_full_domain(
    *,
    conditions: list[Condition],
    curve_predictor: FinalCurvePredictor,
    field_predictor: FieldMapPredictor,
    geo_template: Path,
) -> list[dict[str, Any]]:
    mesh_cache: dict[tuple[float, float], Any] = {}
    rows: list[dict[str, Any]] = []
    for index, condition in enumerate(conditions, start=1):
        key = (condition.L, condition.T)
        if key not in mesh_cache:
            mesh_cache[key] = generate_gmsh_mesh(condition.L, condition.T, geo_template)
        mesh = mesh_cache[key]

        started = time.perf_counter_ns()
        idvd, idvg = _predict_curves(curve_predictor, condition)
        field = _predict_field(field_predictor, mesh, condition)
        elapsed_ms = (time.perf_counter_ns() - started) / 1.0e6
        parameters = extract_electrical_parameters(idvd, idvg)
        _validate_outputs(idvd, idvg, field, parameters)
        rows.append(
            {
                "scope": "full_domain_once",
                "label": "all",
                "case_id": condition.case_id,
                "repeat": 1,
                "metric": "simulation_to_result",
                "elapsed_ms": elapsed_ms,
                "L_nm": condition.L,
                "T_nm": condition.T,
                "B_cm3": condition.B,
                "SD_cm3": condition.SD,
                "LDD_cm3": condition.LDD,
                "mesh_nodes": len(mesh.node_xy_nm),
                "mesh_elements": len(mesh.triangles),
                "valid": True,
            }
        )
        if index % 250 == 0 or index == len(conditions):
            print(f"full-domain {index}/{len(conditions)}", flush=True)
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _package_versions() -> dict[str, str]:
    packages = ("numpy", "scipy", "scikit-learn", "xgboost", "gmsh")
    versions = {}
    for package in packages:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not-installed"
    return versions


def _summaries(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str, str, str], list[float]] = {}
    for row in rows:
        key = (str(row["scope"]), str(row["label"]), str(row["metric"]))
        groups.setdefault(key, []).append(float(row["elapsed_ms"]))
    return {
        f"{scope}/{label}/{metric}": summarize(values)
        for (scope, label, metric), values in sorted(groups.items())
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark packaged Curve and Field surrogate inference")
    parser.add_argument("--status-csv", type=Path, default=Path("D:/IDM/dataset/run_status.csv"))
    parser.add_argument("--retry-status-csv", type=Path, default=Path("D:/IDM/dataset/test_run_status.csv"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPOSITORY_ROOT / "docs/technical_validation/ai_runtime_benchmark",
    )
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--repeats", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--full-domain", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.warmup < 1 or args.repeats < 1 or args.batch_size < 1:
        raise ValueError("warmup, repeats, and batch-size must be positive")
    conditions = load_accepted_conditions(args.status_csv, args.retry_status_csv)
    if len(conditions) != 2574:
        raise ValueError(f"Expected 2574 accepted conditions, found {len(conditions)}")

    curve_dir = REPOSITORY_ROOT / "ai/model_artifacts/curve_model/final/pca_xgboost"
    field_dir = REPOSITORY_ROOT / "ai/model_artifacts/field_map_model/final/coordinate_mlp_physics"
    geo_template = REPOSITORY_ROOT / "tcad/data_extraction/base_case/gmsh_mos2d.geo"
    started = time.perf_counter_ns()
    curve_predictor = FinalCurvePredictor(curve_dir)
    field_predictor = FieldMapPredictor(field_dir)
    model_load_ms = (time.perf_counter_ns() - started) / 1.0e6

    representatives = _select_representatives(conditions, curve_predictor)
    rows: list[dict[str, Any]] = []
    for label, condition in representatives:
        print(f"representative {label}: {condition.case_id}", flush=True)
        rows.extend(
            _time_representative(
                label=label,
                condition=condition,
                curve_predictor=curve_predictor,
                field_predictor=field_predictor,
                geo_template=geo_template,
                warmup=args.warmup,
                repeats=args.repeats,
                batch_size=args.batch_size,
            )
        )
    if args.full_domain:
        rows.extend(
            _time_full_domain(
                conditions=conditions,
                curve_predictor=curve_predictor,
                field_predictor=field_predictor,
                geo_template=geo_template,
            )
        )

    output_dir = args.output_dir.resolve()
    raw_path = output_dir / "ai_runtime_raw.csv"
    _write_csv(raw_path, rows)
    summary = {
        "schema_version": 1,
        "benchmark_scope": {
            "accepted_conditions": len(conditions),
            "representatives": [
                {"label": label, **asdict(condition)}
                for label, condition in representatives
            ],
            "warmup": args.warmup,
            "repeats": args.repeats,
            "batch_size": args.batch_size,
            "full_domain": bool(args.full_domain),
        },
        "model_load_ms": model_load_ms,
        "timing_method": "time.perf_counter_ns; representative short operations batch-averaged",
        "hardware_specifications_recorded": False,
        "llm_included": False,
        "llm_note": "The local application uses the internet-connected Groq API; LLM latency is separate from surrogate simulation speed.",
        "validation": {
            "all_rows_valid": all(bool(row["valid"]) for row in rows),
            "timing_rows": len(rows),
            "full_domain_valid_cases": sum(row["scope"] == "full_domain_once" for row in rows),
        },
        "summaries": _summaries(rows),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "ai_runtime_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    environment = {
        "python": sys.version.split()[0],
        "packages": _package_versions(),
        "hardware_specifications_recorded": False,
    }
    (output_dir / "software_environment.json").write_text(
        json.dumps(environment, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"model_load_ms={model_load_ms:.3f}")
    print(f"raw={raw_path}")
    print(f"summary={output_dir / 'ai_runtime_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
