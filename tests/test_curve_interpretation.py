import json
from itertools import combinations

from backend.explanation.payload_builders import build_payload
from backend.explanation.iv_renderer import render_iv_explanation


def metric(value, name, preference, unit=""):
    return {"value": value, "name": name, "unit": unit, "preference": preference}


def curve(label, *, length=200, tox=20, bulk=1e16, sd=1e20, ldd=1e18,
          ion=10.0, ioff=.1, ratio=100.0, dibl=.2, ss=100.0, gm=5.0, ron=1.0, gds=.2, clm=.1):
    return {
        "label": label,
        "device_parameters": {"L": length, "T": tox, "B": bulk, "SD": sd, "LDD": ldd},
        "electrical_parameters": {
            "ion_ma_per_um": metric(ion, "Ion", "higher_is_better", "mA/um"),
            "ioff_ma_per_um": metric(ioff, "Ioff", "lower_is_better", "mA/um"),
            "ion_ioff_ratio": metric(ratio, "Ion/Ioff", "higher_is_better"),
            "dibl_gm_v_per_v": metric(dibl, "DIBL", "lower_is_better", "V/V"),
            "ss_mv_per_dec": metric(ss, "SS", "lower_is_better", "mV/dec"),
            "gm_max_ms_per_um": metric(gm, "gm max", "higher_is_better"),
            "ron_kohm_um": metric(ron, "Ron", "lower_is_better"),
            "gds_ms_per_um": metric(gds, "gds", "lower_is_better"),
            "lambda_per_v": metric(clm, "lambda", "lower_is_better"),
            "vth_low_v": metric(.1, "Vth low", "context_dependent", "V"),
            "vth_high_v": metric(.2, "Vth high", "context_dependent", "V"),
        },
    }


def payload(baseline, candidate):
    changes = {}
    for key, before in baseline["electrical_parameters"].items():
        after = candidate["electrical_parameters"][key]
        changes[key] = {"baseline": before["value"], "candidate": after["value"], "unit": before["unit"]}
    return build_payload(
        kind="iv_curve", context={}, items=[baseline, candidate],
        legacy_comparisons=[{"electrical_parameter_changes": changes, "current_curve_changes": {}}], warnings=[],
    )


def payload_many(items):
    legacy = []
    for left, right in combinations(range(len(items)), 2):
        changes = {}
        for key, before in items[left]["electrical_parameters"].items():
            after = items[right]["electrical_parameters"][key]
            changes[key] = {"baseline": before["value"], "candidate": after["value"], "unit": before["unit"]}
        legacy.append({"electrical_parameter_changes": changes, "current_curve_changes": {}})
    return build_payload(kind="iv_curve", context={}, items=items, legacy_comparisons=legacy, warnings=[])


def improved_off_degraded_drive_candidate(**parameters):
    values = {"ion": 5, "ioff": .001, "ratio": 5000, "dibl": .08, "ss": 75, "gm": 2, "ron": 3} | parameters
    return curve("Curve 2", **values)


def summary_map(interpretation):
    return {item["performance_area"]: item for item in interpretation["performance_summaries"]}


def test_performance_areas_and_observed_tradeoff_are_synthesized():
    result = payload(curve("Curve 1"), improved_off_degraded_drive_candidate(length=1200)).interpretation
    summaries = summary_map(result)
    assert summaries["off_state_control"]["assessment"] == "improved"
    assert summaries["short_channel_control"]["assessment"] == "improved"
    assert summaries["drive_performance"]["assessment"] == "degraded"
    assert summaries["threshold_behavior"]["evaluation_mode"] == "descriptive"
    assert any(item["result_pattern"] == "leakage_reduction_with_drive_loss" for item in result["observed_tradeoffs"])
    assert result["overall_assessment"]["comparison_results"][0]["result_pattern"] == "leakage_reduction_with_drive_loss"


