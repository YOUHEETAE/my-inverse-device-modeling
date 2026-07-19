import json

from ai.result_interpreter.relationships import build_analysis_conclusions


def comparison(*parameters):
    changes = [{"parameter": name, "direction": direction} for name, direction in parameters]
    return {"comparison_id": "cmp_1_2", "baseline_subject_id": "curve_1", "candidate_subject_id": "curve_2",
            "changed_parameter_count": len(changes), "changed_parameters": changes,
            "causal_claim_level": "controlled_association"}


def evidence(evidence_id, quantity, observation, *, source="curve_parameter_analyzer", magnitude="major", confidence="high", eligible=True, region=None):
    return {"evidence_id": evidence_id, "evidence_type": "metric_change" if source == "curve_parameter_analyzer" else "hotspot_strength_change",
            "source_type": source, "comparison_id": "cmp_1_2", "quantity": quantity, "observation": observation,
            "magnitude_class": magnitude, "confidence": confidence, "importance_score": .8, "eligible_for_output": eligible,
            "suppression_reasons": [] if eligible else ["low_confidence"], "region": region}


def conclusions_for(cmp, items, warnings=()):
    conclusions = build_analysis_conclusions([cmp], items, list(warnings))
    return conclusions, cmp


def find(items, conclusion_type, principle_id=None):
    return next(item for item in items if item["conclusion_type"] == conclusion_type and (principle_id is None or item.get("principle_id") == principle_id))


def test_single_analysis_has_no_relationship():
    conclusions = build_analysis_conclusions([], [], [])
    assert conclusions == []


def test_channel_length_dibl_supports_sce():
    items, cmp = conclusions_for(comparison(("channel_length", "increased")), [evidence("ev_dibl", "dibl", "decreased")])
    relationship = find(items, "physical_relationship", "channel_length_increase_reduces_sce")
    assert relationship["physical_consistency"] == "consistent" and relationship["supporting_evidence_ids"] == ["ev_dibl"]
    assert cmp["declared_claim_level"] == cmp["effective_claim_level"] == "controlled_association"


def test_two_curve_metrics_do_not_force_cross_validation():
    ev = [evidence("ev_dibl", "dibl", "decreased"), evidence("ev_ioff", "ioff", "decreased")]
    items, cmp = conclusions_for(comparison(("channel_length", "increased")), ev)
    assert not any(item["conclusion_type"] == "cross_validated_physical_trend" for item in items)
    assert cmp["effective_claim_level"] == "controlled_association"


def test_curve_and_field_support_cross_validation():
    ev = [evidence("ev_dibl", "dibl", "decreased"),
          evidence("ev_field", "electric_field_magnitude", "weakened", source="field_spatial_analyzer", region="drain_side_ldd_near_surface")]
    items, cmp = conclusions_for(comparison(("channel_length", "increased")), ev)
    cross = find(items, "cross_validated_physical_trend")
    assert cross["supporting_evidence_ids"] == ["ev_dibl", "ev_field"]
    assert cmp["effective_claim_level"] == "cross_validated_controlled_association"


def test_conflicting_field_blocks_cross_validation():
    ev = [evidence("ev_dibl", "dibl", "decreased"),
          evidence("ev_field", "electric_field_magnitude", "strengthened", source="field_spatial_analyzer", region="drain_side_ldd_near_surface")]
    items, cmp = conclusions_for(comparison(("channel_length", "increased")), ev)
    relationship = find(items, "physical_relationship", "channel_length_increase_reduces_sce")
    assert relationship["physical_consistency"] == "partially_consistent"
    assert find(items, "conflicting_physical_evidence")
    assert not any(item["conclusion_type"] == "cross_validated_physical_trend" for item in items)


def test_tox_decrease_gm_decrease_is_inconsistent():
    items, _cmp = conclusions_for(comparison(("oxide_thickness", "decreased")), [evidence("ev_gm", "gm_max", "decreased")])
    relationship = find(items, "physical_relationship", "oxide_thickness_decrease_strengthens_gate_control")
    assert relationship["physical_consistency"] == "inconsistent" and relationship["contradicting_evidence_ids"] == ["ev_gm"]


def test_multiple_parameters_have_association_only():
    items, cmp = conclusions_for(comparison(("channel_length", "increased"), ("oxide_thickness", "decreased")), [evidence("ev_dibl", "dibl", "decreased")])
    assert [item["conclusion_type"] for item in items] == ["multi_parameter_association"]
    assert cmp["effective_claim_level"] == "multi_parameter_association"
    multi = items[0]
    assert [item["parameter"] for item in multi["parameter_effects"]] == ["channel_length", "oxide_thickness"]
    assert multi["dominant_alignment_parameter"] == "channel_length"
    assert multi["parameter_effects"][0]["support_score"] > multi["parameter_effects"][1]["support_score"]
    assert set(multi["competing_quantities"]) == {"electric_field_magnitude", "gm_max", "ion"}


def test_extrapolation_reduces_controlled_claim():
    warning = {"warning_type": "extrapolation", "subject_ids": [], "details": {}}
    items, cmp = conclusions_for(comparison(("channel_length", "increased")), [evidence("ev_dibl", "dibl", "decreased")], [warning])
    assert cmp["declared_claim_level"] == "controlled_association" and cmp["effective_claim_level"] == "descriptive_only"
    assert "extrapolation" in cmp["claim_reduction_reasons"]
    assert not any(item["conclusion_type"] == "cross_validated_physical_trend" for item in items)


def test_low_confidence_is_insufficient():
    ev = evidence("ev_dibl", "dibl", "decreased", confidence="low", eligible=False)
    items, cmp = conclusions_for(comparison(("channel_length", "increased")), [ev])
    relationship = find(items, "physical_relationship", "channel_length_increase_reduces_sce")
    assert relationship["physical_consistency"] == "insufficient_evidence" and cmp["effective_claim_level"] == "descriptive_only"


def test_all_negligible_builds_no_difference():
    ev = evidence("ev_dibl", "dibl", "unchanged", magnitude="negligible", eligible=False)
    ev["suppression_reasons"] = ["negligible_change"]
    items, cmp = conclusions_for(comparison(("channel_length", "increased")), [ev])
    assert find(items, "no_meaningful_difference") and cmp["effective_claim_level"] == "descriptive_only"


def test_energy_band_alone_does_not_cross_validate():
    ev = evidence("ev_band", "channel_entry_barrier", "raised", source="energy_band_analyzer", confidence="medium")
    ev["evidence_type"] = "barrier_or_band_change"
    items, cmp = conclusions_for(comparison(("channel_length", "increased")), [ev])
    assert not any(item["conclusion_type"] == "cross_validated_physical_trend" for item in items)
    assert "model_derived_approximation" in cmp["claim_reduction_reasons"]


def test_bulk_doping_is_context_dependent():
    items, _cmp = conclusions_for(comparison(("bulk_doping", "increased")), [evidence("ev_vth", "vth_at_vd_0_05", "increased")])
    relationship = find(items, "physical_relationship", "bulk_doping_change_modifies_threshold_behavior")
    assert relationship["physical_consistency"] == "not_evaluated"


def test_conclusions_are_strict_json():
    items, cmp = conclusions_for(comparison(("channel_length", "increased")), [evidence("ev_dibl", "dibl", "decreased")])
    json.dumps({"comparison": cmp, "conclusions": items}, allow_nan=False)
