import json

from ai.result_interpreter.field_policies import FIELD_POLICY_REGISTRY
from ai.result_interpreter.field_renderer import render_field_explanation
from tests.test_field_renderer import COMPARISON_POLICY, SINGLE_POLICY, comparison, evidence, payload, subject, text


def relationship(consistency):
    return {"conclusion_type": "physical_relationship", "comparison_id": "cmp_1_2", "physical_consistency": consistency,
            "target_concept": "drain_field_management", "importance_score": .9, "eligible_for_output": True}


def test_potential_policy_and_single_region():
    ev = evidence("region", "regional_level", "dominant_high_value_region", display="potential", region="drain_side_ldd_near_surface", comparison_id=None)
    output = text(render_field_explanation(payload(display="potential", mode="single", evidence_items=[ev])))
    assert "주요 Potential 변화" in output and "Drain-side LDD" in output and "개선되었습니다" not in output
    assert FIELD_POLICY_REGISTRY["potential"].evidence_priority[0] == "contour_spacing_change"


def test_potential_contour_directions_and_no_number():
    narrow = evidence("n", "contour_spacing_change", "narrowed", display="potential", implication="potential_gradient_strengthened", data={"spacing_nm": 2.718})
    wide = evidence("w", "contour_spacing_change", "widened", display="potential", implication="potential_gradient_weakened", data={"spacing_nm": 9.81})
    assert "좁아져 Potential gradient가 강화" in text(render_field_explanation(payload(display="potential", evidence_items=[narrow])))
    output = text(render_field_explanation(payload(display="potential", evidence_items=[wide])))
    assert "넓어져 Potential gradient가 완화" in output and "9.81" not in output


def test_potential_consistency_and_conflict():
    ev = [evidence("n", "contour_spacing_change", "narrowed", display="potential")]
    consistent = text(render_field_explanation(payload(display="potential", evidence_items=ev, conclusions=[relationship("consistent")])))
    conflict = text(render_field_explanation(payload(display="potential", evidence_items=ev, conclusions=[relationship("partially_consistent")])))
    assert "일치합니다" in consistent and "완전히 일치하지는 않았습니다" in conflict


def test_electric_field_specific_hotspot_merge_and_limits():
    single = evidence("single", "regional_level", "dominant_high_value_region", comparison_id=None)
    assert "주요 hotspot" in text(render_field_explanation(payload(mode="single", evidence_items=[single])))
    ev = [evidence("hot", "hotspot_strength_change", "strengthened", data={"p99": 123456.0}), evidence("area", "high_value_area_change", "expanded", data={"area": .42})]
    output = text(render_field_explanation(payload(evidence_items=ev)))
    assert "고전계 영역이 확대되고 hotspot도 강화" in output and "123456" not in output and "0.42" not in output
    assert not any(term in output for term in ("Breakdown이 발생", "소자 수명이 감소", "Reliability가 확실"))


def test_electric_field_location_and_crowding():
    moved = evidence("move", "hotspot_location_shift", "shifted_right")
    crowded = evidence("crowd", "crowding_change", "strengthened")
    assert "오른쪽으로 이동" in text(render_field_explanation(payload(evidence_items=[moved])))
    assert "Field crowding이 강화" in text(render_field_explanation(payload(evidence_items=[crowded])))


def test_electron_density_inversion_merge_connectivity_and_limit():
    single = evidence("single", "regional_level", "dominant_high_value_region", display="electron_density", region="channel_near_surface", comparison_id=None)
    assert "inversion layer" in text(render_field_explanation(payload(display="electron_density", mode="single", evidence_items=[single])))
    ev = [evidence("level", "regional_level_change", "increased", display="electron_density", region="channel_near_surface"),
          evidence("width", "distribution_width_change", "widened", display="electron_density", region="channel_near_surface")]
    output = text(render_field_explanation(payload(display="electron_density", evidence_items=ev)))
    assert len([line for line in render_field_explanation(payload(display="electron_density", evidence_items=ev))["comparisons"] if "inversion layer" in line]) == 1
    assert "Ion 증가" not in output and "Current 증가" not in output
    connected = evidence("path", "path_connectivity_change", "newly_connected", display="electron_density", region="channel_near_surface")
    assert "Electron 분포 연결성이 강화" in text(render_field_explanation(payload(display="electron_density", evidence_items=[connected])))


def test_hole_density_deep_bulk_depletion_and_limits():
    single = evidence("bulk", "regional_level", "dominant_high_value_region", display="hole_density", region="deep_bulk", comparison_id=None)
    assert "Deep bulk" in text(render_field_explanation(payload(display="hole_density", mode="single", evidence_items=[single])))
    width = evidence("width", "distribution_width_change", "widened", display="hole_density", region="channel_near_surface")
    area = evidence("area", "high_value_area_change", "expanded", display="hole_density", region="channel_near_surface")
    output = text(render_field_explanation(payload(display="hole_density", evidence_items=[width, area])))
    assert "depletion 영역의 공간적 폭이 증가" in output and "Hole 변화 영역이 더 넓게" in output
    assert "mobility" not in output.lower() and "leakage 증가" not in output


def test_electron_current_path_width_crowding_and_terminal_limit():
    path = evidence("path", "path_connectivity_change", "newly_connected", display="electron_current_density", region="global")
    width = evidence("width", "distribution_width_change", "widened", display="electron_current_density", region="channel_near_surface")
    output = text(render_field_explanation(payload(display="electron_current_density", evidence_items=[path, width])))
    assert "current path가 더 연속적으로" in output and "공간적 폭도 확대" in output and "Ion 증가" not in output
    crowd = evidence("crowd", "crowding_change", "strengthened", display="electron_current_density")
    assert "Current crowding이 강화" in text(render_field_explanation(payload(display="electron_current_density", evidence_items=[crowd])))