def test_controlled_channel_length_builds_grounded_mechanism_chains():
    baseline = curve(
        "Curve 1", length=700, ion=6, ioff=.001, ratio=6000,
        dibl=.10, ss=70, gm=3, ron=3, gds=.1, clm=.05,
    )
    candidate = curve(
        "Curve 2", length=300, ion=16.8, ioff=.1, ratio=250,
        dibl=.46, ss=84, gm=5, ron=1.2, gds=.2, clm=.12,
    )
    baseline["electrical_parameters"]["vth_low_v"]["value"] = .62
    baseline["electrical_parameters"]["vth_high_v"]["value"] = .60
    candidate["electrical_parameters"]["vth_low_v"]["value"] = .50
    candidate["electrical_parameters"]["vth_high_v"]["value"] = .44
    result_payload = payload(baseline, candidate)
    chains = {
        item["mechanism_key"]: item
        for item in result_payload.interpretation["mechanism_chains"]
    }
    assert {
        "channel_resistance_reduction",
        "drain_barrier_coupling_increase",
        "subthreshold_control_weakened",
        "saturation_control_weakened",
    } <= set(chains)
    assert {
        item["quantity"]
        for item in chains["drain_barrier_coupling_increase"]["observed_metric_links"]
    } >= {"dibl", "ioff", "vth_at_vd_1_5"}
    assert all(
        item["claim_level"] == "controlled_association"
        and item["supporting_evidence_ids"]
        for item in chains.values()
    )

    response = render_iv_explanation(result_payload.to_dict())
    text = " ".join(sum(response.values(), []))
    assert "Source 쪽 주입 장벽" in text
    assert "Gate 전압만으로 전류를 끄는 능력" in text
    assert "채널 저항 성분" in text
    assert "log(Id)-Vg의 subthreshold 구간" in text
    assert "낮은 Drain bias와 높은 Drain bias에서 추출한 threshold 위치 차이" in text
    assert "evidence_id" not in text and "ev_cmp" not in text


def test_reinforcing_multi_parameter_effect_is_explicit():
    result = payload(curve("Curve 1"), improved_off_degraded_drive_candidate(length=1200, tox=22)).interpretation
    interactions = {item["quantity"]: item for item in result["parameter_interactions"] if item["quantity"]}
    assert interactions["ion"]["interaction_type"] == "reinforcing"
    assert interactions["ion"]["observed_direction"] == "decreased"
    assert interactions["ion"]["observation_consistency"] == "consistent"
    assert {item["parameter"] for item in interactions["ion"]["contributors"]} == {"channel_length", "oxide_thickness"}
    assert any(item["tradeoff_type"] == "observed_performance_tradeoff" for item in result["observed_tradeoffs"])
    assert result["mechanism_chains"] == []


def test_competing_multi_parameter_effect_reports_observed_side_without_causality():
    result = payload(curve("Curve 1"), improved_off_degraded_drive_candidate(length=1200, tox=17)).interpretation
    ion = next(item for item in result["parameter_interactions"] if item["quantity"] == "ion")
    assert ion["interaction_type"] == "competing"
    assert ion["observed_direction"] == "decreased"
    assert ion["observation_consistency"] == "consistent_with_one_contributor"
    assert ion["claim_level"] == "combined_association"


def test_three_doping_changes_keep_analysis_and_independent_effects():
    candidate = improved_off_degraded_drive_candidate(bulk=2e16, sd=2e20, ldd=2e18)
    result = payload(curve("Curve 1"), candidate).interpretation
    assert result["status"] == "complete"
    assert len(result["parameter_effects"]) == 3
    assert any(item["interaction_type"] == "reinforcing" and item["quantity"] == "ion" for item in result["parameter_interactions"])
    assert any(item["interaction_type"] == "independent" and any(c["parameter"] == "bulk_doping" for c in item["contributors"]) for item in result["parameter_interactions"])
    json.dumps(result, ensure_ascii=False, allow_nan=False)


def test_single_curve_has_no_comparative_overall_claim():
    item = curve("Curve 1")
    result_payload = build_payload(kind="iv_curve", context={}, items=[item], legacy_comparisons=[], warnings=[])
    result = result_payload.interpretation
    assert result["status"] == "insufficient"
    assert result["overall_assessment"] is None
    response = render_iv_explanation(result_payload.to_dict())
    text = " ".join(sum(response.values(), []))
    assert "log(Id)–Vg" in text
    assert "저전압 Id–Vd 선형 구간" in text
    assert "고전압 saturation 구간" in text
    assert "개선됐" not in text and "악화됐" not in text


