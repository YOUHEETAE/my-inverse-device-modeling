import json

from ai.result_interpreter.iv_renderer import render_iv_explanation, validate_explanation_response


POLICY = {"max_total_sentences": 7, "max_descriptions": 2, "max_comparisons": 3, "max_tradeoffs": 1, "max_cautions": 1,
          "minimum_importance_score": .35, "include_general_physical_principle": True, "include_model_limitation": True}


def metric(eid, quantity, *, comparison_id=None, observation="measured_value", value=1.0, percent=None, decade=None,
           assessment="not_applicable", importance=.8, eligible=True, unit="V"):
    return {"evidence_id": eid, "evidence_type": "metric_value" if comparison_id is None else "metric_change",
            "source_type": "curve_parameter_analyzer", "subject_ids": ["curve_1"] if comparison_id is None else ["curve_1", "curve_2"],
            "comparison_id": comparison_id, "quantity": quantity, "observation": observation,
            "data": {"value": value, "unit": unit, "percent_difference": percent, "decade_difference": decade},
            "magnitude_class": "major", "confidence": "high", "importance_score": importance, "assessment": assessment,
            "eligible_for_output": eligible, "suppression_reasons": [], "numeric_display": {"allowed": True, "preferred_fields": ["value", "percent_difference"]}}


def subject(index):
    return {"subject_id": f"curve_{index}", "display_name": f"Curve {index}"}


def comparison(cid="cmp_1_2", *, count=1, parameter="channel_length", direction="increased", order=1, role="primary_baseline_to_variant", effective="controlled_association"):
    i, j = cid.removeprefix("cmp_").split("_")
    changes = [] if count == 0 else [{"parameter": parameter, "direction": direction, "baseline": 100.0, "candidate": 200.0, "unit": "nm"}]
    if count > 1: changes.append({"parameter": "oxide_thickness", "direction": "decreased", "baseline": 5.0, "candidate": 3.0, "unit": "nm"})
    return {"comparison_id": cid, "baseline_subject_id": f"curve_{i}", "candidate_subject_id": f"curve_{j}", "comparison_order": order,
            "comparison_role": role, "changed_parameter_count": count, "changed_parameters": changes, "effective_claim_level": effective}


def relationship(cid="cmp_1_2", *, principle="channel_length_increase_reduces_sce", consistency="consistent", concept="short_channel_control"):
    return {"conclusion_type": "physical_relationship", "comparison_id": cid, "principle_id": principle, "physical_consistency": consistency,
            "target_concept": concept, "importance_score": .8, "eligible_for_output": True}


def payload(*, subjects=None, comparisons=None, evidence=None, conclusions=None, warnings=None, policy=None, analysis_type="iv_curve_comparison"):
    return {"analysis_type": analysis_type, "subjects": subjects or [], "comparisons": comparisons or [], "evidence": evidence or [],
            "conclusions": conclusions or [], "warnings": warnings or [], "output_policy": dict(POLICY if policy is None else policy)}


def all_text(response): return " ".join(sum(response.values(), []))


def test_01_single_curve_schema_and_limit():
    p = payload(analysis_type="iv_curve_single", subjects=[subject(1)], evidence=[metric("vth", "vth_at_vd_0_05", value=.61), metric("ion", "ion", value=1.2, unit="mA/um")])
    p["output_policy"].update(max_descriptions=4, max_comparisons=0, max_tradeoffs=0, max_cautions=2, max_total_sentences=6)
    result = render_iv_explanation(p)
    assert set(result) == {"descriptions", "comparisons", "tradeoffs", "cautions"} and not result["comparisons"]
    assert "개선되었습니다" not in all_text(result) and "우수합니다" not in all_text(result) and "TCAD" in all_text(result)


def test_02_single_invalid_metric_is_excluded():
    p = payload(analysis_type="iv_curve_single", subjects=[subject(1)], evidence=[metric("ion", "ion")],
                warnings=[{"warning_type": "parameter_extraction_failed", "eligible_for_output": True}])
    p["output_policy"].update(max_descriptions=4, max_comparisons=0, max_tradeoffs=0, max_cautions=2)
    result = render_iv_explanation(p); assert "추출" in all_text(result) and "Ion" in all_text(result)


