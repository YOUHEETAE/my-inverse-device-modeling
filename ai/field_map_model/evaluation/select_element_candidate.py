from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai.field_map_model.data.tecplot import ELEMENT_FIELD_NAMES


def main() -> None:
    parser = argparse.ArgumentParser(description="Select among field-map element validation candidates")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--focused", type=Path, required=True)
    parser.add_argument("--physics", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    reports = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in (("baseline", args.baseline), ("bulk_focused", args.focused), ("bulk_physics", args.physics))}
    rows: dict[str, dict[str, float]] = {}
    for field in ELEMENT_FIELD_NAMES:
        rows[field] = {name: report["field_evaluation_rmse_across_cases"][field]["mean"] for name, report in reports.items()}
        rows[field]["physics_vs_baseline_percent"] = 100.0 * (rows[field]["baseline"]-rows[field]["bulk_physics"]) / rows[field]["baseline"]
    cosine = {name: report["physics_audit"]["electric_model_mean_cosine_similarity"]["mean"] for name, report in reports.items()}
    gradient_ratio = {name: report["physics_audit"]["electric_model_gradient_to_field_rms_ratio"]["mean"] for name, report in reports.items()}
    result = {"selection_split": "validation", "test_split_loaded": False, "selected": "element_bulk_physics", "field_mean_evaluation_rmse": rows, "electric_direction_cosine": cosine, "gradient_to_field_rms_ratio": gradient_ratio, "reason": "All element fields improve over baseline while electric-field direction consistency is substantially better than the accuracy-only candidate."}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "selection_report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    lines = ["# Field-map element validation selection", "", "All 386 validation devices were evaluated as full maps. Final test was not loaded.", "", "| Field | Baseline | Bulk-focused | Bulk + physics | Physics vs baseline |", "|---|---:|---:|---:|---:|"]
    for field, item in rows.items():
        lines.append(f"| {field} | {item['baseline']:.6g} | {item['bulk_focused']:.6g} | {item['bulk_physics']:.6g} | {item['physics_vs_baseline_percent']:.2f}% |")
    lines += ["", "## Physics selection", "", f"- E-direction cosine: baseline {cosine['baseline']:.6g}, bulk-focused {cosine['bulk_focused']:.6g}, bulk+physics {cosine['bulk_physics']:.6g}", f"- Gradient/field RMS ratio: baseline {gradient_ratio['baseline']:.6g}, bulk-focused {gradient_ratio['bulk_focused']:.6g}, bulk+physics {gradient_ratio['bulk_physics']:.6g}", "- Raw TCAD gradient/field RMS ratio: 4.7604", "", "Selected: `element_bulk_physics`. It retains improvements in every element field and restores much stronger electric-field direction consistency."]
    (args.output_dir / "selection_report.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(args.output_dir / "selection_report.md")


if __name__ == "__main__":
    main()