def test_single_negative_dibl_is_excluded_and_explained():
    item = curve("Curve 1", dibl=-.2)
    result_payload = build_payload(kind="iv_curve", context={}, items=[item], legacy_comparisons=[], warnings=[])
    response = render_iv_explanation(result_payload.to_dict())
    text = " ".join(sum(response.values(), []))
    assert "DIBL -" not in text
    assert "DIBL 부호" in text


def test_negative_dibl_is_not_misclassified_as_short_channel_improvement():
    result_payload = payload(curve("Curve 1", dibl=-.20), improved_off_degraded_drive_candidate(length=1200, dibl=-.30))
    dibl = next(item for item in result_payload.evidence if item.get("quantity") == "dibl" and item.get("comparison_id"))
    assert dibl["assessment"] == "neutral_or_context_dependent"
    assert "physically_ambiguous_sign" in dibl["suppression_reasons"]
    assert "short_channel_control" not in summary_map(result_payload.interpretation)


def test_structured_renderer_outputs_observation_interaction_tradeoff_and_limit():
    result_payload = payload(curve("Curve 1"), improved_off_degraded_drive_candidate(length=1200, tox=22))
    response = render_iv_explanation(result_payload.to_dict())
    text = " ".join(sum(response.values(), []))
    assert "Off-state 측면" in text and "Drive 측면" in text
    assert "같은 감소 방향" in text
    assert "off-state control이 개선됐지만 drive performance는 저하" in text
    assert response["tradeoffs"] and "Trade-off" in response["tradeoffs"][0]
    assert "각각 추가해 비교해야 합니다" in text
    assert "더 많이 일치" not in text
    assert sum(map(len, response.values())) <= result_payload.output_policy["max_total_sentences"]


def test_compound_pair_separates_observation_general_effect_and_followup_design():
    result_payload = payload(
        curve("Curve 1", length=700, tox=15),
        improved_off_degraded_drive_candidate(length=300, tox=10),
    )
    response = render_iv_explanation(result_payload.to_dict())
    text = " ".join(sum(response.values(), []))
    assert result_payload.comparison_plan["analysis_mode"] == "compound_pair"
    assert "Channel length" in text and "Oxide thickness(Tox)" in text
    assert "Source-side 장벽" in text
    assert "Gate control" in text
    assert "이번 모델에서는" in text
    assert "현재 비교만으로 분리해 단정할 수 없습니다" in text
    assert "Channel length만 300 nm로 바꾼 조건" in text
    assert "Oxide thickness(Tox)만 10 nm로 바꾼 조건" in text


def test_vth_uses_absolute_voltage_shift_and_bulk_depletion_mechanism():
    baseline = curve(
        "Curve 1", bulk=1e16, ion=10, gm=5,
    )
    candidate = curve(
        "Curve 2", bulk=5e16, ion=6.4, gm=4.4,
    )
    baseline["electrical_parameters"]["vth_low_v"]["value"] = .09
    candidate["electrical_parameters"]["vth_low_v"]["value"] = .39
    baseline["electrical_parameters"]["vth_high_v"]["value"] = .12
    candidate["electrical_parameters"]["vth_high_v"]["value"] = .23
    result = render_iv_explanation(payload(baseline, candidate).to_dict())
    text = " ".join(sum(result.values(), []))
    assert "Vth(Vd=0.05 V) 0.09 V→0.39 V (0.3 V 증가)" in text
    assert "333.3%" not in text
    assert "이온화 불순물 전하" in text
    assert "반전을 형성하기 전에 Gate가 담당해야 하는 전하" in text
    assert "drive 변화" in text
    assert "drive·saturation" not in text
    assert "saturation 변화" not in text


def test_saturation_observation_requires_saturation_evidence():
    baseline = curve("Curve 1", length=700, gds=.1, clm=.05)
    candidate = curve("Curve 2", length=300, gds=.22, clm=.13)
    # Keep switching and drive metrics unchanged so the observation location
    # must be supported by gds/lambda rather than inherited from drive.
    response = render_iv_explanation(payload(baseline, candidate).to_dict())
    text = " ".join(sum(response.values(), []))
    assert "saturation 변화" in text
    assert "Id-Vd 고전압 구간의 잔류 기울기" in text
    assert "drive·saturation" not in text