def test_03_channel_length_controlled():
    ev = [metric("dibl", "dibl", comparison_id="cmp_1_2", observation="decreased", percent=-24.3), metric("ion", "ion", comparison_id="cmp_1_2", observation="decreased", percent=-13.8)]
    result = render_iv_explanation(payload(subjects=[subject(1), subject(2)], comparisons=[comparison()], evidence=ev, conclusions=[relationship()]))
    text = all_text(result); assert "Channel length" in text and "short-channel effect" in text and "DIBL" in text and "Ion" in text


def test_04_tox_gate_control():
    cmp = comparison(parameter="oxide_thickness", direction="decreased"); ev = [metric("gm", "gm_max", comparison_id="cmp_1_2", observation="increased", percent=12), metric("ss", "ss", comparison_id="cmp_1_2", observation="decreased", percent=-9)]
    rel = relationship(principle="oxide_thickness_decrease_strengthens_gate_control", concept="gate_control")
    text = all_text(render_iv_explanation(payload(subjects=[subject(1), subject(2)], comparisons=[cmp], evidence=ev, conclusions=[rel])))
    assert "Gate control" in text and "gm max" in text and "SS" in text and "증명" not in text


def test_05_multiple_parameter_caution():
    cmp = comparison(count=2, effective="multi_parameter_association"); ev = [metric("ion", "ion", comparison_id="cmp_1_2", observation="increased", percent=10)]
    text = all_text(render_iv_explanation(payload(subjects=[subject(1), subject(2)], comparisons=[cmp], evidence=ev)))
    assert "함께 변경" in text and "분리해 단정할 수 없습니다" in text


def test_06_same_condition_no_difference():
    cmp = comparison(count=0, effective="descriptive_only"); conclusion = {"conclusion_type": "no_meaningful_difference", "comparison_id": "cmp_1_2"}
    text = all_text(render_iv_explanation(payload(subjects=[subject(1), subject(2)], comparisons=[cmp], conclusions=[conclusion])))
    assert "조건은 동일" in text and "유사하게" in text and "원인" not in text


def test_07_three_curve_order():
    comparisons = [comparison("cmp_1_2", order=1), comparison("cmp_1_3", order=2), comparison("cmp_2_3", order=3, role="variant_to_variant", count=2, effective="multi_parameter_association")]
    ev = [metric("a", "ion", comparison_id=cid, observation="decreased", percent=-10) for cid in ("cmp_1_2", "cmp_1_3", "cmp_2_3")]
    result = render_iv_explanation(payload(subjects=[subject(1), subject(2), subject(3)], comparisons=comparisons, evidence=ev))
    assert ["Curve 1 대비 Curve 2", "Curve 1 대비 Curve 3", "Curve 2 대비 Curve 3"] == [line.split("에서는")[0] for line in result["comparisons"]]


def test_08_variant_effect_requires_conclusion():
    cmp = comparison(); ev = [metric("ion", "ion", comparison_id="cmp_1_2", observation="increased", percent=10)]
    base = payload(subjects=[subject(1), subject(2)], comparisons=[cmp], evidence=ev)
    assert "더 크게" not in all_text(render_iv_explanation(base))
    base["conclusions"] = [{"conclusion_type": "variant_effect_comparison", "quantity": "ion", "larger_effect_comparison_id": "cmp_1_2", "eligible_for_output": True}]
    assert "더 크게" in all_text(render_iv_explanation(base))


def test_09_ioff_decade_display():
    ev = [metric("ioff", "ioff", comparison_id="cmp_1_2", observation="decreased", percent=-90, decade=-1, assessment="improved")]
    assert "1.0 decade 감소" in all_text(render_iv_explanation(payload(subjects=[subject(1), subject(2)], comparisons=[comparison()], evidence=ev)))


def test_10_vth_context_dependent():
    ev = [metric("vth", "vth_at_vd_0_05", comparison_id="cmp_1_2", observation="increased", percent=10, assessment="neutral_or_context_dependent")]
    text = all_text(render_iv_explanation(payload(subjects=[subject(1), subject(2)], comparisons=[comparison()], evidence=ev)))
    assert "Vth" in text and "개선" not in text


