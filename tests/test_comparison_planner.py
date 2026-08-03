from __future__ import annotations

from backend.explanation.comparison_planner import build_comparison_plan


def subject(
    index: int,
    *,
    length: float = 700.0,
    oxide: float = 10.0,
    body: float = 1e16,
) -> dict:
    return {
        "subject_id": f"curve_{index}",
        "display_name": f"Curve {index}",
        "device_parameters": {
            "channel_length_nm": length,
            "oxide_thickness_nm": oxide,
            "bulk_doping_cm3": body,
            "source_drain_doping_cm3": 1e20,
            "ldd_doping_cm3": 1e18,
        },
    }


def test_single_subject_builds_characterization_plan() -> None:
    plan = build_comparison_plan([subject(1)])
    assert plan.analysis_mode == "single_characterization"
    assert plan.baseline_subject_id is None
    assert plan.allowed_claim_level == "descriptive_only"
    assert plan.selected_comparison_ids == ()


def test_two_subjects_distinguish_controlled_and_compound_pairs() -> None:
    controlled = build_comparison_plan([
        subject(1, length=700),
        subject(2, length=300),
    ])
    assert controlled.analysis_mode == "controlled_pair"
    assert controlled.controlled_pair_ids == ("cmp_1_2",)
    assert controlled.compound_pair_ids == ()
    assert controlled.allowed_claim_level == "controlled_association"

    compound = build_comparison_plan([
        subject(1, length=700, oxide=20),
        subject(2, length=300, oxide=10),
    ])
    assert compound.analysis_mode == "compound_pair"
    assert compound.compound_pair_ids == ("cmp_1_2",)
    assert set(compound.changed_parameters) == {
        "channel_length",
        "oxide_thickness",
    }
    assert compound.allowed_claim_level == "multi_parameter_association"


def test_three_lengths_build_sorted_controlled_sweep() -> None:
    plan = build_comparison_plan([
        subject(1, length=700),
        subject(2, length=300),
        subject(3, length=500),
    ])
    assert plan.analysis_mode == "controlled_sweep"
    assert plan.sweep_parameter == "channel_length"
    assert plan.sweep_subject_ids == ("curve_2", "curve_3", "curve_1")
    assert plan.sweep_values == (300.0, 500.0, 700.0)
    assert plan.sweep_order == "selected_order"
    assert plan.controlled_pair_ids == ("cmp_1_2", "cmp_1_3", "cmp_2_3")
    assert plan.representative_subject_ids == ("curve_2", "curve_1")


def test_mixed_group_prioritizes_controlled_edges() -> None:
    plan = build_comparison_plan([
        subject(1, length=700, oxide=20),
        subject(2, length=300, oxide=20),
        subject(3, length=700, oxide=10),
        subject(4, length=300, oxide=10),
    ])
    assert plan.analysis_mode == "mixed_group"
    assert plan.controlled_pair_ids == (
        "cmp_1_2",
        "cmp_1_3",
        "cmp_2_4",
        "cmp_3_4",
    )
    assert plan.compound_pair_ids == ("cmp_1_4", "cmp_2_3")
    assert plan.selected_comparison_ids == plan.controlled_pair_ids
    assert plan.allowed_claim_level == "comparison_specific"
    assert plan.representative_subject_ids == ("curve_1", "curve_2")


def test_invalid_preferred_baseline_falls_back_and_requests_clarification() -> None:
    plan = build_comparison_plan(
        [subject(1), subject(2, length=300)],
        preferred_baseline_id="curve_99",
    )
    assert plan.baseline_subject_id == "curve_1"
    assert plan.requires_clarification
    assert plan.clarification_reason == "requested_baseline_not_found"
