from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np

from ai.field_map_model.data.tecplot import ELEMENT_FIELD_NAMES
from ai.field_map_model.evaluation.visualization_app import DomainPredictor
from ai.field_map_model.inference.mesh_inputs import analytic_net_doping, generate_gmsh_mesh
from ai.field_map_model.training.screen_preprocessing import NODE_TARGET_NAMES, _coordinate_features

REGIONS = ("bulk", "oxide", "gate")


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


def _args() -> argparse.Namespace:
    root = _root()
    parser = argparse.ArgumentParser(description="Full validation and physics audit for field-map baseline")
    parser.add_argument("--dataset", type=Path, default=root / "ai/model_artifacts/field_map_model/dataset/fieldmap_dataset.h5")
    parser.add_argument("--model-dir", type=Path, default=root / "ai/model_artifacts/field_map_model/baselines/coordinate_mlp")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--geo-template", type=Path, default=root / "tcad/data_extraction/base_case/gmsh_mos2d.geo")
    parser.add_argument("--split", choices=("validation", "test"), default="validation")
    return parser.parse_args()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metric(raw: np.ndarray, pred: np.ndarray, transformer) -> dict[str, float]:
    raw64, pred64 = np.asarray(raw, dtype=np.float64), np.asarray(pred, dtype=np.float64)
    difference = pred64 - raw64
    eval_difference = transformer.transform(pred64).astype(np.float64) - transformer.transform(raw64).astype(np.float64)
    significant = np.abs(raw64) >= transformer.nonlinear_scale
    return {
        "points": int(len(raw64)),
        "raw_mae": float(np.mean(np.abs(difference))),
        "raw_rmse": float(np.sqrt(np.mean(difference * difference))),
        "evaluation_mae": float(np.mean(np.abs(eval_difference))),
        "evaluation_rmse": float(np.sqrt(np.mean(eval_difference * eval_difference))),
        "significant_sign_accuracy": float(np.mean(np.sign(raw64[significant]) == np.sign(pred64[significant]))) if np.any(significant) else None,
    }


