import json

import numpy as np
import pytest

from ai.result_interpreter.evidence import (
    build_contour_spacing_change_evidence,
    build_curve_point_change_evidence,
    build_curve_shape_change_evidence,
    build_high_value_area_change_evidence,
    build_hotspot_location_shift_evidence,
    build_metric_change_evidence,
    build_metric_value_evidence,
    classify_log_ratio_magnitude,
    determine_output_eligibility,
    validate_evidence,
)


def metric(value=1.0, unit="mA/um"):
    return {"value": value, "unit": unit}


def change(before, after, unit="mA/um"):
    return {"baseline": before, "candidate": after, "unit": unit}


def test_metric_value():
    ev = build_metric_value_evidence("curve_1", "ion_ma_per_um", metric()).to_dict()
    assert ev["evidence_type"] == "metric_value" and ev["comparison_id"] is None
    assert ev["numeric_display"]["allowed"] and ev["assessment"] == "neutral_or_context_dependent"
    json.dumps(ev, allow_nan=False)


def test_ion_decrease_is_degraded():
    ev = build_metric_change_evidence("cmp_1_2", ["curve_1", "curve_2"], "ion_ma_per_um", change(1.0, .8)).to_dict()
    assert ev["observation"] == "decreased" and ev["assessment"] == "degraded" and ev["magnitude_class"] == "major"
    assert ev["data"]["percent_difference"] == pytest.approx(-20)


def test_dibl_decrease_is_improved():
    ev = build_metric_change_evidence("cmp_1_2", ["curve_1", "curve_2"], "dibl_gm_v_per_v", change(100, 70, "mV/V")).to_dict()
    assert ev["observation"] == "decreased" and ev["assessment"] == "improved"


def test_vth_uses_absolute_change():
    ev = build_metric_change_evidence("cmp_1_2", ["curve_1", "curve_2"], "vth_low_v", change(.01, .05, "V")).to_dict()
    assert ev["magnitude_class"] == "moderate" and ev["assessment"] == "neutral_or_context_dependent"


def test_ioff_decade_change_is_critical():
    ev = build_metric_change_evidence("cmp_1_2", ["curve_1", "curve_2"], "ioff_ma_per_um", change(1e-6, 1e-7)).to_dict()
    assert ev["magnitude_class"] == "critical" and ev["assessment"] == "improved"
    assert ev["data"]["decade_difference"] == pytest.approx(-1)


def test_zero_denominator_is_safe():
    ev = build_metric_change_evidence("cmp_1_2", ["curve_1", "curve_2"], "ioff_ma_per_um", change(0, 1)).to_dict()
    assert ev["data"]["percent_difference"] is None and ev["data"]["decade_difference"] is None
    assert not ev["eligible_for_output"] and "invalid_data" in ev["suppression_reasons"]
    json.dumps(ev, allow_nan=False)


def test_curve_point_change_has_bias_and_no_assessment():
    point = {"fixed_bias_V": 1.5, "end_current_baseline_mA_per_um": .9, "end_current_candidate_mA_per_um": 1.08,
             "end_current_percent_change": 20, "max_absolute_curve_difference_mA_per_um": .2}
    ev = build_curve_point_change_evidence("cmp_1_2", ["curve_1", "curve_2"], "idvd", 0, point).to_dict()
    assert ev["data"]["fixed_bias_name"] == "vg" and ev["assessment"] == "not_applicable"


def test_field_area_expansion_is_internal_numeric():
    ev = build_high_value_area_change_evidence("cmp_1_2", ["curve_1", "curve_2"], "electric_field", "Drain-side LDD near-surface", .12, .18).to_dict()
    assert ev["observation"] == "expanded" and ev["magnitude_class"] == "moderate"
    assert ev["data"]["threshold_reference"] == "shared_p90" and not ev["numeric_display"]["allowed"]


def test_contour_spacing_narrowed():
    ev = build_contour_spacing_change_evidence("cmp_1_2", ["curve_1", "curve_2"], "Channel near-surface", 10, 7).to_dict()
    assert ev["observation"] == "narrowed" and ev["physical_implication"] == "potential_gradient_strengthened"


def test_hotspot_displacement_normalized():
    ev = build_hotspot_location_shift_evidence("cmp_1_2", ["curve_1", "curve_2"], "electric_field", 12, [12, 0], 100).to_dict()
    assert ev["magnitude_class"] == "major" and ev["data"]["normalized_displacement"] == pytest.approx(.12)
    assert not ev["numeric_display"]["allowed"]


def test_low_confidence_is_suppressed():
    ev = build_metric_value_evidence("curve_1", "ion_ma_per_um", metric(np.nan))
    assert not ev.eligible_for_output and "low_confidence" in ev.suppression_reasons


def test_negligible_change_is_preserved_but_suppressed():
    ev = build_metric_change_evidence("cmp_1_2", ["curve_1", "curve_2"], "ion_ma_per_um", change(1, 1.01)).to_dict()
    assert ev["magnitude_class"] == "negligible" and not ev["eligible_for_output"]
    assert "negligible_change" in ev["suppression_reasons"]


def test_transition_duplicate_links_vth():
    ev = build_curve_shape_change_evidence(comparison_id="cmp_1_2", subject_ids=["curve_1", "curve_2"], quantity="idvg_transition_position",
                                           observation="shifted_right", data={"shift_v": .1}, related_vth_id="ev_cmp_1_2_vth_at_vd_0_05").to_dict()
    assert not ev["eligible_for_output"] and "duplicate_of_higher_priority_evidence" in ev["suppression_reasons"]
    assert ev["related_evidence_ids"] == ["ev_cmp_1_2_vth_at_vd_0_05"]


def test_invalid_field_combination_rejected():
    ev = build_contour_spacing_change_evidence("cmp_1_2", ["curve_1", "curve_2"], "channel_near_surface", 10, 8).to_dict()
    ev["field_display"] = "electron_density"
    with pytest.raises(ValueError):
        validate_evidence(ev)


def test_strict_json_with_numpy_values():
    ev = build_metric_value_evidence("curve_1", "ion_ma_per_um", metric(np.float64(1e20))).to_dict()
    ev["related_evidence_ids"] = []
    json.dumps(ev, allow_nan=False)
