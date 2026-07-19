from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from .selection_policy import FIELD_GROUPS, IMPORTANCE_POLICY, IV_GROUPS, SUMMARY_KEYS

MAGNITUDE_ORDER = {"negligible": 0, "minor": 1, "moderate": 2, "major": 3, "critical": 4, "not_applicable": 2}
CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}


def physical_group_for(evidence: dict[str, Any]) -> str:
    quantity = evidence.get("quantity")
    if quantity in IV_GROUPS: return IV_GROUPS[quantity]
    display, kind = evidence.get("field_display"), evidence.get("evidence_type")
    if kind == "distribution_width_change":
        if display == "electron_density": return "channel_inversion"
        if display == "hole_density": return "depletion_behavior"
        if display and "current_density" in display: return "current_transport"
    if kind == "regional_level_change":
        if display == "electron_density": return "channel_inversion"
        if display == "hole_density": return "depletion_behavior"
        if display == "srh_recombination": return "recombination_activity"
        if display and "current_density" in display: return "current_transport"
    if display == "srh_recombination": return "recombination_activity"
    return FIELD_GROUPS.get(kind, "carrier_distribution" if display else "curve_shape")


def _priority_class(score: float, eligible: bool) -> str:
    if not eligible: return "internal_only"
    for name, threshold in IMPORTANCE_POLICY["priority_thresholds"].items():
        if score >= threshold: return name
    return "internal_only"


def calculate_evidence_importance(evidence: dict[str, Any], comparisons: dict[str, dict[str, Any]], warnings: list[dict[str, Any]]) -> float:
    if "invalid_data" in evidence.get("suppression_reasons", []): return 0.0
    policy = IMPORTANCE_POLICY; kind = evidence.get("evidence_type")
    base = policy["metric_weights"].get(evidence.get("quantity"), policy["field_feature_weights"].get(kind, .45))
    magnitude = policy["magnitude_weights"].get(evidence.get("magnitude_class"), .5)
    confidence = policy["confidence_weights"].get(evidence.get("confidence"), .5)
    comparison = comparisons.get(evidence.get("comparison_id"), {})
    role = policy["comparison_role_weights"].get(comparison.get("comparison_role"), 1.0)
    claim = 1.0 if not comparison else policy["claim_quality_weights"].get(comparison.get("effective_claim_level", "descriptive_only"), .6)
    relevance = 1.0
    if evidence.get("field_display") and evidence.get("source_type") == "curve_parameter_analyzer": relevance = .70
    reasons = evidence.get("suppression_reasons", [])
    uniqueness = 0.0 if "duplicate_of_higher_priority_evidence" in reasons else (.85 if evidence.get("related_evidence_ids") else 1.0)
    warning_penalty = 1.0
    for warning in warnings:
        affected = set(warning.get("affected_evidence_ids", [])); linked_subjects = set(warning.get("subject_ids", []))
        quantities = set(warning.get("affected_quantities", []))
        regions = set(warning.get("affected_regions", []))
        explicitly_affected = evidence.get("evidence_id") in affected
        quantity_affected = bool(quantities and evidence.get("quantity") in quantities)
        region_affected = bool(regions and evidence.get("region") in regions)
        subject_affected = bool(linked_subjects and linked_subjects.intersection(evidence.get("subject_ids", [])))
        scoped_match = explicitly_affected or quantity_affected or region_affected or (subject_affected and not (affected or quantities or regions))
        if scoped_match:
            warning_penalty *= policy["warning_penalties"].get(warning.get("warning_type"), 1.0)
    value = base * magnitude * confidence * relevance * role * claim * uniqueness * warning_penalty
    return max(0.0, min(1.0, value if math.isfinite(value) else 0.0))


