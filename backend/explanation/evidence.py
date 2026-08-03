from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

from .schemas import json_safe

MAGNITUDES = ("negligible", "minor", "moderate", "major", "critical", "not_applicable")
CONFIDENCES = ("low", "medium", "high")
ASSESSMENTS = ("improved", "degraded", "neutral_or_context_dependent", "not_applicable")
SUPPRESSION_REASONS = {"negligible_change", "low_confidence", "invalid_data", "missing_region",
                       "duplicate_of_higher_priority_evidence", "covered_by_conclusion", "below_output_threshold",
                       "conflicting_evidence", "not_relevant_to_current_display", "numeric_only_internal_evidence", "unsupported_analysis",
                       "not_comparable_visual_scale", "physically_ambiguous_sign"}
SOURCE_TYPES = {"curve_parameter_analyzer", "curve_array_analyzer", "field_global_analyzer", "field_region_analyzer",
                "field_spatial_analyzer", "energy_band_analyzer", "cross_validator"}
PHYSICAL_IMPLICATIONS = {"potential_gradient_strengthened", "potential_gradient_weakened", "channel_entry_more_restricted",
                         "channel_entry_less_restricted", "inversion_layer_expanded", "inversion_layer_contracted",
                         "channel_carrier_population_increased", "channel_carrier_population_decreased", "current_path_more_continuous",
                         "current_path_less_continuous", "current_crowding_strengthened", "current_crowding_weakened",
                         "field_crowding_strengthened", "field_crowding_weakened", "depletion_region_expanded", "depletion_region_contracted"}

OBSERVATIONS = {
    "metric_value": {"measured_value"},
    "metric_change": {"increased", "decreased", "unchanged"},
    "curve_point_change": {"increased", "decreased", "unchanged"},
    "curve_shape_change": {"overall_separation_increased", "overall_separation_decreased", "shifted_left", "shifted_right", "saturation_slope_increased", "saturation_slope_decreased", "unchanged"},
    "regional_level": {"dominant_high_value_region", "dominant_low_value_region", "localized_activity_region", "distributed_activity_region"},
    "regional_level_change": {"increased", "decreased", "unchanged"},
    "high_value_area_change": {"expanded", "contracted", "appeared", "disappeared", "unchanged"},
    "hotspot_strength_change": {"strengthened", "weakened", "unchanged", "appeared", "disappeared"},
    "hotspot_location_shift": {"shifted_toward_source", "shifted_toward_channel", "shifted_toward_drain", "shifted_deeper_into_bulk", "shifted_toward_surface", "shifted_left", "shifted_right", "region_changed", "location_unchanged"},
    "distribution_width_change": {"widened", "narrowed", "unchanged"},
    "contour_spacing_change": {"widened", "narrowed", "unchanged"},
    "path_connectivity_change": {"disconnected", "newly_connected", "unchanged"},
    "crowding_change": {"strengthened", "weakened", "unchanged"},
    "barrier_or_band_change": {"raised", "lowered", "band_bending_increased", "band_bending_decreased", "slope_increased", "slope_decreased", "unchanged"},
}

FIELD_ALLOWED = {
    "potential": {"regional_level", "regional_level_change", "high_value_area_change", "hotspot_location_shift", "distribution_width_change", "contour_spacing_change"},
    "electric_field": {"regional_level", "regional_level_change", "high_value_area_change", "hotspot_strength_change", "hotspot_location_shift", "distribution_width_change", "crowding_change"},
    "electron_density": {"regional_level", "regional_level_change", "high_value_area_change", "hotspot_location_shift", "distribution_width_change", "path_connectivity_change"},
    "hole_density": {"regional_level", "regional_level_change", "high_value_area_change", "hotspot_location_shift", "distribution_width_change"},
    "electron_current_density": {"regional_level", "regional_level_change", "high_value_area_change", "hotspot_strength_change", "hotspot_location_shift", "distribution_width_change", "path_connectivity_change", "crowding_change"},
    "hole_current_density": {"regional_level", "regional_level_change", "high_value_area_change", "hotspot_strength_change", "hotspot_location_shift", "distribution_width_change", "path_connectivity_change", "crowding_change"},
    "total_current_density": {"regional_level", "regional_level_change", "high_value_area_change", "hotspot_strength_change", "hotspot_location_shift", "distribution_width_change", "path_connectivity_change", "crowding_change"},
    "srh_recombination": {"regional_level", "regional_level_change", "high_value_area_change", "hotspot_strength_change", "hotspot_location_shift", "distribution_width_change"},
    "energy_band": {"regional_level", "regional_level_change", "hotspot_location_shift", "barrier_or_band_change"},
}

