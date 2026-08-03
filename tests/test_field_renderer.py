import json

from backend.explanation.cache import JsonExplanationCache
from backend.explanation.field_renderer import render_field_explanation


SINGLE_POLICY = {"max_total_sentences": 5, "max_descriptions": 3, "max_comparisons": 0, "max_tradeoffs": 0, "max_cautions": 2,
                 "minimum_importance_score": .35, "field_internal_statistics_visible": False, "number_display_policy": "qualitative_only", "include_model_limitation": True}
COMPARISON_POLICY = {"max_total_sentences": 5, "max_descriptions": 1, "max_comparisons": 3, "max_tradeoffs": 1, "max_cautions": 1,
                     "minimum_importance_score": .35, "field_internal_statistics_visible": False, "number_display_policy": "qualitative_only", "include_model_limitation": True}


def subject(index): return {"subject_id": f"curve_{index}", "display_name": f"Curve {index}"}


def comparison(*, count=1, effective="controlled_association"):
    changes = [] if count == 0 else [{"parameter": "channel_length", "direction": "increased"}]
    if count > 1: changes.append({"parameter": "oxide_thickness", "direction": "decreased"})
    return {"comparison_id": "cmp_1_2", "baseline_subject_id": "curve_1", "candidate_subject_id": "curve_2", "comparison_order": 1,
            "changed_parameter_count": count, "changed_parameters": changes, "effective_claim_level": effective}


def evidence(eid, evidence_type, observation, *, display="electric_field", region="drain_side_ldd_near_surface", comparison_id="cmp_1_2",
             implication=None, importance=.8, data=None):
    return {"evidence_id": eid, "evidence_type": evidence_type, "source_type": "field_spatial_analyzer", "subject_ids": ["curve_1", "curve_2"],
            "comparison_id": comparison_id, "field_display": display, "region": region, "quantity": display, "observation": observation,
            "data": data or {"p99": 340000.0, "area_fraction": .187, "coordinates": [12.3, 4.5]}, "magnitude_class": "major",
            "confidence": "high", "importance_score": importance, "assessment": "not_applicable", "physical_implication": implication,
            "eligible_for_output": True, "suppression_reasons": [], "numeric_display": {"allowed": False, "preferred_fields": []}}


def payload(*, display="electric_field", mode="comparison", shared=True, evidence_items=None, conclusions=None, warnings=None, policy=None, scale="auto", fixed=True):
    context = {"mode": mode, "display": display, "scale": scale, "range_mode": "robust_1_99", "shared_color_scale": shared,
               "visual_evidence_policy": "supplied_evidence_only"}
    if fixed: context["fixed_bias"] = {"vg_v": 3.0, "vd_v": 3.0}
    return {"analysis_type": f"field_{mode}", "context": context, "subjects": [subject(1)] if mode == "single" else [subject(1), subject(2)],
            "comparisons": [] if mode == "single" else [comparison()], "evidence": evidence_items or [], "conclusions": conclusions or [],
            "warnings": warnings or [], "output_policy": dict(policy or (SINGLE_POLICY if mode == "single" else COMPARISON_POLICY))}


def text(result): return " ".join(sum(result.values(), []))


def test_01_single_electric_field():
    ev = evidence("regional", "regional_level", "dominant_high_value_region", comparison_id=None)
    result = render_field_explanation(payload(mode="single", evidence_items=[ev])); output = text(result)
    assert result["descriptions"] and not result["comparisons"] and "개선되었습니다" not in output and "340000" not in output and "prediction" in output


def test_02_shared_area_and_hotspot_are_merged():
    ev = [evidence("area", "high_value_area_change", "expanded"), evidence("hotspot", "hotspot_strength_change", "strengthened")]
    result = render_field_explanation(payload(evidence_items=ev)); output = text(result)
    assert "영역이 확대되고 hotspot도 강화" in output and "0.187" not in output and len(result["comparisons"]) == 1


def test_03_non_shared_scale_suppresses_visual_comparison():
    ev = [evidence("area", "high_value_area_change", "expanded"), evidence("hotspot", "hotspot_strength_change", "strengthened")]
    result = render_field_explanation(payload(shared=False, evidence_items=ev)); output = text(result)
    assert "확대" not in output and "강화" not in output and "서로 다른 normalization" in output


def test_04_potential_contour_spacing():
    ev = evidence("contour", "contour_spacing_change", "narrowed", display="potential", implication="potential_gradient_strengthened")
    output = text(render_field_explanation(payload(display="potential", evidence_items=[ev])))
    assert "contour 간격이 좁아져" in output and "Potential gradient가 강화" in output and "340000" not in output


def test_05_electron_density_width():
    ev = evidence("width", "distribution_width_change", "widened", display="electron_density", region="channel_near_surface")
    output = text(render_field_explanation(payload(display="electron_density", evidence_items=[ev])))
    assert "inversion layer가 확대" in output and "Ion 증가" not in output


def test_06_current_connectivity():
    ev = evidence("path", "path_connectivity_change", "newly_connected", display="total_current_density", region="global", data={"connectivity_score": .82})
    output = text(render_field_explanation(payload(display="total_current_density", evidence_items=[ev])))
    assert "Total current path가 더 연속적으로" in output and "0.82" not in output


