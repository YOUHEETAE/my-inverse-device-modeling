from __future__ import annotations

from typing import Any

from .field_policies import FIELD_POLICY_REGISTRY


FIELD_CONCLUSION_VERSION = "1.0"
MAX_CONCLUSIONS = 5
MAX_REGIONS_PER_CONCEPT = 3


IMPLICATION_MAP: dict[str, dict[tuple[str, str], tuple[str, str]]] = {
    "potential": {
        ("contour_spacing_change", "narrowed"): ("potential_gradient", "strengthened"),
        ("contour_spacing_change", "widened"): ("potential_gradient", "weakened"),
        ("regional_level_change", "increased"): ("regional_potential", "increased"),
        ("regional_level_change", "decreased"): ("regional_potential", "decreased"),
    },
    "electric_field": {
        ("hotspot_strength_change", "strengthened"): ("field_concentration", "strengthened"),
        ("hotspot_strength_change", "weakened"): ("field_concentration", "weakened"),
        ("crowding_change", "strengthened"): ("field_crowding", "strengthened"),
        ("crowding_change", "weakened"): ("field_crowding", "weakened"),
        ("high_value_area_change", "expanded"): ("high_field_extent", "expanded"),
        ("high_value_area_change", "contracted"): ("high_field_extent", "contracted"),
    },
    "electron_density": {
        ("regional_level_change", "increased"): ("channel_carrier_population", "increased"),
        ("regional_level_change", "decreased"): ("channel_carrier_population", "decreased"),
        ("distribution_width_change", "widened"): ("inversion_layer", "expanded"),
        ("distribution_width_change", "narrowed"): ("inversion_layer", "contracted"),
        ("path_connectivity_change", "newly_connected"): ("carrier_path", "more_continuous"),
        ("path_connectivity_change", "disconnected"): ("carrier_path", "less_continuous"),
    },
    "hole_density": {
        ("distribution_width_change", "widened"): ("depletion_region", "expanded"),
        ("distribution_width_change", "narrowed"): ("depletion_region", "contracted"),
        ("regional_level_change", "increased"): ("regional_hole_population", "increased"),
        ("regional_level_change", "decreased"): ("regional_hole_population", "decreased"),
    },
    "electron_current_density": {}, "hole_current_density": {}, "total_current_density": {},
    "srh_recombination": {
        ("hotspot_strength_change", "strengthened"): ("srh_activity_magnitude", "strengthened"),
        ("hotspot_strength_change", "weakened"): ("srh_activity_magnitude", "weakened"),
        ("high_value_area_change", "expanded"): ("srh_activity_extent", "expanded"),
        ("high_value_area_change", "contracted"): ("srh_activity_extent", "contracted"),
    },
    "energy_band": {
        ("barrier_or_band_change", "raised"): ("channel_entry_barrier", "raised"),
        ("barrier_or_band_change", "lowered"): ("channel_entry_barrier", "lowered"),
    },
}

CURRENT_MAP = {
    ("path_connectivity_change", "newly_connected"): ("current_path", "more_continuous"),
    ("path_connectivity_change", "strengthened"): ("current_path", "more_continuous"),
    ("path_connectivity_change", "disconnected"): ("current_path", "less_continuous"),
    ("crowding_change", "strengthened"): ("current_crowding", "strengthened"),
    ("crowding_change", "weakened"): ("current_crowding", "weakened"),
    ("high_value_area_change", "expanded"): ("current_path_extent", "expanded"),
    ("high_value_area_change", "contracted"): ("current_path_extent", "contracted"),
}
for _display in ("electron_current_density", "hole_current_density", "total_current_density"):
    IMPLICATION_MAP[_display] = CURRENT_MAP


def _support(evidence: dict[str, Any]) -> str:
    if evidence.get("confidence") == "high" and evidence.get("magnitude_class") in {"major", "moderate"}:
        return "strongly_supported"
    if evidence.get("confidence") == "high":
        return "supported"
    return "tentative"