METRIC_MAP = {
    "vth_low_v": "vth_at_vd_0_05", "vth_high_v": "vth_at_vd_1_5", "ion_ma_per_um": "ion",
    "ioff_ma_per_um": "ioff", "ion_ioff_ratio": "ion_ioff_ratio", "ss_mv_per_dec": "ss",
    "dibl_gm_v_per_v": "dibl", "gm_max_ms_per_um": "gm_max", "gds_ms_per_um": "gds",
    "ron_kohm_um": "ron", "lambda_per_v": "lambda_clm",
}
PREFERENCES = {"ion": "higher_is_better", "ioff": "lower_is_better", "ion_ioff_ratio": "higher_is_better",
               "ss": "lower_is_better", "dibl": "lower_is_better", "gm_max": "higher_is_better",
               "gds": "lower_is_better", "ron": "lower_is_better", "lambda_clm": "lower_is_better",
               "vth_at_vd_0_05": "context_dependent", "vth_at_vd_1_5": "context_dependent"}
REGION_MAP = {"Gate": "gate", "Oxide": "oxide", "Source near-surface": "source_near_surface",
              "Source-side LDD near-surface": "source_side_ldd_near_surface", "Channel near-surface": "channel_near_surface",
              "Drain-side LDD near-surface": "drain_side_ldd_near_surface", "Drain near-surface": "drain_near_surface", "Deep bulk": "deep_bulk"}


@dataclass
class Evidence:
    evidence_id: str
    evidence_type: str
    source_type: str
    subject_ids: list[str]
    comparison_id: str | None
    field_display: str | None
    region: str | None
    quantity: str
    observation: str
    data: dict[str, Any]
    magnitude_class: str
    confidence: str
    importance_score: float
    assessment: str = "not_applicable"
    physical_implication: str | None = None
    eligible_for_output: bool = True
    suppression_reasons: list[str] = field(default_factory=list)
    related_evidence_ids: list[str] = field(default_factory=list)
    numeric_display: dict[str, Any] = field(default_factory=lambda: {"allowed": False, "preferred_fields": []})

    def to_dict(self) -> dict[str, Any]:
        result = json_safe(asdict(self))
        validate_evidence(result)
        return result


def _classify(value: float, thresholds: tuple[float, float, float, float], *, allow_critical: bool = True) -> str:
    value = abs(float(value))
    labels = ("negligible", "minor", "moderate", "major")
    for threshold, label in zip(thresholds, labels):
        if value < threshold:
            return label
    return "critical" if allow_critical else "major"


def classify_metric_magnitude(percent_difference: float) -> str:
    return _classify(percent_difference, (2, 5, 15, 40), allow_critical=False)


def classify_vth_magnitude(absolute_difference_v: float) -> str:
    return _classify(absolute_difference_v, (.01, .03, .10, .30), allow_critical=False)


def classify_log_ratio_magnitude(baseline: float, candidate: float) -> tuple[str, float | None]:
    if not _valid_number(baseline) or not _valid_number(candidate) or baseline <= 0 or candidate <= 0:
        return "not_applicable", None
    decades = math.log10(candidate / baseline)
    return _classify(decades, (.05, .15, .30, 1.0)), decades


def classify_field_area_magnitude(percentage_point_change: float) -> str:
    return _classify(percentage_point_change, (1, 3, 8, 20), allow_critical=False)