def test_07_crowding_requires_crowding_evidence():
    hotspot = evidence("hotspot", "hotspot_strength_change", "strengthened")
    assert "집중" not in text(render_field_explanation(payload(evidence_items=[hotspot])))
    crowding = evidence("crowding", "crowding_change", "strengthened")
    assert "좁은 영역" in text(render_field_explanation(payload(evidence_items=[crowding])))


def test_08_hotspot_location_hides_coordinates():
    ev = evidence("location", "hotspot_location_shift", "shifted_right", data={"delta_xy_nm": [12.3, 4.5]})
    output = text(render_field_explanation(payload(evidence_items=[ev])))
    assert "오른쪽으로 이동" in output and "12.3" not in output and "4.5" not in output


def test_09_multiple_parameter_caution():
    p = payload(evidence_items=[evidence("area", "high_value_area_change", "expanded")]); p["comparisons"] = [comparison(count=2, effective="multi_parameter_association")]
    output = text(render_field_explanation(p)); assert "여러 device parameter" in output and "분리해 단정할 수 없습니다" in output


def test_10_controlled_condition():
    output = text(render_field_explanation(payload(evidence_items=[evidence("area", "high_value_area_change", "expanded")])))
    assert "Channel length만 변경" in output and "증명" not in output


def test_11_conflicting_evidence():
    ev = [evidence("area", "high_value_area_change", "expanded")]
    conclusion = {"conclusion_type": "physical_relationship", "comparison_id": "cmp_1_2", "physical_consistency": "partially_consistent",
                  "target_concept": "drain_field_management", "importance_score": .9, "eligible_for_output": True}
    output = text(render_field_explanation(payload(evidence_items=ev, conclusions=[conclusion])))
    assert "완전히 일치하지는 않았습니다" in output and "전반적으로 개선" not in output


def test_12_no_meaningful_difference():
    conclusion = {"conclusion_type": "no_meaningful_difference", "comparison_id": "cmp_1_2"}
    output = text(render_field_explanation(payload(conclusions=[conclusion])))
    assert "차이는 크지 않았습니다" in output and "영향을 주지" not in output


def test_13_missing_region():
    warning = {"warning_type": "missing_region", "eligible_for_output": True}
    output = text(render_field_explanation(payload(warnings=[warning])))
    assert "mesh region" in output and "비교를 제외" in output


def test_14_invalid_numeric_fallback():
    warning = {"warning_type": "invalid_numeric_value", "eligible_for_output": True}
    result = render_field_explanation(payload(warnings=[warning])); json.dumps(result, ensure_ascii=False, allow_nan=False)
    assert result["descriptions"] and "공간 분석 데이터" in text(result)


def test_15_srh_signed_magnitude():
    ev = evidence("area", "high_value_area_change", "expanded", display="srh_recombination", data={"value_mode": "signed", "magnitude_mode": "absolute_for_hotspot_detection"})
    output = text(render_field_explanation(payload(display="srh_recombination", scale="symlog", evidence_items=[ev])))
    assert "절대 크기" in output and "recombination과 generation" in output and "Recombination이 증가" not in output


def test_16_energy_band_approximation():
    ev = evidence("barrier", "barrier_or_band_change", "raised", display="energy_band", region="channel_near_surface", data={"barrier_ev": .61})
    output = text(render_field_explanation(payload(display="energy_band", evidence_items=[ev])))
    assert "Channel barrier가 Channel near-surface에서 상승" in output and "model-derived approximation" in output and "0.61" not in output


def test_17_output_policy():
    policy = dict(COMPARISON_POLICY, max_total_sentences=2, max_comparisons=1, max_cautions=0, minimum_importance_score=.9)
    ev = [evidence("low", "hotspot_location_shift", "shifted_right", importance=.5), evidence("high", "high_value_area_change", "expanded", importance=.95)]
    result = render_field_explanation(payload(evidence_items=ev, policy=policy)); assert sum(map(len, result.values())) <= 2 and "오른쪽" not in text(result)


def test_18_unsupported_display():
    result = render_field_explanation(payload(display="mesh")); assert not result["descriptions"] and "지원 대상이 아닙니다" in text(result)


def test_19_cache_key_keeps_field_context():
    first = payload(display="potential"); second = payload(display="electric_field")
    assert JsonExplanationCache.key(first, "mock", "v4") != JsonExplanationCache.key(second, "mock", "v4")
    second["context"]["range_mode"] = "full_range"
    assert JsonExplanationCache.key(first, "mock", "v4") != JsonExplanationCache.key(second, "mock", "v4")


def test_20_field_internal_numbers_never_rendered():
    ev = evidence("hotspot", "hotspot_strength_change", "strengthened", data={"p99": 987654.321, "threshold": 123456.789, "coordinates": [9.87, 6.54]})
    output = text(render_field_explanation(payload(evidence_items=[ev])))
    assert not any(value in output for value in ("987654", "123456", "9.87", "6.54"))


def test_strict_json():
    json.dumps(render_field_explanation(payload(display="mesh")), ensure_ascii=False, allow_nan=False)
