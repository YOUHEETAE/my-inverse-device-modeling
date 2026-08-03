from __future__ import annotations

import hashlib
import json
from itertools import combinations
from typing import Any

from .schemas import AnalysisPayload
from .comparison_planner import build_comparison_plan
from .interpretation_contract import build_interpretation_scaffold, validate_interpretation_contract
from .curve_interpretation import build_curve_interpretation, validate_curve_interpretation
from .evidence import build_standard_evidence, validate_evidence
from .relationships import build_analysis_conclusions, determine_declared_claim_level
from .selection import (build_mixed_group_conclusions, build_tradeoff_conclusions,
                        build_variant_effect_conclusions, rank_conclusions,
                        score_and_select_evidence)

PARAMETERS = {
    "L": ("channel_length", "channel_length_nm", "nm"),
    "T": ("oxide_thickness", "oxide_thickness_nm", "nm"),
    "B": ("bulk_doping", "bulk_doping_cm3", "cm^-3"),
    "SD": ("source_drain_doping", "source_drain_doping_cm3", "cm^-3"),
    "LDD": ("ldd_doping", "ldd_doping_cm3", "cm^-3"),
}

POLICIES = {
    "iv_curve_single": (6, 4, 0, 0, 2, "selected_key_values_only"),
    "iv_curve_comparison": (12, 4, 6, 1, 1, "baseline_candidate_difference_percent"),
    "field_single": (5, 3, 0, 0, 2, "qualitative_only"),
    "field_comparison": (10, 2, 5, 1, 1, "qualitative_only"),
}


def build_output_policy(analysis_type: str) -> dict[str, Any]:
    total, descriptions, comparisons, tradeoffs, cautions, numbers = POLICIES[analysis_type]
    return {"max_total_sentences": total, "max_descriptions": descriptions, "max_comparisons": comparisons,
            "max_tradeoffs": tradeoffs, "max_cautions": cautions, "sentence_length": "medium",
            "number_display_policy": numbers, "field_internal_statistics_visible": False,
            "repeat_table_values": False, "deduplicate_similar_evidence": True,
            "minimum_importance_score": 0.35, "include_general_physical_principle": True,
            "include_model_limitation": True}


def build_subject(index: int, label: str, parameters: dict[str, Any], *, count: int) -> dict[str, Any]:
    normalized = {output: float(parameters[source]) for source, (_name, output, _unit) in PARAMETERS.items() if source in parameters}
    return {"subject_id": f"curve_{index + 1}", "display_name": label,
            "role": "single_subject" if count == 1 else ("primary_baseline" if index == 0 else "variant"),
            "device_parameters": normalized, "training_domain_status": "unknown", "data_quality_status": "valid"}


def build_device_parameter_changes(baseline: dict[str, Any], candidate: dict[str, Any]) -> list[dict[str, Any]]:
    changes = []
    for source, (name, output, unit) in PARAMETERS.items():
        if source not in baseline or source not in candidate or baseline[source] == candidate[source]:
            continue
        before, after = float(baseline[source]), float(candidate[source])
        changes.append({"parameter": name, "baseline": before, "candidate": after, "unit": unit,
                        "direction": "increased" if after > before else "decreased",
                        "absolute_difference": after - before,
                        "percent_difference": None if before == 0 else (after - before) / abs(before) * 100.0})
    return changes


def build_comparison(i: int, j: int, order: int, items: list[dict[str, Any]]) -> dict[str, Any]:
    changes = build_device_parameter_changes(items[i]["device_parameters"], items[j]["device_parameters"])
    count = len(changes)
    declared = determine_declared_claim_level(count)
    return {"comparison_id": f"cmp_{i + 1}_{j + 1}", "baseline_subject_id": f"curve_{i + 1}",
            "candidate_subject_id": f"curve_{j + 1}",
            "subject_ids": [f"curve_{i + 1}", f"curve_{j + 1}"],
            "comparison_role": "primary_baseline_to_variant" if i == 0 else "variant_to_variant",
            "comparison_order": order, "changed_parameter_count": count, "changed_parameters": changes,
            "is_single_parameter_controlled_comparison": count == 1,
            "declared_claim_level": declared, "effective_claim_level": declared, "claim_reduction_reasons": [],
            "causal_claim_level": declared}


