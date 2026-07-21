from __future__ import annotations

from types import SimpleNamespace

from backend.explanation.field_conclusions import (
    build_field_specific_conclusions,
    validate_field_specific_conclusions,
)


CASES = (
    ("potential", "contour_spacing_change", "widened", "channel_near_surface", "potential_gradient", "weakened"),
    ("electric_field", "hotspot_strength_change", "strengthened", "drain_side_ldd_near_surface", "field_concentration", "strengthened"),
    ("electron_density", "distribution_width_change", "widened", "channel_near_surface", "inversion_layer", "expanded"),
    ("hole_density", "distribution_width_change", "widened", "deep_bulk", "depletion_region", "expanded"),
    ("electron_current_density", "path_connectivity_change", "disconnected", "channel_near_surface", "current_path", "less_continuous"),
    ("total_current_density", "crowding_change", "strengthened", "drain_side_ldd_near_surface", "current_crowding", "strengthened"),
    ("srh_recombination", "hotspot_strength_change", "strengthened", "drain_near_surface", "srh_activity_magnitude", "strengthened"),
    ("energy_band", "barrier_or_band_change", "raised", "channel_near_surface", "channel_entry_barrier", "raised"),
)


def _payload(display: str, evidence_type: str, observation: str, region: str):
    evidence = [{
        "evidence_id": "ev_1", "evidence_type": evidence_type, "field_display": display,
        "observation": observation, "region": region, "subject_ids": ["curve_1", "curve_2"],
        "comparison_id": "cmp_1_2", "eligible_for_output": True, "confidence": "high",
        "magnitude_class": "major", "importance_score": 0.8,
    }]
    features = [{
        "feature_id": "fsf_1", "feature": "regional_change", "region": region,
        "baseline_subject_id": "curve_1", "candidate_subject_id": "curve_2",
    }]
    return SimpleNamespace(
        context={"display": display}, evidence=evidence,
        comparisons=[{"comparison_id": "cmp_1_2", "changed_parameter_count": 2}],
        interpretation={"spatial_features": features},
    )


def test_every_field_policy_produces_only_its_allowed_concept() -> None:
    for display, evidence_type, observation, region, concept, assessment in CASES:
        payload = _payload(display, evidence_type, observation, region)
        conclusions = build_field_specific_conclusions(payload)
        assert len(conclusions) == 1
        assert conclusions[0]["concept"] == concept
        assert conclusions[0]["assessment"] == assessment
        assert conclusions[0]["spatial_feature_ids"] == ["fsf_1"]
        validate_field_specific_conclusions(conclusions, payload)


def test_field_conclusion_never_assigns_parameter_causality() -> None:
    payload = _payload("electric_field", "hotspot_strength_change", "weakened", "drain_side_ldd_near_surface")
    conclusion = build_field_specific_conclusions(payload)[0]
    assert conclusion["causal_attribution"] == "not_assigned"
    assert conclusion["parameter_attribution_limit"] == "multiple_parameters_changed"
    assert conclusion["claim_limit"] == "spatial_prediction_only"


def test_srh_magnitude_does_not_infer_recombination_or_generation_sign() -> None:
    payload = _payload("srh_recombination", "hotspot_strength_change", "strengthened", "drain_near_surface")
    conclusion = build_field_specific_conclusions(payload)[0]
    assert conclusion["concept"] == "srh_activity_magnitude"
    assert "recombination_dominant" not in conclusion.values()
    assert "generation_dominant" not in conclusion.values()


def test_unsupported_evidence_cannot_create_a_conclusion() -> None:
    payload = _payload("potential", "hotspot_strength_change", "strengthened", "channel_near_surface")
    assert build_field_specific_conclusions(payload) == []
