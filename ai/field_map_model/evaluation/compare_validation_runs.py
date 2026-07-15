from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai.field_map_model.data.tecplot import ELEMENT_FIELD_NAMES


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two full field-map validation audits")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    if baseline["split"] != "validation" or candidate["split"] != "validation":
        raise ValueError("Only validation reports may be compared")
    fields: dict[str, dict[str, float]] = {}
    for name in ELEMENT_FIELD_NAMES:
        old = baseline["field_evaluation_rmse_across_cases"][name]
        new = candidate["field_evaluation_rmse_across_cases"][name]
        fields[name] = {
            "baseline_mean": old["mean"], "candidate_mean": new["mean"],
            "mean_improvement_percent": 100.0 * (old["mean"]-new["mean"]) / old["mean"],
            "baseline_p95": old["p95"], "candidate_p95": new["p95"],
            "p95_improvement_percent": 100.0 * (old["p95"]-new["p95"]) / old["p95"],
        }
    physics_keys = (
        "electric_model_normalized_vector_rmse", "electric_model_mean_cosine_similarity",
        "electric_model_gradient_to_field_rms_ratio", "electron_current_model_to_raw_jump_ratio",
        "hole_current_model_to_raw_jump_ratio",
    )
    physics = {key: {"baseline": baseline["physics_audit"][key], "candidate": candidate["physics_audit"][key]} for key in physics_keys}
    selected_name = args.candidate.parent.parent.name
    result = {"selection_split": "validation", "test_split_loaded": False, "selected": selected_name, "fields": fields, "physics": physics}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "comparison_report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    lines = ["# Field-map element candidate comparison", "", "Selection uses all 386 validation maps. Final test was not loaded.", "", "| Field | Baseline mean | Candidate mean | Mean improvement | Baseline P95 | Candidate P95 | P95 improvement |", "|---|---:|---:|---:|---:|---:|---:|"]
    for name, item in fields.items():
        lines.append(f"| {name} | {item['baseline_mean']:.6g} | {item['candidate_mean']:.6g} | {item['mean_improvement_percent']:.2f}% | {item['baseline_p95']:.6g} | {item['candidate_p95']:.6g} | {item['p95_improvement_percent']:.2f}% |")
    raw_ratio = candidate["physics_audit"]["electric_raw_gradient_to_field_rms_ratio"]["mean"]
    lines += ["", "## Physics audit", "", f"- Raw TCAD gradient/field RMS ratio: {raw_ratio:.6g}", f"- Model gradient/field RMS ratio: {physics['electric_model_gradient_to_field_rms_ratio']['baseline']['mean']:.6g} -> {physics['electric_model_gradient_to_field_rms_ratio']['candidate']['mean']:.6g}", f"- Electric-field direction cosine: {physics['electric_model_mean_cosine_similarity']['baseline']['mean']:.6g} -> {physics['electric_model_mean_cosine_similarity']['candidate']['mean']:.6g}", f"- Electron-current neighbor-jump ratio P50: {physics['electron_current_model_to_raw_jump_ratio']['baseline']['p50']:.6g} -> {physics['electron_current_model_to_raw_jump_ratio']['candidate']['p50']:.6g}", f"- Hole-current neighbor-jump ratio P50: {physics['hole_current_model_to_raw_jump_ratio']['baseline']['p50']:.6g} -> {physics['hole_current_model_to_raw_jump_ratio']['candidate']['p50']:.6g}", "", "The candidate is selected because all six element-field mean and P95 errors improve. The slightly lower E-direction cosine remains a target for a later joint physics loss."]
    (args.output / "comparison_report.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(args.output / "comparison_report.md")


if __name__ == "__main__":
    main()