def classify_hotspot_strength_magnitude(percent_difference: float) -> str:
    return _classify(percent_difference, (3, 8, 20, 50), allow_critical=False)


def classify_displacement_magnitude(normalized_displacement: float, *, region_changed: bool = False) -> str:
    result = _classify(normalized_displacement * 100, (1, 3, 10, math.inf), allow_critical=False)
    return "major" if region_changed and result in {"negligible", "minor", "moderate"} else result


def determine_metric_assessment(observation: str, preference: str) -> str:
    if observation == "unchanged" or preference == "context_dependent":
        return "neutral_or_context_dependent"
    improved = (observation == "increased") == (preference == "higher_is_better")
    return "improved" if improved else "degraded"


def determine_evidence_confidence(*, data_valid: bool, robust: bool = True, interpolated: bool = False, sample_count: int | None = None) -> tuple[str, dict[str, Any]]:
    reasons = {"data_valid": data_valid, "robust_statistic": robust, "interpolated": interpolated, "sample_count": sample_count}
    if not data_valid or (sample_count is not None and sample_count < 5):
        return "low", reasons
    if interpolated or not robust or (sample_count is not None and sample_count < 20):
        return "medium", reasons
    return "high", reasons


def determine_output_eligibility(evidence: Evidence, *, data_valid: bool = True, relevant: bool = True) -> None:
    if not data_valid:
        evidence.suppression_reasons.append("invalid_data")
    if evidence.magnitude_class == "negligible" and evidence.evidence_type not in {"metric_value", "regional_level"}:
        evidence.suppression_reasons.append("negligible_change")
    if evidence.confidence == "low":
        evidence.suppression_reasons.append("low_confidence")
    if not relevant:
        evidence.suppression_reasons.append("not_relevant_to_current_display")
    evidence.suppression_reasons = list(dict.fromkeys(evidence.suppression_reasons))
    evidence.eligible_for_output = not evidence.suppression_reasons


def validate_evidence(evidence: dict[str, Any]) -> None:
    if evidence["source_type"] not in SOURCE_TYPES or evidence["evidence_type"] not in OBSERVATIONS:
        raise ValueError("Unsupported Evidence type or source type.")
    if evidence["observation"] not in OBSERVATIONS[evidence["evidence_type"]]:
        raise ValueError(f"{evidence['observation']} is invalid for {evidence['evidence_type']}.")
    if evidence["magnitude_class"] not in MAGNITUDES or evidence["confidence"] not in CONFIDENCES or evidence["assessment"] not in ASSESSMENTS:
        raise ValueError("Invalid Evidence classification enum.")
    if any(reason not in SUPPRESSION_REASONS for reason in evidence["suppression_reasons"]):
        raise ValueError("Invalid Evidence suppression reason.")
    if evidence.get("physical_implication") is not None and evidence["physical_implication"] not in PHYSICAL_IMPLICATIONS:
        raise ValueError("Invalid physical implication.")
    display = evidence.get("field_display")
    if display and evidence["evidence_type"] not in FIELD_ALLOWED.get(display, set()):
        raise ValueError(f"{evidence['evidence_type']} is not valid for {display}.")
    if not 0 <= evidence["importance_score"] <= 1:
        raise ValueError("importance_score must be between 0 and 1.")


def _valid_number(value: Any) -> bool:
    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _observation(before: float, after: float) -> str:
    return "increased" if after > before else ("decreased" if after < before else "unchanged")