def _id(analysis_type: str, context: dict[str, Any], subjects: list[dict[str, Any]]) -> str:
    value = json.dumps([analysis_type, context, subjects], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "analysis_" + hashlib.sha256(value.encode()).hexdigest()[:16]


def build_payload(*, kind: str, context: dict[str, Any], items: list[dict[str, Any]], legacy_comparisons: list[dict[str, Any]], warnings: list[str]) -> AnalysisPayload:
    mode = "single" if len(items) == 1 else "comparison"
    analysis_type = f"{kind}_{mode}" if kind == "field" else f"iv_curve_{mode}"
    subjects = [build_subject(i, item["label"], item["device_parameters"], count=len(items)) for i, item in enumerate(items)]
    pairs = (
        list(combinations(range(len(items)), 2))
        if len(items) > 1
        else []
    )
    comparisons = [build_comparison(i, j, order, items) for order, (i, j) in enumerate(pairs, 1)]
    evidence = build_standard_evidence(kind, context, items, legacy_comparisons, pairs)
    def warning_type(text: str) -> str:
        lowered = text.lower()
        if "zero_denominator" in lowered: return "zero_denominator"
        if "nonpositive_log_input" in lowered: return "nonpositive_log_input"
        if "parameter_extraction_failed" in lowered: return "parameter_extraction_failed"
        if "non-finite" in lowered: return "invalid_numeric_value"
        return "extrapolation"
    structured_warnings = [{"warning_id": f"warn_{i + 1:03d}", "warning_type": warning_type(text), "severity": "high",
                            "subject_ids": [], "affected_evidence_ids": [], "details": {"message": text},
                            "fallback_action": "include_caution_and_reduce_claim_strength", "eligible_for_output": True} for i, text in enumerate(warnings)]
    structured_warnings.append({"warning_id": f"warn_{len(structured_warnings) + 1:03d}", "warning_type": "model_approximation", "severity": "medium",
                                "subject_ids": [subject["subject_id"] for subject in subjects], "affected_evidence_ids": [],
                                "details": {"model_result_type": "prediction"}, "fallback_action": "include_model_limitation", "eligible_for_output": True})
    for comparison in comparisons:
        if comparison["changed_parameter_count"] > 1:
            structured_warnings.append({"warning_id": f"warn_{len(structured_warnings) + 1:03d}", "warning_type": "multiple_parameter_change", "severity": "medium",
                                        "subject_ids": [comparison["baseline_subject_id"], comparison["candidate_subject_id"]], "affected_evidence_ids": [],
                                        "details": {"comparison_id": comparison["comparison_id"]}, "fallback_action": "reduce_claim_strength", "eligible_for_output": True})
    for warning in structured_warnings:
        message = str(warning.get("details", {}).get("message", ""))
        if not warning.get("subject_ids"):
            warning["subject_ids"] = [f"curve_{index + 1}" for index, item in enumerate(items) if message.startswith(str(item.get("label", "")) + ":")]
        warning.setdefault("comparison_ids", [warning.get("details", {}).get("comparison_id")] if warning.get("details", {}).get("comparison_id") else [])
        quantities = [name for name in ("ion_ioff_ratio", "dibl", "ion", "ioff", "ss", "gm_max", "gds", "ron", "lambda_clm") if name.lower() in message.lower()]
        warning.setdefault("affected_quantities", quantities)
        warning.setdefault("affected_regions", [])
        if warning["warning_type"] == "model_approximation": warning["severity"] = "info"
    conclusions = build_analysis_conclusions(comparisons, evidence, structured_warnings)
    score_and_select_evidence(evidence, comparisons, structured_warnings)
    conclusions.extend(build_tradeoff_conclusions(comparisons, evidence))
    conclusions.extend(build_mixed_group_conclusions(comparisons, evidence))
    conclusions.extend(build_variant_effect_conclusions(comparisons, evidence))
    rank_conclusions(conclusions)
    normalized_context = {"mode": mode, "language": "ko", "technical_term_style": "english", "model_result_type": "prediction",
                          "primary_baseline_id": None if mode == "single" else "curve_1",
                          "effective_claim_level": "descriptive_only" if mode == "single" else "comparison_specific",
                          "comparison_strategy": "none" if mode == "single" else ("all_pairwise_selected_order" if kind == "iv_curve" else "selected_pair"), **context}
    comparison_plan = build_comparison_plan(
        subjects,
        preferred_baseline_id=normalized_context.get("primary_baseline_id"),
    )
    normalized_context["analyzed_subject_count"] = len(subjects)
    normalized_context["representative_subject_ids"] = list(
        comparison_plan.representative_subject_ids
    )
    if kind == "field" and len(subjects) > 1:
        normalized_context["comparison_strategy"] = (
            "all_pairwise_with_representative_display"
            if len(subjects) > 2
            else "selected_pair"
        )
    valid_count = sum(bool(item.get("eligible_for_output")) for item in evidence)
    suppressed_count = len(evidence) - valid_count
    normalized_context["analysis_status"] = "success" if valid_count and not suppressed_count else ("partial_success" if valid_count else "insufficient_data")
    normalized_context["valid_evidence_count"] = valid_count
    normalized_context["suppressed_evidence_count"] = suppressed_count
    interpretation = build_curve_interpretation(comparisons, evidence, conclusions) if kind == "iv_curve" else build_interpretation_scaffold(analysis_type)
    payload = AnalysisPayload(
        _id(analysis_type, normalized_context, subjects), analysis_type, normalized_context,
        subjects, comparisons, evidence, conclusions, structured_warnings,
        build_output_policy(analysis_type), interpretation,
        comparison_plan.to_dict(),
    )
    validate_analysis_payload(payload)
    return payload


def validate_analysis_payload(payload: AnalysisPayload) -> None:
    if payload.schema_version != "3.0" or payload.analysis_type not in POLICIES:
        raise ValueError("Unsupported analysis payload schema or type.")
    if payload.context.get("mode") == "single" and payload.comparisons:
        raise ValueError("Single analysis cannot contain comparisons.")
    if payload.comparison_plan:
        if payload.comparison_plan.get("subject_count") != len(payload.subjects):
            raise ValueError("Comparison plan subject count does not match payload.")
        if payload.comparison_plan.get("baseline_subject_id") not in {
            None, *(item["subject_id"] for item in payload.subjects)
        }:
            raise ValueError("Comparison plan references an unknown baseline.")
    validate_interpretation_contract(payload.interpretation, payload.analysis_type)
    if payload.analysis_type.startswith("iv_curve_"):
        validate_curve_interpretation(payload.interpretation, payload.comparisons, payload.evidence)
    evidence_ids = [item.get("evidence_id") for item in payload.evidence]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("Evidence IDs must be unique within an analysis.")
    subject_ids = {subject["subject_id"] for subject in payload.subjects}
    comparison_ids = {comparison["comparison_id"] for comparison in payload.comparisons}
    for item in payload.evidence:
        validate_evidence(item)
        if not set(item["subject_ids"]).issubset(subject_ids):
            raise ValueError("Evidence references an unknown subject.")
        if item["comparison_id"] is not None and item["comparison_id"] not in comparison_ids:
            raise ValueError("Evidence references an unknown comparison.")
    json.dumps(payload.to_dict(), allow_nan=False)