def _gradient(values: np.ndarray, xy_nm: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    xy = np.asarray(xy_nm, dtype=np.float64) * 1e-7
    points, z = xy[triangles], np.asarray(values, dtype=np.float64)[triangles]
    x0, x1, x2 = points[:, 0, 0], points[:, 1, 0], points[:, 2, 0]
    y0, y1, y2 = points[:, 0, 1], points[:, 1, 1], points[:, 2, 1]
    denominator = x0*(y1-y2) + x1*(y2-y0) + x2*(y0-y1)
    gx = (z[:, 0]*(y1-y2) + z[:, 1]*(y2-y0) + z[:, 2]*(y0-y1)) / denominator
    gy = (z[:, 0]*(x2-x1) + z[:, 1]*(x0-x2) + z[:, 2]*(x1-x0)) / denominator
    return np.column_stack((gx, gy))


def _field_consistency(field: np.ndarray, negative_gradient: np.ndarray) -> dict[str, float]:
    field, grad = np.asarray(field, dtype=np.float64), np.asarray(negative_gradient, dtype=np.float64)
    scale = max(float(np.sqrt(np.mean(np.sum(field*field, axis=1)))), np.finfo(float).tiny)
    norm = np.linalg.norm(field, axis=1) * np.linalg.norm(grad, axis=1)
    valid = norm > 0
    field_rms = max(float(np.sqrt(np.mean(np.sum(field*field, axis=1)))), np.finfo(float).tiny)
    gradient_rms = float(np.sqrt(np.mean(np.sum(grad*grad, axis=1))))
    return {
        "normalized_vector_rmse": float(np.sqrt(np.mean(np.sum((field-grad)**2, axis=1))) / scale),
        "mean_cosine_similarity": float(np.mean(np.sum(field[valid]*grad[valid], axis=1) / norm[valid])) if np.any(valid) else None,
        "gradient_to_field_rms_ratio": gradient_rms / field_rms,
    }


def _adjacent_pairs(triangles: np.ndarray, regions: np.ndarray) -> np.ndarray:
    owners: dict[tuple[int, int], int] = {}
    pairs: list[tuple[int, int]] = []
    for index, triangle in enumerate(np.asarray(triangles)):
        for a, b in ((triangle[0], triangle[1]), (triangle[1], triangle[2]), (triangle[2], triangle[0])):
            edge = (int(min(a, b)), int(max(a, b)))
            previous = owners.get(edge)
            if previous is None: owners[edge] = index
            elif regions[previous] == regions[index]: pairs.append((previous, index))
    return np.asarray(pairs, dtype=np.int32)


def _jump(values: np.ndarray, pairs: np.ndarray) -> float:
    if not len(pairs): return float("nan")
    difference = np.asarray(values, dtype=np.float64)[pairs[:, 0]] - np.asarray(values, dtype=np.float64)[pairs[:, 1]]
    return float(np.median(np.linalg.norm(difference, axis=1)))


def _summarize(values: list[float]) -> dict[str, float]:
    finite = np.asarray(values, dtype=np.float64); finite = finite[np.isfinite(finite)]
    if not len(finite): return {}
    calculated = (np.mean(finite), *np.percentile(finite, (50, 90, 95, 99)), np.max(finite))
    return {name: float(value) for name, value in zip(("mean", "p50", "p90", "p95", "p99", "max"), calculated)}


def main() -> None:
    args = _args()
    if args.output_dir is None:
        args.output_dir = args.model_dir / ("full_validation" if args.split == "validation" else "final_test")
    marker_path = args.output_dir / "FINAL_TEST_COMPLETED.json"
    if args.split == "test" and marker_path.exists():
        raise RuntimeError(f"Final test was already completed; refusing to repeat it: {marker_path}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    predictors = {domain: DomainPredictor(args.model_dir / domain / "model.pt") for domain in ("node", "element")}
    rows: list[dict[str, object]] = []; per_field: dict[str, list[float]] = defaultdict(list)
    physics: dict[str, list[float]] = defaultdict(list); doping_errors: list[float] = []
    adjacency_cache: dict[str, np.ndarray] = {}
    with h5py.File(args.dataset, "r") as archive:
        case_keys = archive["case_keys"].asstr()[:]
        split_index = 1 if args.split == "validation" else 2
        evaluation_indices = np.flatnonzero(archive["case_split"][:] == split_index)
        for progress, case_index in enumerate(evaluation_indices, start=1):
            key = str(case_keys[case_index]); case = archive[f"cases/{key}"]
            structure = str(case.attrs["structure_id"]); mesh = archive[f"meshes/{structure}"]
            xy, triangles = mesh["node_xy_nm"][:], mesh["triangles"][:]
            node_region, element_region = mesh["node_region"][:], mesh["element_region"][:]
            node_raw, element_raw = case["node_fields"][:], case["element_fields"][:]
            node_features = _coordinate_features(case["device_features"][:], xy, node_region, node_raw[:, 0], xy)
            element_doping = node_raw[:, 0][triangles].mean(axis=1)
            element_features = _coordinate_features(case["device_features"][:], mesh["element_centroid_xy_nm"][:], element_region, element_doping, xy)
            node_pred, element_pred = predictors["node"].predict(node_features), predictors["element"].predict(element_features)
            row: dict[str, object] = {"case_id": str(case.attrs["case_id"]), "structure_id": structure}
            for domain, names, raw, pred in (("node", NODE_TARGET_NAMES, node_raw[:, 1:], node_pred), ("element", ELEMENT_FIELD_NAMES, element_raw, element_pred)):
                for column, name in enumerate(names):
                    metric = _metric(raw[:, column], pred[:, column], predictors[domain].transformers[column])
                    row[f"{name}_evaluation_rmse"] = metric["evaluation_rmse"]; per_field[name].append(metric["evaluation_rmse"])
                    for region_id, region_name in enumerate(REGIONS):
                        mask = (node_region if domain == "node" else element_region) == region_id
                        if np.any(mask): per_field[f"{name}@{region_name}"].append(_metric(raw[mask, column], pred[mask, column], predictors[domain].transformers[column])["evaluation_rmse"])
            predicted_doping = analytic_net_doping(xy, node_region, float(case["device_features"][0]), *case["physical_doping"][:])
            raw_log = np.sign(node_raw[:, 0])*np.log1p(np.abs(node_raw[:, 0])/1e15)
            pred_log = np.sign(predicted_doping)*np.log1p(np.abs(predicted_doping)/1e15)
            doping_error = float(np.sqrt(np.mean((pred_log-raw_log)**2))); doping_errors.append(doping_error); row["analytic_doping_signed_log_rmse"] = doping_error
            physics["negative_carrier_values"].append(float(np.sum(node_pred[:, 1:3] < 0)))
            for label, result in (("raw", _field_consistency(element_raw[:, :2], -_gradient(node_raw[:, 1], xy, triangles))), ("model", _field_consistency(element_pred[:, :2], -_gradient(node_pred[:, 0], xy, triangles)))):
                for metric_name, value in result.items():
                    if value is not None: physics[f"electric_{label}_{metric_name}"].append(value)
            pairs = adjacency_cache.setdefault(structure, _adjacent_pairs(triangles, element_region))
            for label, values in (("raw", element_raw), ("model", element_pred)):
                physics[f"electron_current_{label}_median_neighbor_jump"].append(_jump(values[:, 2:4], pairs))
                physics[f"hole_current_{label}_median_neighbor_jump"].append(_jump(values[:, 4:6], pairs))
            raw_e_jump = physics["electron_current_raw_median_neighbor_jump"][-1]
            raw_h_jump = physics["hole_current_raw_median_neighbor_jump"][-1]
            physics["electron_current_model_to_raw_jump_ratio"].append(physics["electron_current_model_median_neighbor_jump"][-1] / max(raw_e_jump, np.finfo(float).tiny))
            physics["hole_current_model_to_raw_jump_ratio"].append(physics["hole_current_model_median_neighbor_jump"][-1] / max(raw_h_jump, np.finfo(float).tiny))
            rows.append(row)
            if progress % 25 == 0 or progress == len(evaluation_indices): print(f"{args.split} {progress}/{len(evaluation_indices)}", flush=True)
        sample = archive[f"cases/{case_keys[int(evaluation_indices[0])]}" ]; features, physical = sample["device_features"][:], sample["physical_doping"][:]
        generated = generate_gmsh_mesh(float(features[0]), float(features[1]), args.geo_template)
        generated_doping = analytic_net_doping(generated.node_xy_nm, generated.node_region, float(features[0]), *physical)
        node_features = _coordinate_features(features, generated.node_xy_nm, generated.node_region, generated_doping, generated.node_xy_nm)
        element_doping = generated_doping[generated.triangles].mean(axis=1)
        element_features = _coordinate_features(features, generated.element_centroid_xy_nm, generated.element_region, element_doping, generated.node_xy_nm)
        node_output, element_output = predictors["node"].predict(node_features), predictors["element"].predict(element_features)
        stored = archive[f"meshes/{sample.attrs['structure_id']}"]
        mesh_report = {"case_id": str(sample.attrs["case_id"]), "stored_nodes": int(len(stored["node_xy_nm"])), "generated_nodes": int(len(generated.node_xy_nm)), "stored_elements": int(len(stored["triangles"])), "generated_elements": int(len(generated.triangles)), "generated_node_outputs_all_finite": bool(np.isfinite(node_output).all()), "generated_element_outputs_all_finite": bool(np.isfinite(element_output).all()), "note": "Gmsh version/algorithm may change point counts; the coordinate MLP accepts variable-size meshes."}
    field_summary = {name: _summarize(values) for name, values in per_field.items()}; physics_summary = {name: _summarize(values) for name, values in physics.items()}
    report = {"split": args.split, "cases": len(rows), "test_split_loaded": args.split == "test", "field_evaluation_rmse_across_cases": field_summary, "physics_audit": physics_summary, "analytic_net_doping_signed_log_rmse": _summarize(doping_errors), "regenerated_mesh_inference": mesh_report}
    report_stem = "full_validation_report" if args.split == "validation" else "final_test_report"
    metrics_name = "device_metrics.csv" if args.split == "validation" else "test_device_metrics.csv"
    (args.output_dir / f"{report_stem}.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    with (args.output_dir / metrics_name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    title = "Coordinate MLP full validation audit" if args.split == "validation" else "Field-map model final test"
    split_note = f"Validation devices: {len(rows)}. Test split was not loaded." if args.split == "validation" else f"Test devices: {len(rows)}. The validation-selected model was frozen before this one-time evaluation."
    lines = [f"# {title}", "", split_note, "", "## Full-map evaluation", "", "| Field | Mean | P50 | P90 | P95 | Max |", "|---|---:|---:|---:|---:|---:|"]
    for name in NODE_TARGET_NAMES + ELEMENT_FIELD_NAMES:
        s = field_summary[name]; lines.append(f"| {name} | {s['mean']:.6g} | {s['p50']:.6g} | {s['p90']:.6g} | {s['p95']:.6g} | {s['max']:.6g} |")
    lines += ["", "Values are per-device RMSE in each field's frozen evaluation/transform space.", "", "## Input and physics checks", "", f"- Analytic NetDoping signed-log RMSE (mean): {report['analytic_net_doping_signed_log_rmse']['mean']:.6g}", f"- Negative predicted carrier values: {physics_summary['negative_carrier_values']['max']:.0f} maximum per device", f"- Raw E vs -grad(V): normalized RMSE {physics_summary['electric_raw_normalized_vector_rmse']['mean']:.6g}, cosine {physics_summary['electric_raw_mean_cosine_similarity']['mean']:.6g}, gradient/field RMS ratio {physics_summary['electric_raw_gradient_to_field_rms_ratio']['mean']:.6g}", f"- Model E vs -grad(V): normalized RMSE {physics_summary['electric_model_normalized_vector_rmse']['mean']:.6g}, cosine {physics_summary['electric_model_mean_cosine_similarity']['mean']:.6g}, gradient/field RMS ratio {physics_summary['electric_model_gradient_to_field_rms_ratio']['mean']:.6g}", f"- Model/raw median neighbor-jump ratio: electron current P50 {physics_summary['electron_current_model_to_raw_jump_ratio']['p50']:.6g}, hole current P50 {physics_summary['hole_current_model_to_raw_jump_ratio']['p50']:.6g}", f"- Regenerated mesh: {mesh_report['generated_nodes']} nodes / {mesh_report['generated_elements']} triangles; all outputs finite: {mesh_report['generated_node_outputs_all_finite'] and mesh_report['generated_element_outputs_all_finite']}", "", f"Region metrics and current-neighbor jump distributions are in `{report_stem}.json`; device errors are in `{metrics_name}`."]
    report_md = args.output_dir / f"{report_stem}.md"
    report_md.write_text("\n".join(lines)+"\n", encoding="utf-8")
    if args.split == "test":
        marker = {"completed_at_utc": datetime.now(timezone.utc).isoformat(), "model_dir": str(args.model_dir.resolve()), "node_model_sha256": _sha256(args.model_dir / "node/model.pt"), "element_model_sha256": _sha256(args.model_dir / "element/model.pt"), "test_cases": len(rows), "report": str(report_md.resolve())}
        marker_path.write_text(json.dumps(marker, indent=2), encoding="utf-8")
    print(report_md)


if __name__ == "__main__": main()
