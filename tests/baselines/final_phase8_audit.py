"""Run the frozen phase-1 cases through the current real-model pipeline."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from generate_phase1_baseline import generate


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]


def _strict_json(value: Any) -> bool:
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False)
        return True
    except (TypeError, ValueError):
        return False


def _response_valid(response: dict[str, Any]) -> bool:
    return set(response) == {"descriptions", "comparisons", "tradeoffs", "cautions"} and all(
        isinstance(response[key], list) and all(isinstance(item, str) and item.strip() for item in response[key])
        for key in response
    )


def audit_case(name: str, old: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    payload = current["payload"]
    interpretation = payload.get("interpretation", {})
    response = current["mock_response"]
    checks = {
        "strict_json": _strict_json(current),
        "response_schema": _response_valid(response),
        "nonempty_explanation": bool(response.get("descriptions")),
        "changed_from_phase1_mock": response != old.get("mock_response"),
    }
    details: dict[str, Any] = {
        "analysis_family": interpretation.get("analysis_family"),
        "interpretation_status": interpretation.get("status"),
        "old_sentence_counts": {key: len(value) for key, value in old["mock_response"].items()},
        "new_sentence_counts": {key: len(value) for key, value in response.items()},
    }
    if name.startswith("curve_"):
        comparative = name != "curve_single_default"
        checks["curve_status"] = interpretation.get("status") == ("complete" if comparative else "insufficient")
        checks["structured_curve_analysis"] = (not comparative) or bool(interpretation.get("performance_summaries"))
        if name == "curve_three_dopings_doubled":
            patterns = [item.get("result_pattern") for item in (interpretation.get("overall_assessment") or {}).get("comparison_results", [])]
            checks["no_difference_is_analyzed"] = "no_meaningful_change" in patterns
        details.update({
            "performance_summary_count": len(interpretation.get("performance_summaries", [])),
            "parameter_effect_count": len(interpretation.get("parameter_effects", [])),
            "interaction_count": len(interpretation.get("parameter_interactions", [])),
            "tradeoff_count": len(interpretation.get("observed_tradeoffs", [])),
        })
    else:
        quality = interpretation.get("analysis_quality", {})
        geometry = (interpretation.get("geometry_context") or {}).get("comparison", {})
        conclusions = interpretation.get("field_specific_conclusions", [])
        evidence_ids = {item.get("evidence_id") for item in payload.get("evidence", [])}
        feature_ids = {item.get("feature_id") for item in interpretation.get("spatial_features", [])}
        refs_valid = all(set(item.get("evidence_ids", [])).issubset(evidence_ids) and set(item.get("spatial_feature_ids", [])).issubset(feature_ids) for item in conclusions)
        checks.update({
            "geometry_alignment_high": quality.get("geometry_alignment") == "high",
            "region_coverage_high": quality.get("region_coverage") == "high",
            "normalized_profile_stable": quality.get("profile_stability") == "high",
            "regional_hotspot_stable": quality.get("hotspot_stability") == "high",
            "raw_index_and_pixel_forbidden": geometry.get("raw_index_comparison_allowed") is False and geometry.get("raw_pixel_comparison_allowed") is False,
            "regional_and_spatial_features_present": bool(interpretation.get("regional_summaries")) and bool(interpretation.get("spatial_features")),
            "field_conclusions_present": bool(conclusions),
            "conclusion_traceability": refs_valid,
            "structured_mock_not_fallback": not any("충분히 확보하지 못했습니다" in item for item in response.get("descriptions", [])),
        })
        details.update({
            "regional_summary_count": len(interpretation.get("regional_summaries", [])),
            "spatial_feature_count": len(interpretation.get("spatial_features", [])),
            "field_conclusion_count": len(conclusions),
            "analysis_quality": quality,
        })
    return {"passed": all(checks.values()), "checks": checks, "details": details}


def _markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Phase 8 final explanation audit", "",
        f"- Generated: {result['generated_at_utc']}",
        f"- Conda environment: `{result['environment']['conda_environment']}`",
        f"- Python: `{result['environment']['python_executable']}` ({result['environment']['python_version']})",
        f"- Mock model: `{result['environment']['mock_model']}`", "",
        "| Frozen real-model case | Result | Checks |", "|---|---:|---|",
    ]
    for name, case in result["cases"].items():
        failed = [key for key, passed in case["checks"].items() if not passed]
        lines.append(f"| `{name}` | {'PASS' if case['passed'] else 'FAIL'} | {'all' if not failed else ', '.join(failed)} |")
    lines.extend(["", f"Final result: **{result['summary']['passed_cases']}/{result['summary']['total_cases']} PASS**.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=HERE / "phase8_final_snapshot.json")
    parser.add_argument("--report", type=Path, default=REPO_ROOT / "docs/final_phase8_audit_report.md")
    args = parser.parse_args()
    before = json.loads((HERE / "phase1_explanation_baseline.json").read_text(encoding="utf-8"))
    current = generate()
    cases = {name: audit_case(name, before["cases"][name], case) for name, case in current["cases"].items()}
    result = {
        "audit_version": "phase8-v1", "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "conda_environment": "devsim_env", "python_executable": sys.executable,
            "python_version": platform.python_version(), "mock_model": current["mock_model"],
        },
        "summary": {"total_cases": len(cases), "passed_cases": sum(item["passed"] for item in cases.values())},
        "cases": cases, "current_snapshots": current["cases"],
    }
    args.snapshot.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    args.report.write_text(_markdown(result), encoding="utf-8")
    for name, case in cases.items():
        print(f"{'PASS' if case['passed'] else 'FAIL'} {name}")
        for check, passed in case["checks"].items():
            if not passed: print(f"  FAIL {check}")
    print(f"SUMMARY {result['summary']['passed_cases']}/{result['summary']['total_cases']} passed")
    return 0 if result["summary"]["passed_cases"] == result["summary"]["total_cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