def build_metric_value_evidence(subject_id: str, key: str, metric: dict[str, Any]) -> Evidence:
    quantity = METRIC_MAP[key]; value = metric.get("value"); valid = _valid_number(value)
    confidence, quality = determine_evidence_confidence(data_valid=valid)
    evidence = Evidence(f"ev_{subject_id}_{quantity}", "metric_value", "curve_parameter_analyzer", [subject_id], None, None, None,
                        quantity, "measured_value", {"value": value, "unit": metric.get("unit"), "extraction_status": "valid" if valid else "invalid", "quality_metadata": quality},
                        "not_applicable", confidence, .70, "neutral_or_context_dependent", numeric_display={"allowed": valid, "preferred_fields": ["value"] if valid else []})
    determine_output_eligibility(evidence, data_valid=valid)
    if quantity == "dibl" and valid and float(value) < 0:
        evidence.data["interpretation_status"] = "physically_ambiguous_sign"
        evidence.suppression_reasons = list(dict.fromkeys([*evidence.suppression_reasons, "physically_ambiguous_sign"]))
        evidence.eligible_for_output = False
    return evidence


def build_metric_change_evidence(comparison_id: str, subject_ids: list[str], key: str, change: dict[str, Any]) -> Evidence:
    quantity = METRIC_MAP[key]; before, after = change.get("baseline"), change.get("candidate")
    valid = _valid_number(before) and _valid_number(after); observation = _observation(before, after) if valid else "unchanged"
    absolute = after - before if valid else None
    percent = None if not valid or before == 0 else absolute / abs(before) * 100
    decade = None
    if quantity in {"ioff", "ion_ioff_ratio"}:
        magnitude, decade = classify_log_ratio_magnitude(before, after) if valid else ("not_applicable", None)
    elif quantity.startswith("vth_"):
        magnitude = classify_vth_magnitude(absolute) if valid else "not_applicable"
    else:
        magnitude = classify_metric_magnitude(percent) if percent is not None else "not_applicable"
    confidence, quality = determine_evidence_confidence(data_valid=valid)
    data = {"baseline": before, "candidate": after, "unit": change.get("unit"), "absolute_difference": absolute,
            "percent_difference": percent, "decade_difference": decade, "comparison_method": "log_ratio" if decade is not None else "relative_difference",
            "preference": PREFERENCES[quantity], "quality_metadata": quality}
    evidence = Evidence(f"ev_{comparison_id}_{quantity}", "metric_change", "curve_parameter_analyzer", subject_ids, comparison_id, None, None,
                        quantity, observation, data, magnitude, confidence, .85, determine_metric_assessment(observation, PREFERENCES[quantity]),
                        numeric_display={"allowed": valid, "preferred_fields": ["baseline", "candidate", "percent_difference"]})
    comparable = decade is not None if quantity in {"ioff", "ion_ioff_ratio"} else (valid if quantity.startswith("vth_") else percent is not None)
    determine_output_eligibility(evidence, data_valid=valid and comparable)
    # DIBL is defined as (Vth_low-Vth_high)/(Vd_high-Vd_low) and should be
    # non-negative for conventional barrier lowering. A negative prediction is
    # still preserved numerically, but must not be ranked as an improvement by
    # the generic lower-is-better rule or used to support a physical mechanism.
    if quantity == "dibl" and valid and (float(before) < 0 or float(after) < 0):
        evidence.assessment = "neutral_or_context_dependent"
        evidence.data["interpretation_status"] = "physically_ambiguous_sign"
        evidence.suppression_reasons = list(dict.fromkeys([*evidence.suppression_reasons, "physically_ambiguous_sign"]))
        evidence.eligible_for_output = False
    return evidence