def _feature_refs(spatial_features: list[dict[str, Any]], evidence: dict[str, Any]) -> list[str]:
    region = evidence.get("region")
    subject_ids = set(evidence.get("subject_ids", []))
    refs = []
    for feature in spatial_features:
        if feature.get("region") != region:
            continue
        feature_subjects = {value for key, value in feature.items() if key in {"subject_id", "baseline_subject_id", "candidate_subject_id"}}
        if subject_ids and not subject_ids.issubset(feature_subjects):
            continue
        if feature.get("feature_id"):
            refs.append(feature["feature_id"])
    return refs[:3]


def build_field_specific_conclusions(payload: Any) -> list[dict[str, Any]]:
    display = payload.context.get("display")
    policy = FIELD_POLICY_REGISTRY.get(display)
    mapping = IMPLICATION_MAP.get(display, {})
    if policy is None or not mapping:
        return []
    comparison_counts = {item["comparison_id"]: item.get("changed_parameter_count", 0) for item in payload.comparisons}
    candidates = []
    for evidence in payload.evidence:
        if not evidence.get("eligible_for_output") or evidence.get("field_display") != display:
            continue
        conclusion = mapping.get((evidence.get("evidence_type"), evidence.get("observation")))
        if conclusion is None or evidence.get("region") not in policy.region_priority:
            continue
        concept, assessment = conclusion
        changed_count = comparison_counts.get(evidence.get("comparison_id"))
        candidates.append((
            policy.evidence_score(evidence["evidence_type"]) + policy.region_score(evidence.get("region")) + float(evidence.get("importance_score", 0)),
            {
                "conclusion_version": FIELD_CONCLUSION_VERSION,
                "field_display": display, "conclusion_type": "field_specific_spatial_interpretation",
                "concept": concept, "assessment": assessment, "region": evidence.get("region"),
                "support_level": _support(evidence), "evidence_ids": [evidence["evidence_id"]],
                "spatial_feature_ids": _feature_refs(payload.interpretation.get("spatial_features", []), evidence),
                "comparison_id": evidence.get("comparison_id"),
                "causal_attribution": "not_assigned",
                "parameter_attribution_limit": "multiple_parameters_changed" if changed_count and changed_count > 1 else None,
                "claim_limit": "spatial_prediction_only",
            },
        ))
    conclusions = []
    used = set()
    concept_counts: dict[tuple[str | None, str], int] = {}
    for _score, item in sorted(candidates, key=lambda value: (-value[0], value[1]["evidence_ids"][0])):
        key = (item["comparison_id"], item["concept"], item["region"])
        concept_key = (item["comparison_id"], item["concept"])
        if key in used or concept_counts.get(concept_key, 0) >= MAX_REGIONS_PER_CONCEPT:
            continue
        item["conclusion_id"] = f"fsc_{len(conclusions) + 1}"
        conclusions.append(item); used.add(key)
        concept_counts[concept_key] = concept_counts.get(concept_key, 0) + 1
        if len(conclusions) >= MAX_CONCLUSIONS:
            break
    return conclusions


def validate_field_specific_conclusions(conclusions: list[dict[str, Any]], payload: Any) -> None:
    evidence_ids = {item["evidence_id"] for item in payload.evidence}
    feature_ids = {item.get("feature_id") for item in payload.interpretation.get("spatial_features", [])}
    if len(conclusions) > MAX_CONCLUSIONS:
        raise ValueError("Too many Field-specific conclusions.")
    for item in conclusions:
        if not set(item.get("evidence_ids", [])).issubset(evidence_ids):
            raise ValueError("Field conclusion references unknown Evidence.")
        if not set(item.get("spatial_feature_ids", [])).issubset(feature_ids):
            raise ValueError("Field conclusion references unknown spatial feature.")
        if item.get("causal_attribution") != "not_assigned":
            raise ValueError("Field-only conclusions cannot assign parameter causality.")
        if item.get("claim_limit") != "spatial_prediction_only":
            raise ValueError("Field conclusion claim limit is missing.")
