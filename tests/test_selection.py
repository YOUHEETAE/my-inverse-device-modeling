import json

from backend.explanation.selection import (build_mixed_group_conclusions,
    build_tradeoff_conclusions, build_variant_effect_conclusions,
    calculate_evidence_importance, score_and_select_evidence)


def comparison(cid="cmp_1_2", role="primary_baseline_to_variant", changed=1):
    return {"comparison_id": cid, "comparison_role": role, "changed_parameter_count": changed,
            "baseline_subject_id": "curve_1", "candidate_subject_id": cid[-1].join(["curve_", ""]),
            "effective_claim_level": "controlled_association"}


def evidence(eid, quantity, observation, assessment="improved", *, magnitude="major", confidence="high", cid="cmp_1_2", **extra):
    item = {"evidence_id": eid, "evidence_type": "metric_change", "source_type": "curve_parameter_analyzer",
            "subject_ids": ["curve_1", "curve_2"], "comparison_id": cid, "quantity": quantity,
            "observation": observation, "assessment": assessment, "magnitude_class": magnitude,
            "confidence": confidence, "importance_score": 0, "eligible_for_output": True,
            "suppression_reasons": [], "related_evidence_ids": [], "data": {"percent_difference": 20, "unit": "A"}}
    item.update(extra); return item


def test_importance_penalties_duplicate_and_strict_json():
    cmp = comparison(); major = evidence("ion", "ion", "increased")
    low = evidence("low", "ion", "increased", confidence="low")
    duplicate = evidence("dup", "ion", "increased", suppression_reasons=["duplicate_of_higher_priority_evidence"])
    assert calculate_evidence_importance(major, {"cmp_1_2": cmp}, []) > calculate_evidence_importance(low, {"cmp_1_2": cmp}, [])
    assert calculate_evidence_importance(duplicate, {"cmp_1_2": cmp}, []) == 0
    json.dumps({"score": calculate_evidence_importance(major, {"cmp_1_2": cmp}, [])}, allow_nan=False)


def test_quantity_scoped_warning_does_not_suppress_other_metrics():
    cmp = comparison(); ion = evidence("ion", "ion", "increased"); dibl = evidence("dibl", "dibl", "decreased")
    warning = {"warning_type": "parameter_extraction_failed", "subject_ids": ["curve_1", "curve_2"],
               "affected_evidence_ids": [], "affected_quantities": ["dibl"], "affected_regions": []}
    comparison_map = {"cmp_1_2": cmp}
    assert calculate_evidence_importance(ion, comparison_map, [warning]) > 0
    assert calculate_evidence_importance(dibl, comparison_map, [warning]) == 0


def test_group_selection_and_saturation_major_gate():
    items = [evidence("dibl", "dibl", "decreased"), evidence("ioff", "ioff", "decreased"),
             evidence("ss", "ss", "decreased", magnitude="minor"), evidence("ion", "ion", "increased"),
             evidence("gds", "gds", "increased", magnitude="moderate")]
    score_and_select_evidence(items, [comparison()], [])
    selected = {item["evidence_id"] for item in items if item["selected_for_explanation"]}
    assert {"dibl", "ioff", "ion"}.issubset(selected)
    assert "ss" not in selected and "gds" not in selected


def test_tradeoff_and_mixed_behavior_are_distinct():
    items = [evidence("dibl", "dibl", "decreased"), evidence("ion", "ion", "decreased", "degraded")]
    score_and_select_evidence(items, [comparison()], [])
    tradeoffs = build_tradeoff_conclusions([comparison()], items)
    assert tradeoffs[0]["label"] == "short_channel_control_vs_drive_performance"
    mixed_items = [evidence("d", "dibl", "decreased"), evidence("s", "ss", "increased", "degraded")]
    score_and_select_evidence(mixed_items, [comparison()], [])
    assert not build_tradeoff_conclusions([comparison()], mixed_items)
    assert build_mixed_group_conclusions([comparison()], mixed_items)[0]["conclusion_type"] == "mixed_group_behavior"


def test_tradeoff_rejects_low_confidence_and_multiple_parameter_comparison():
    items = [evidence("ion", "ion", "increased"), evidence("ioff", "ioff", "increased", "degraded", confidence="low")]
    score_and_select_evidence(items, [comparison()], [])
    assert not build_tradeoff_conclusions([comparison()], items)
    items[1]["confidence"] = "high"; score_and_select_evidence(items, [comparison(changed=2)], [])
    assert not build_tradeoff_conclusions([comparison(changed=2)], items)


def test_variant_effect_uses_primary_pairs_only_and_requires_separation():
    comparisons = [comparison("cmp_1_2"), comparison("cmp_1_3")]
    a = evidence("a", "ion", "increased", cid="cmp_1_2")
    b = evidence("b", "ion", "increased", cid="cmp_1_3"); b["data"]["percent_difference"] = 40
    score_and_select_evidence([a, b], comparisons, [])
    result = build_variant_effect_conclusions(comparisons, [a, b])
    assert result and result[0]["larger_effect_comparison_id"] == "cmp_1_3"