def build_curve_point_change_evidence(comparison_id: str, subject_ids: list[str], curve_kind: str, index: int, point: dict[str, Any]) -> Evidence:
    before, after = point.get("end_current_baseline_mA_per_um"), point.get("end_current_candidate_mA_per_um")
    valid = _valid_number(before) and _valid_number(after); percent = point.get("end_current_percent_change")
    confidence, quality = determine_evidence_confidence(data_valid=valid)
    fixed_name, sweep_name = ("vg", "vd") if curve_kind == "idvd" else ("vd", "vg")
    data = {"curve_kind": curve_kind, "fixed_bias_name": fixed_name, "fixed_bias_value_v": point.get("fixed_bias_V"),
            "sweep_name": sweep_name, "sweep_position": "end", "sweep_value_v": None,
            "baseline_current_mA_per_um": before, "candidate_current_mA_per_um": after,
            "absolute_difference_mA_per_um": after - before if valid else None, "percent_difference": percent,
            "max_absolute_curve_difference_mA_per_um": point.get("max_absolute_curve_difference_mA_per_um"), "quality_metadata": quality}
    ev = Evidence(f"ev_{comparison_id}_{curve_kind}_{fixed_name}_{index}_end", "curve_point_change", "curve_array_analyzer", subject_ids, comparison_id, None, None,
                  "drain_current", _observation(before, after) if valid else "unchanged", data,
                  classify_metric_magnitude(percent) if _valid_number(percent) else "not_applicable", confidence, .55,
                  numeric_display={"allowed": valid, "preferred_fields": ["fixed_bias_value_v", "baseline_current_mA_per_um", "candidate_current_mA_per_um", "percent_difference"]})
    determine_output_eligibility(ev, data_valid=valid and _valid_number(percent))
    return ev


def build_curve_shape_change_evidence(*, comparison_id: str, subject_ids: list[str], quantity: str, observation: str, data: dict[str, Any], related_vth_id: str | None = None) -> Evidence:
    ev = Evidence(f"ev_{comparison_id}_{quantity}", "curve_shape_change", "curve_array_analyzer", subject_ids, comparison_id, None, None,
                  quantity, observation, data, "moderate", "medium", .45)
    if related_vth_id:
        ev.suppression_reasons.append("duplicate_of_higher_priority_evidence"); ev.related_evidence_ids.append(related_vth_id)
    determine_output_eligibility(ev)
    return ev


def _field_evidence(*, comparison_id: str, subject_ids: list[str], display: str, region: str | None, evidence_type: str,
                    quantity: str, observation: str, data: dict[str, Any], magnitude: str, confidence: str = "high",
                    implication: str | None = None, importance: float = .7) -> Evidence:
    region_id = REGION_MAP.get(region, region or "global")
    ev = Evidence(f"ev_{comparison_id}_{display}_{region_id}_{evidence_type}", evidence_type,
                  "energy_band_analyzer" if evidence_type == "barrier_or_band_change" else ("field_region_analyzer" if evidence_type in {"regional_level", "regional_level_change"} else "field_spatial_analyzer"),
                  subject_ids, comparison_id, display, region_id, quantity, observation, data, magnitude, confidence, importance,
                  physical_implication=implication, numeric_display={"allowed": False, "preferred_fields": []})
    determine_output_eligibility(ev, relevant=evidence_type in FIELD_ALLOWED.get(display, set()))
    return ev


def build_high_value_area_change_evidence(comparison_id: str, subject_ids: list[str], display: str, region: str, before: float, after: float) -> Evidence:
    delta_pp = (after - before) * 100; observation = "expanded" if delta_pp > 0 else ("contracted" if delta_pp < 0 else "unchanged")
    data = {"threshold_reference": "shared_p90", "baseline_area_fraction": before, "candidate_area_fraction": after,
            "percentage_point_change": delta_pp, "relative_area_change_percent": None if before == 0 else (after - before) / abs(before) * 100}
    return _field_evidence(comparison_id=comparison_id, subject_ids=subject_ids, display=display, region=region, evidence_type="high_value_area_change",
                           quantity=display + "_magnitude", observation=observation, data=data, magnitude=classify_field_area_magnitude(delta_pp), importance=.82)


def build_hotspot_strength_change_evidence(comparison_id: str, subject_ids: list[str], display: str, region: str, before: float, after: float) -> Evidence:
    percent = None if before == 0 else (after - before) / abs(before) * 100
    return _field_evidence(comparison_id=comparison_id, subject_ids=subject_ids, display=display, region=region, evidence_type="hotspot_strength_change",
                           quantity=display + "_magnitude", observation="strengthened" if after > before else ("weakened" if after < before else "unchanged"),
                           data={"comparison_statistic": "p99", "baseline_internal_value": before, "candidate_internal_value": after, "percent_difference": percent},
                           magnitude=classify_hotspot_strength_magnitude(percent) if percent is not None else "not_applicable", importance=.8)