def test_hole_current_activity_and_contribution_gate():
    active = evidence("active", "regional_level_change", "increased", display="hole_current_density", region="drain_near_surface")
    base = payload(display="hole_current_density", evidence_items=[active]); output = text(render_field_explanation(base))
    assert "Hole current activity가 강화" in output and "Electron contribution이 지배적" not in output
    base["conclusions"] = [{"conclusion_type": "carrier_contribution", "dominant_carrier": "electron", "eligible_for_output": True}]
    assert "Electron contribution이 지배적" in text(render_field_explanation(base))


def test_total_current_path_and_tradeoff():
    path = evidence("path", "path_connectivity_change", "newly_connected", display="total_current_density", region="global")
    width = evidence("width", "distribution_width_change", "widened", display="total_current_density", region="channel_near_surface")
    tradeoff = {"conclusion_type": "tradeoff", "label": "current_spreading_vs_current_crowding", "eligible_for_output": True}
    result = render_field_explanation(payload(display="total_current_density", evidence_items=[path, width], conclusions=[tradeoff]))
    output = text(result); assert "Total current path가 더 연속적으로" in output and "Trade-off" in output
    assert "Jtotal" not in output and "Ion 증가" not in output


def test_srh_absolute_and_signed_directions():
    absolute = evidence("hot", "hotspot_strength_change", "strengthened", display="srh_recombination", data={"value_mode": "signed"})
    assert "절대 크기가 강화" in text(render_field_explanation(payload(display="srh_recombination", scale="symlog", evidence_items=[absolute])))
    recombination = evidence("r", "regional_level_change", "increased", display="srh_recombination", data={"sign_class": "recombination_dominant"})
    generation = evidence("g", "regional_level_change", "increased", display="srh_recombination", data={"sign_class": "generation_dominant"})
    assert "recombination-dominant" in text(render_field_explanation(payload(display="srh_recombination", evidence_items=[recombination])))
    assert "generation-dominant" in text(render_field_explanation(payload(display="srh_recombination", evidence_items=[generation])))


def test_srh_without_sign_and_lifetime_limit():
    ev = evidence("area", "high_value_area_change", "expanded", display="srh_recombination", data={"value_mode": "signed"})
    output = text(render_field_explanation(payload(display="srh_recombination", evidence_items=[ev])))
    assert "SRH activity 영역이 확대" in output and "recombination-dominant" not in output and "generation-dominant" not in output
    assert "수명이 감소" not in output and "lifetime" not in output.lower()


def test_energy_band_variants_and_approximation():
    raised = evidence("up", "barrier_or_band_change", "raised", display="energy_band", region="channel_near_surface", data={"barrier_ev": .734})
    lowered = evidence("down", "barrier_or_band_change", "lowered", display="energy_band", region="channel_near_surface")
    bending = evidence("bend", "barrier_or_band_change", "band_bending_increased", display="energy_band", region="channel_near_surface")
    assert "Channel 진입이 더 억제" in text(render_field_explanation(payload(display="energy_band", evidence_items=[raised])))
    assert "Channel로 진입하기 쉬운" in text(render_field_explanation(payload(display="energy_band", evidence_items=[lowered])))
    output = text(render_field_explanation(payload(display="energy_band", evidence_items=[bending])))
    assert "band bending이 강화" in output and "model-derived approximation" in output and "0.734" not in output


def test_energy_band_location_and_single():
    single = evidence("single", "regional_level", "dominant_high_value_region", display="energy_band", region="channel_near_surface", comparison_id=None)
    assert "Channel barrier가 형성" in text(render_field_explanation(payload(display="energy_band", mode="single", evidence_items=[single])))
    moved = evidence("move", "hotspot_location_shift", "shifted_right", display="energy_band", region="channel_near_surface")
    assert "Channel barrier의 위치가 Drain 방향" in text(render_field_explanation(payload(display="energy_band", evidence_items=[moved])))


def test_specific_no_difference_and_policy_fallback():
    conclusion = {"conclusion_type": "no_meaningful_difference", "comparison_id": "cmp_1_2"}
    for display, phrase in (("potential", "Potential drop"), ("electric_field", "Electric field hotspot"), ("total_current_density", "Total current path"), ("energy_band", "Channel barrier")):
        assert phrase in text(render_field_explanation(payload(display=display, conclusions=[conclusion])))
    assert set(FIELD_POLICY_REGISTRY) == {"potential", "electric_field", "electron_density", "hole_density", "electron_current_density", "hole_current_density", "total_current_density", "srh_recombination", "energy_band"}


def test_multiple_controlled_warnings_output_and_json():
    ev = evidence("area", "high_value_area_change", "expanded")
    p = payload(evidence_items=[ev]); p["comparisons"] = [comparison(count=2, effective="multi_parameter_association")]
    assert "분리해 단정할 수 없습니다" in text(render_field_explanation(p))
    warning = {"warning_type": "extrapolation", "eligible_for_output": True}; controlled = payload(evidence_items=[ev], warnings=[warning])
    result = render_field_explanation(controlled); assert "Extrapolation" in text(result)
    json.dumps(result, ensure_ascii=False, allow_nan=False)


def test_forbidden_specific_claims_absent():
    displays = list(FIELD_POLICY_REGISTRY)
    output = " ".join(text(render_field_explanation(payload(display=display, evidence_items=[evidence("x", "regional_level_change", "increased", display=display)]))) for display in displays)
    forbidden = ("증명", "입증", "반드시 유발", "Breakdown이 발생", "소자 수명이 감소", "Reliability가 완전히 개선")
    assert not any(term in output for term in forbidden)