def test_no_meaningful_doping_change_is_not_rendered_as_analysis_failure():
    candidate = curve("Curve 2", bulk=2e16, sd=2e20, ldd=2e18)
    response = render_iv_explanation(payload(curve("Curve 1"), candidate).to_dict())
    text = " ".join(sum(response.values(), []))
    assert "뚜렷한 차이를 보이지 않았습니다" in text
    assert "충분히 확보하지 못했습니다" not in text


def test_three_curve_renderer_prioritizes_baseline_variants_and_rankings():
    third = improved_off_degraded_drive_candidate(length=1200, tox=17, ion=7, ioff=.0001, ratio=70000, gm=3, ron=2)
    third["label"] = "Curve 3"
    result_payload = payload_many([
        curve("Curve 1"),
        improved_off_degraded_drive_candidate(length=1200, tox=22),
        third,
    ])
    assert result_payload.interpretation["variant_rankings"]
    response = render_iv_explanation(result_payload.to_dict())
    text = " ".join(response["comparisons"])
    assert "Curve 1 대비 Curve 2" in text and "Curve 1 대비 Curve 3" in text, response
    assert any("개선 폭" in line or "손실" in line for line in response["comparisons"])
    assert len(response["comparisons"]) <= result_payload.output_policy["max_comparisons"]


def test_controlled_sweep_is_sorted_and_rendered_as_metric_trends():
    middle = curve(
        "Curve 3", length=500, ion=12, ioff=.01, ratio=1200,
        dibl=.2, ss=80, gm=4, ron=2, gds=.15, clm=.075,
    )
    result_payload = payload_many([
        curve(
            "Curve 1", length=700, ion=8, ioff=.001, ratio=8000,
            dibl=.1, ss=70, gm=3, ron=3, gds=.1, clm=.05,
        ),
        curve(
            "Curve 2", length=300, ion=16, ioff=.1, ratio=160,
            dibl=.4, ss=90, gm=5, ron=1, gds=.2, clm=.1,
        ),
        middle,
    ])
    response = render_iv_explanation(result_payload.to_dict())
    text = " ".join(sum(response.values(), []))
    assert result_payload.comparison_plan["analysis_mode"] == "controlled_sweep"
    assert "300 nm (Curve 2) → 500 nm (Curve 3) → 700 nm (Curve 1)" in text
    assert "DIBL: 지속 감소" in text
    assert "Ioff: 지속 감소" in text
    assert "Ion: 지속 감소" in text
    assert "Ron: 지속 증가" in text
    assert "Sweep 방향" in text and "Trade-off" in text
    assert "지점 사이 또는 범위 밖" in text


def test_controlled_sweep_marks_non_monotonic_metric():
    result_payload = payload_many([
        curve("Curve 1", length=700, ion=8),
        curve("Curve 2", length=300, ion=16),
        curve("Curve 3", length=500, ion=18),
    ])
    text = " ".join(sum(render_iv_explanation(result_payload.to_dict()).values(), []))
    assert "Ion: 중간 조건에서 방향이 바뀌는 비단조 변화" in text
    assert "endpoint만으로 중간 조건을 추정하지 말고" in text


def test_mixed_group_prioritizes_controlled_edges_and_limits_compound_claims():
    result_payload = payload_many([
        curve("Curve 1", length=700, tox=20, ion=8, ioff=.001, dibl=.1),
        curve("Curve 2", length=300, tox=20, ion=14, ioff=.05, dibl=.35),
        curve("Curve 3", length=700, tox=10, ion=12, ioff=.0008, dibl=.08),
        curve("Curve 4", length=300, tox=10, ion=20, ioff=.03, dibl=.28),
    ])
    response = render_iv_explanation(result_payload.to_dict())
    text = " ".join(sum(response.values(), []))
    assert result_payload.comparison_plan["analysis_mode"] == "mixed_group"
    assert "controlled pair를 우선 분석" in text
    assert "Curve 1 대비 Curve 2에서는 Channel length만" in text
    assert "Curve 1 대비 Curve 3에서는 Oxide thickness(Tox)만" in text
    assert "Curve 2 대비 Curve 4에서는 Oxide thickness(Tox)만" in text
    assert "Curve 3 대비 Curve 4에서는 Channel length만" in text
    assert "개별 변수의 기여도 산정이나 원인 귀속에 사용하지 않았습니다" in text
    assert "개별 parameter의 원인 순위는 아닙니다" in text
    assert len(response["comparisons"]) <= result_payload.output_policy["max_comparisons"]