def build_contour_spacing_change_evidence(comparison_id: str, subject_ids: list[str], region: str, before: float, after: float) -> Evidence:
    percent = None if before == 0 else (after - before) / abs(before) * 100
    narrowed = after < before
    return _field_evidence(comparison_id=comparison_id, subject_ids=subject_ids, display="potential", region=region, evidence_type="contour_spacing_change",
                           quantity="potential_contour_spacing", observation="narrowed" if narrowed else ("widened" if after > before else "unchanged"),
                           data={"baseline_internal_spacing_nm": before, "candidate_internal_spacing_nm": after, "percent_difference": percent},
                           magnitude=classify_hotspot_strength_magnitude(percent) if percent is not None else "not_applicable",
                           implication="potential_gradient_strengthened" if narrowed else "potential_gradient_weakened", importance=.75)


def build_hotspot_location_shift_evidence(comparison_id: str, subject_ids: list[str], display: str, shift_nm: float, delta_xy_nm: list[float], characteristic_length_nm: float) -> Evidence:
    normalized = None if characteristic_length_nm <= 0 else shift_nm / characteristic_length_nm
    dx, dy = delta_xy_nm
    observation = "location_unchanged" if shift_nm == 0 else ("shifted_right" if abs(dx) >= abs(dy) and dx > 0 else "shifted_left" if abs(dx) >= abs(dy) else "shifted_deeper_into_bulk" if dy > 0 else "shifted_toward_surface")
    return _field_evidence(comparison_id=comparison_id, subject_ids=subject_ids, display=display, region="global", evidence_type="hotspot_location_shift",
                           quantity=display + "_hotspot", observation=observation,
                           data={"displacement_nm": shift_nm, "delta_xy_nm": delta_xy_nm, "characteristic_length_nm": characteristic_length_nm, "normalized_displacement": normalized},
                           magnitude=classify_displacement_magnitude(normalized) if normalized is not None else "not_applicable", importance=.65)


def build_barrier_or_band_change_evidence(comparison_id: str, subject_ids: list[str], before: float, after: float) -> Evidence:
    raised = after > before
    return _field_evidence(comparison_id=comparison_id, subject_ids=subject_ids, display="energy_band", region="channel_near_surface", evidence_type="barrier_or_band_change",
                           quantity="channel_entry_barrier", observation="raised" if raised else ("lowered" if after < before else "unchanged"),
                           data={"baseline_internal_value_ev": before, "candidate_internal_value_ev": after, "absolute_difference_ev": after - before},
                           magnitude=classify_vth_magnitude(after - before), confidence="medium",
                           implication="channel_entry_more_restricted" if raised else "channel_entry_less_restricted", importance=.75)


def build_band_bending_change_evidence(
    comparison_id: str,
    subject_ids: list[str],
    before: float,
    after: float,
) -> Evidence:
    increased = after > before
    percent = None if before == 0 else (after - before) / abs(before) * 100
    evidence = _field_evidence(
        comparison_id=comparison_id,
        subject_ids=subject_ids,
        display="energy_band",
        region="channel_near_surface",
        evidence_type="barrier_or_band_change",
        quantity="vertical_band_bending",
        observation=(
            "band_bending_increased"
            if increased else
            "band_bending_decreased"
            if after < before else
            "unchanged"
        ),
        data={
            "baseline_internal_value_ev": before,
            "candidate_internal_value_ev": after,
            "absolute_difference_ev": after - before,
            "percent_difference": percent,
            "extraction": "vertical_channel_center_surface_to_deep_bulk",
        },
        magnitude=(
            classify_hotspot_strength_magnitude(percent)
            if percent is not None else "not_applicable"
        ),
        confidence="medium",
        importance=.74,
    )
    evidence.evidence_id = (
        f"ev_{comparison_id}_energy_band_channel_near_surface_"
        "vertical_band_bending_change"
    )
    return evidence