def test_11_saturation_metrics_are_merged():
    ev = [metric("gds", "gds", comparison_id="cmp_1_2", observation="decreased", percent=-10), metric("lambda", "lambda_clm", comparison_id="cmp_1_2", observation="decreased", percent=-12)]
    result = render_iv_explanation(payload(subjects=[subject(1), subject(2)], comparisons=[comparison()], evidence=ev))
    assert sum("gds" in line or "lambda" in line for line in result["comparisons"]) == 1


def test_12_inconsistency_is_visible():
    ev = [metric("gm", "gm_max", comparison_id="cmp_1_2", observation="decreased", percent=-10)]
    rel = relationship(principle="oxide_thickness_decrease_strengthens_gate_control", consistency="inconsistent", concept="gate_control")
    result = render_iv_explanation(payload(subjects=[subject(1), subject(2)], comparisons=[comparison(parameter="oxide_thickness", direction="decreased")], evidence=ev, conclusions=[rel]))
    assert "기대 방향과 다르게" in all_text(result) and "교차" not in all_text(result)


def test_13_conflict_is_not_full_improvement():
    ev = [metric("dibl", "dibl", comparison_id="cmp_1_2", observation="decreased", percent=-10), metric("ss", "ss", comparison_id="cmp_1_2", observation="increased", percent=10)]
    rel = relationship(consistency="partially_consistent")
    text = all_text(render_iv_explanation(payload(subjects=[subject(1), subject(2)], comparisons=[comparison()], evidence=ev, conclusions=[rel])))
    assert "부분적으로만 일치" in text and "DIBL" in text and "SS" in text


def test_14_extrapolation_caution():
    ev = [metric("dibl", "dibl", comparison_id="cmp_1_2", observation="decreased", percent=-10)]
    warning = {"warning_type": "extrapolation", "eligible_for_output": True}
    text = all_text(render_iv_explanation(payload(subjects=[subject(1), subject(2)], comparisons=[comparison(effective="descriptive_only")], evidence=ev, warnings=[warning])))
    assert "extrapolation" in text and "참고 경향" in text


def test_15_negligible_is_synthesized_only():
    cmp = comparison(effective="descriptive_only"); conclusion = {"conclusion_type": "no_meaningful_difference", "comparison_id": "cmp_1_2"}
    result = render_iv_explanation(payload(subjects=[subject(1), subject(2)], comparisons=[cmp], conclusions=[conclusion]))
    assert len(result["comparisons"]) == 1 and "영향이 없다" not in all_text(result)


def test_16_invalid_payload_falls_back():
    result = render_iv_explanation({"analysis_type": "iv_curve_comparison", "comparisons": [{"bad": True}], "output_policy": POLICY})
    validate_explanation_response(result); assert result["descriptions"] and result["cautions"]


def test_17_output_policy_is_enforced():
    policy = dict(POLICY, max_total_sentences=2, max_descriptions=1, max_comparisons=1, max_tradeoffs=0, max_cautions=1, minimum_importance_score=.9)
    ev = [metric("low", "ion", comparison_id="cmp_1_2", observation="increased", percent=10, importance=.5)]
    result = render_iv_explanation(payload(subjects=[subject(1), subject(2)], comparisons=[comparison()], evidence=ev, policy=policy))
    assert sum(map(len, result.values())) <= 2 and not result["tradeoffs"]


def test_18_forbidden_words_absent():
    ev = [metric("dibl", "dibl", comparison_id="cmp_1_2", observation="decreased", percent=-10)]
    text = all_text(render_iv_explanation(payload(subjects=[subject(1), subject(2)], comparisons=[comparison()], evidence=ev, conclusions=[relationship()])))
    assert not any(word in text for word in ("증명", "입증", "유일한 원인", "반드시 유발", "완전히 최적", "절대적으로 우수"))


def test_strict_json():
    json.dumps(render_iv_explanation(payload()), ensure_ascii=False, allow_nan=False)