def score_and_select_evidence(evidence: list[dict[str, Any]], comparisons: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> None:
    comparison_map = {item["comparison_id"]: item for item in comparisons}
    grouped: dict[tuple[str | None, str], list[dict[str, Any]]] = defaultdict(list)
    for item in evidence:
        item["physical_group"] = physical_group_for(item)
        item["importance_score"] = calculate_evidence_importance(item, comparison_map, warnings)
        item["priority_class"] = _priority_class(item["importance_score"], bool(item.get("eligible_for_output")))
        item["selected_for_explanation"] = False; item["selection_rank"] = None; item["selection_reasons"] = []
        if item.get("eligible_for_output"): grouped[(item.get("comparison_id"), item["physical_group"])].append(item)
    selected = []
    limits = {"switching_control": 2, "drive_performance": 2, "saturation_behavior": 1, "threshold_behavior": 1,
              "curve_shape": 1, "field_concentration": 2, "current_transport": 2}
    for (_comparison_id, group), items in grouped.items():
        items.sort(key=lambda value: (-CONFIDENCE_ORDER.get(value.get("confidence"), 0), -MAGNITUDE_ORDER.get(value.get("magnitude_class"), 0), -value["importance_score"], value["evidence_id"]))
        limit = limits.get(group, 1)
        if group == "saturation_behavior" and not any(MAGNITUDE_ORDER.get(item.get("magnitude_class"), 0) >= MAGNITUDE_ORDER["major"] for item in items): limit = 0
        for index, item in enumerate(items):
            if index < limit and item["importance_score"] >= .30:
                item["selected_for_explanation"] = True; item["selection_reasons"] = [f"highest_in_{group}", f"{item['magnitude_class']}_change", f"{item['confidence']}_confidence"]; selected.append(item)
            else: item["selection_reasons"] = ["lower_rank_within_physical_group"]
    selected.sort(key=lambda value: (-value["importance_score"], value["evidence_id"]))
    for rank, item in enumerate(selected, 1): item["selection_rank"] = rank


def _valid_tradeoff_evidence(item: dict[str, Any]) -> bool:
    return bool(item.get("eligible_for_output") and item.get("selected_for_explanation")
                and CONFIDENCE_ORDER.get(item.get("confidence"), 0) >= CONFIDENCE_ORDER[IMPORTANCE_POLICY["tradeoff_min_confidence"]]
                and MAGNITUDE_ORDER.get(item.get("magnitude_class"), 0) >= MAGNITUDE_ORDER[IMPORTANCE_POLICY["tradeoff_min_magnitude"]])


def _match(item: dict[str, Any], specs: set[tuple[str, str]]) -> bool:
    return (item.get("quantity"), item.get("observation")) in specs or (item.get("evidence_type"), item.get("observation")) in specs


TRADEOFF_RULES = {
    "short_channel_control_vs_drive_performance": ({("dibl", "decreased"), ("ioff", "decreased"), ("ss", "decreased"), ("ion_ioff_ratio", "increased")}, {("ion", "decreased"), ("gm_max", "decreased"), ("ron", "increased")}, "short_channel_control", "drive_performance"),
    "drive_current_vs_off_state_leakage": ({("ion", "increased"), ("gm_max", "increased"), ("ron", "decreased")}, {("ioff", "increased"), ("ion_ioff_ratio", "decreased")}, "drive_performance", "off_state_leakage"),
    "gate_control_vs_oxide_field": ({("gm_max", "increased"), ("ss", "decreased"), ("distribution_width_change", "widened")}, {("hotspot_strength_change", "strengthened"), ("high_value_area_change", "expanded")}, "gate_control", "oxide_field"),
    "series_resistance_vs_drain_field": ({("ron", "decreased"), ("ion", "increased"), ("path_connectivity_change", "newly_connected")}, {("hotspot_strength_change", "strengthened"), ("high_value_area_change", "expanded"), ("crowding_change", "strengthened")}, "series_resistance", "drain_field_management"),
    "current_spreading_vs_current_crowding": ({("distribution_width_change", "widened"), ("high_value_area_change", "expanded"), ("path_connectivity_change", "newly_connected")}, {("crowding_change", "strengthened"), ("hotspot_strength_change", "strengthened")}, "current_spreading", "current_crowding"),
    "drive_performance_vs_saturation_behavior": ({("ion", "increased"), ("gm_max", "increased")}, {("gds", "increased"), ("lambda_clm", "increased")}, "drive_performance", "saturation_behavior"),
    "field_reduction_vs_extension_resistance": ({("hotspot_strength_change", "weakened"), ("high_value_area_change", "contracted"), ("contour_spacing_change", "widened")}, {("ron", "increased"), ("ion", "decreased"), ("path_connectivity_change", "disconnected")}, "drain_field_management", "series_resistance"),
    "channel_inversion_vs_field_concentration": ({("distribution_width_change", "widened"), ("regional_level_change", "increased")}, {("hotspot_strength_change", "strengthened"), ("crowding_change", "strengthened")}, "channel_inversion", "field_concentration"),
}


def build_tradeoff_conclusions(comparisons: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for comparison in comparisons:
        if comparison.get("changed_parameter_count", 0) >= 2: continue
        pair = [item for item in evidence if item.get("comparison_id") == comparison["comparison_id"] and _valid_tradeoff_evidence(item)]
        for label, (positive_specs, negative_specs, positive_target, negative_target) in TRADEOFF_RULES.items():
            positive = [item for item in pair if _match(item, positive_specs)]; negative = [item for item in pair if _match(item, negative_specs)]
            if not positive or not negative: continue
            # Region restrictions prevent generic density/field observations from satisfying oxide/drain-specific rules.
            if label == "gate_control_vs_oxide_field": negative = [item for item in negative if item.get("region") == "oxide"]
            if label in {"series_resistance_vs_drain_field", "field_reduction_vs_extension_resistance"}: negative_or_positive = negative if label.startswith("series") else positive; valid = [item for item in negative_or_positive if "drain" in (item.get("region") or "")]
            else: valid = [True]
            if label == "current_spreading_vs_current_crowding":
                positive = [item for item in positive if "current_density" in (item.get("field_display") or "")]
                negative = [item for item in negative if "current_density" in (item.get("field_display") or "")]
            if label == "channel_inversion_vs_field_concentration":
                positive = [item for item in positive if item.get("field_display") == "electron_density"]
                negative = [item for item in negative if item.get("field_display") == "electric_field"]
            if not positive or not negative or not valid: continue
            confidences = {item.get("confidence") for item in positive + negative}; confidence = "high" if confidences == {"high"} else "medium"
            pos_max, neg_max = max(item["importance_score"] for item in positive), max(item["importance_score"] for item in negative)
            importance = max(0.0, min(1.0, pos_max * .35 + neg_max * .35 + .20 + (.10 if comparison.get("effective_claim_level") == "cross_validated_controlled_association" else 0)))
            positive_key, negative_key = SUMMARY_KEYS[label]
            results.append({"conclusion_id": f"tradeoff_{comparison['comparison_id']}_{label}", "conclusion_type": "tradeoff", "comparison_id": comparison["comparison_id"], "label": label,
                            "positive_target": positive_target, "negative_target": negative_target, "positive_evidence_ids": [item["evidence_id"] for item in positive],
                            "negative_evidence_ids": [item["evidence_id"] for item in negative], "positive_summary_key": positive_key, "negative_summary_key": negative_key,
                            "confidence": confidence, "importance_score": importance, "priority_class": _priority_class(importance, True), "eligible_for_output": importance >= .50})
    return results


def build_mixed_group_conclusions(comparisons: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for comparison in comparisons:
        by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in evidence:
            if item.get("comparison_id") == comparison["comparison_id"] and _valid_tradeoff_evidence(item) and item.get("assessment") in {"improved", "degraded"}: by_group[item["physical_group"]].append(item)
        for group, items in by_group.items():
            favorable = [item for item in items if item["assessment"] == "improved"]; unfavorable = [item for item in items if item["assessment"] == "degraded"]
            if favorable and unfavorable:
                importance = max(item["importance_score"] for item in items)
                results.append({"conclusion_id": f"mixed_{comparison['comparison_id']}_{group}", "conclusion_type": "mixed_group_behavior", "comparison_id": comparison["comparison_id"],
                                "target_concept": group, "favorable_evidence_ids": [item["evidence_id"] for item in favorable], "unfavorable_evidence_ids": [item["evidence_id"] for item in unfavorable],
                                "importance_score": importance, "priority_class": _priority_class(importance, True), "eligible_for_output": True})
    return results


def build_variant_effect_conclusions(comparisons: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    primary = [item for item in comparisons if item.get("comparison_role") == "primary_baseline_to_variant"]
    if len(primary) < 2: return []
    first, second = primary[:2]; results = []
    first_items = {item["quantity"]: item for item in evidence if item.get("comparison_id") == first["comparison_id"] and item.get("evidence_type") == "metric_change" and _valid_tradeoff_evidence(item)}
    second_items = {item["quantity"]: item for item in evidence if item.get("comparison_id") == second["comparison_id"] and item.get("evidence_type") == "metric_change" and _valid_tradeoff_evidence(item)}
    for quantity in first_items.keys() & second_items.keys():
        a, b = first_items[quantity], second_items[quantity]; da, db = a.get("data", {}).get("percent_difference"), b.get("data", {}).get("percent_difference")
        if da is None or db is None or a.get("data", {}).get("unit") != b.get("data", {}).get("unit"): continue
        separation = abs(abs(float(da)) - abs(float(db)))
        if separation < IMPORTANCE_POLICY["variant_effect_min_separation"]: continue
        larger, smaller = (a, b) if abs(float(da)) > abs(float(db)) else (b, a)
        importance = max(a["importance_score"], b["importance_score"])
        results.append({"conclusion_id": f"variant_effect_{quantity}_{first['comparison_id']}_vs_{second['comparison_id']}", "conclusion_type": "variant_effect_comparison",
                        "primary_baseline_id": first["baseline_subject_id"], "comparison_ids": [first["comparison_id"], second["comparison_id"]], "quantity": quantity,
                        "larger_effect_comparison_id": larger["comparison_id"], "smaller_effect_comparison_id": smaller["comparison_id"],
                        "effect_direction_cmp_1_2": a["observation"], "effect_direction_cmp_1_3": b["observation"], "difference_basis": "absolute_percent_change",
                        "effect_separation_class": "major" if separation >= 15 else "moderate", "importance_score": importance,
                        "priority_class": _priority_class(importance, True), "eligible_for_output": True})
    return results


def rank_conclusions(conclusions: list[dict[str, Any]]) -> None:
    order = {"tradeoff": 2, "cross_validated_physical_trend": 3, "conflicting_physical_evidence": 4, "physical_relationship": 5,
             "variant_effect_comparison": 6, "no_meaningful_difference": 7, "mixed_group_behavior": 4}
    conclusions.sort(key=lambda item: (order.get(item.get("conclusion_type"), 8), -float(item.get("importance_score", 0)), item.get("conclusion_id", "")))
    for rank, item in enumerate(conclusions, 1): item["selection_rank"] = rank