def build_channel_band_slope_change_evidence(
    comparison_id: str,
    subject_ids: list[str],
    before: float,
    after: float,
) -> Evidence:
    increased = after > before
    percent = None if before == 0 else (after - before) / abs(before) * 100
    evidence = _field_evidence(
        comparison_id=comparison_id,
        subject_ids=subject_ids,
        display="energy_band",
        region="channel_near_surface",
        evidence_type="barrier_or_band_change",
        quantity="channel_band_slope",
        observation=(
            "slope_increased"
            if increased else
            "slope_decreased"
            if after < before else
            "unchanged"
        ),
        data={
            "baseline_internal_value_ev_per_nm": before,
            "candidate_internal_value_ev_per_nm": after,
            "absolute_difference_ev_per_nm": after - before,
            "percent_difference": percent,
            "extraction": "horizontal_channel_source_edge_to_drain_edge",
        },
        magnitude=(
            classify_hotspot_strength_magnitude(percent)
            if percent is not None else "not_applicable"
        ),
        confidence="medium",
        importance=.72,
    )
    evidence.evidence_id = (
        f"ev_{comparison_id}_energy_band_channel_near_surface_"
        "channel_band_slope_change"
    )
    return evidence


# Interfaces reserved for analyzers that do not yet have stable calculations.
build_regional_level_evidence = _field_evidence
build_regional_level_change_evidence = _field_evidence
build_distribution_width_change_evidence = _field_evidence
build_path_connectivity_change_evidence = _field_evidence
build_crowding_change_evidence = _field_evidence


def build_standard_evidence(kind: str, context: dict[str, Any], items: list[dict[str, Any]],
                            comparisons: list[dict[str, Any]], pair_indices: list[tuple[int, int]]) -> list[dict[str, Any]]:
    """Convert existing analyzer output into one-observation-per-Evidence records."""
    evidence: list[Evidence] = []
    if kind == "iv_curve":
        for index, item in enumerate(items):
            for key, metric in item.get("electrical_parameters", {}).items():
                if key in METRIC_MAP:
                    evidence.append(build_metric_value_evidence(f"curve_{index + 1}", key, metric))
        for index, comparison in enumerate(comparisons):
            i, j = pair_indices[index]; comparison_id = f"cmp_{i + 1}_{j + 1}"; subjects = [f"curve_{i + 1}", f"curve_{j + 1}"]
            for key, change in comparison.get("electrical_parameter_changes", {}).items():
                if key in METRIC_MAP:
                    evidence.append(build_metric_change_evidence(comparison_id, subjects, key, change))
            for curve_kind, points in comparison.get("current_curve_changes", {}).items():
                for point_index, point in enumerate(points):
                    evidence.append(build_curve_point_change_evidence(comparison_id, subjects, curve_kind.lower(), point_index, point))
        return [item.to_dict() for item in evidence]

    display = context.get("display", "field")
    # Single-field regional ranking uses robust p99/log-p95 only to select a region; values stay internal.
    for index, item in enumerate(items):
        regions = item.get("specialized_metrics", {}).get("regions", {})
        ranked = []
        for region, values in regions.items():
            stats = values.get("log10_magnitude") or values.get("electric_field_V_per_cm") or values.get("magnitude") or {}
            rank_value = stats.get("p95") if "log10_magnitude" in values else stats.get("p99")
            if _valid_number(rank_value):
                ranked.append((float(rank_value), region))
        if ranked:
            _value, region = max(ranked)
            regional = _field_evidence(comparison_id=f"curve_{index + 1}", subject_ids=[f"curve_{index + 1}"], display=display, region=region,
                                       evidence_type="regional_level", quantity=display, observation="dominant_high_value_region",
                                       data={"ranking_among_regions": 1, "internal_statistic_basis": ["p95_log10" if "density" in display else "p99"]},
                                       magnitude="not_applicable", importance=.65)
            regional.comparison_id = None; regional.evidence_id = f"ev_curve_{index + 1}_{display}_{REGION_MAP.get(region, region)}_regional_level"
            evidence.append(regional)
    for index, comparison in enumerate(comparisons):
        i, j = pair_indices[index]; comparison_id = f"cmp_{i + 1}_{j + 1}"; subjects = [f"curve_{i + 1}", f"curve_{j + 1}"]
        base_regions = items[i].get("specialized_metrics", {}).get("regions", {})
        candidate_regions = items[j].get("specialized_metrics", {}).get("regions", {})
        for region in base_regions.keys() & candidate_regions.keys():
            before_region, after_region = base_regions[region], candidate_regions[region]
            stats_key = "electric_field_V_per_cm" if "electric_field_V_per_cm" in before_region else "magnitude"
            before_stats, after_stats = before_region.get(stats_key, {}), after_region.get(stats_key, {})
            before_p99, after_p99 = before_stats.get("p99"), after_stats.get("p99")
            if _valid_number(before_p99) and _valid_number(after_p99):
                percent = None if before_p99 == 0 else (after_p99 - before_p99) / abs(before_p99) * 100
                region_ev = _field_evidence(comparison_id=comparison_id, subject_ids=subjects, display=display, region=region,
                                            evidence_type="regional_level_change", quantity=display,
                                            observation=_observation(before_p99, after_p99),
                                            data={"comparison_space": "magnitude", "baseline_internal_value": before_p99, "candidate_internal_value": after_p99,
                                                  "difference": after_p99 - before_p99, "statistic": "p99"},
                                            magnitude=classify_hotspot_strength_magnitude(percent) if percent is not None else "not_applicable", importance=.7)
                evidence.append(region_ev)
                if "hotspot_strength_change" in FIELD_ALLOWED.get(display, set()):
                    evidence.append(build_hotspot_strength_change_evidence(comparison_id, subjects, display, region, before_p99, after_p99))
            fraction_key = "area_fraction_above_shared_high_field_threshold" if "area_fraction_above_shared_high_field_threshold" in before_region else "area_fraction_above_shared_display_threshold"
            before_fraction, after_fraction = before_region.get(fraction_key), after_region.get(fraction_key)
            if _valid_number(before_fraction) and _valid_number(after_fraction):
                evidence.append(build_high_value_area_change_evidence(comparison_id, subjects, display, region, before_fraction, after_fraction))
            before_spacing, after_spacing = before_region.get("estimated_median_contour_spacing_nm"), after_region.get("estimated_median_contour_spacing_nm")
            if display == "potential" and _valid_number(before_spacing) and _valid_number(after_spacing):
                evidence.append(build_contour_spacing_change_evidence(comparison_id, subjects, region, before_spacing, after_spacing))
        for visual in comparison.get("visual_evidence", []):
            if visual.get("visual_cue") == "hotspot_shift":
                length = max(float(items[i]["device_parameters"].get("L", 0)), float(items[j]["device_parameters"].get("L", 0)))
                evidence.append(build_hotspot_location_shift_evidence(comparison_id, subjects, display, visual["shift_nm"], visual["delta_xy_nm"], length))
            elif visual.get("visual_cue") == "channel_barrier_changed":
                evidence.append(build_barrier_or_band_change_evidence(comparison_id, subjects, visual["baseline_barrier_eV"], visual["candidate_barrier_eV"]))
            elif visual.get("visual_cue") == "vertical_band_bending_changed":
                evidence.append(build_band_bending_change_evidence(
                    comparison_id,
                    subjects,
                    visual["baseline_bending_eV"],
                    visual["candidate_bending_eV"],
                ))
            elif visual.get("visual_cue") == "channel_band_slope_changed":
                evidence.append(build_channel_band_slope_change_evidence(
                    comparison_id,
                    subjects,
                    visual["baseline_slope"],
                    visual["candidate_slope"],
                ))
    return [item.to_dict() for item in evidence]
