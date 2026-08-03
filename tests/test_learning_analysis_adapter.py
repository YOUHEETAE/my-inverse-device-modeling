from __future__ import annotations

import json
import math
from pathlib import Path

from backend.learning import LearningAnalysisAdapter


CONDITIONS = {
    "baseline": {"L": 700, "T": 10, "B": 1e16, "SD": 1e20, "LDD": 1e18},
    "comparison": {"L": 300, "T": 10, "B": 1e16, "SD": 1e20, "LDD": 1e18},
}


def _curve_payload() -> dict:
    return {
        "schema_version": "3.0",
        "context": {"analysis_status": "success"},
        "evidence": [
            {
                "evidence_id": "ev_ion",
                "evidence_type": "metric_change",
                "comparison_id": "cmp_1_2",
                "quantity": "ion",
                "observation": "increased",
                "eligible_for_output": True,
                "data": {
                    "baseline": 1.0,
                    "candidate": 1.5,
                    "absolute_difference": 0.5,
                    "percent_difference": 50.0,
                    "unit": "mA/um",
                },
            },
            {
                "evidence_id": "ev_ioff",
                "evidence_type": "metric_change",
                "comparison_id": "cmp_1_2",
                "quantity": "ioff",
                "observation": "increased",
                "eligible_for_output": True,
                "data": {
                    "baseline": 1e-9,
                    "candidate": 4e-7,
                    "absolute_difference": 3.99e-7,
                    "percent_difference": 39900.0,
                    "unit": "mA/um",
                },
            },
            {
                "evidence_id": "ev_curve_shape",
                "evidence_type": "curve_point_change",
                "comparison_id": "cmp_1_2",
                "quantity": "drain_current",
                "observation": "increased",
                "confidence": "high",
                "eligible_for_output": True,
                "selected_for_explanation": True,
                "numeric_display": {
                    "allowed": True,
                    "preferred_fields": ["percent_difference"],
                },
                "data": {"percent_difference": 42.0, "internal_value": 999.0},
            },
        ],
        "conclusions": [
            {
                "conclusion_id": "tradeoff",
                "conclusion_type": "tradeoff",
                "label": "drive_current_vs_off_state_leakage",
                "positive_target": "drive_current",
                "negative_target": "off_state_leakage",
                "positive_evidence_ids": ["ev_ion"],
                "negative_evidence_ids": ["ev_ioff"],
                "eligible_for_output": True,
            },
            {
                "conclusion_id": "sce",
                "conclusion_type": "controlled_parameter_effect",
                "changed_parameters": ["channel_length"],
                "principle_ids": ["channel_length_decrease_increases_sce"],
                "supporting_evidence_ids": ["ev_ioff"],
                "effective_claim_level": "controlled_single_parameter",
                "eligible_for_output": True,
            }
        ],
        "warnings": [
            {
                "warning_type": "model_approximation",
                "severity": "info",
                "affected_quantities": [],
                "affected_regions": [],
            }
        ],
    }


def _field_payload() -> dict:
    return {
        "schema_version": "3.0",
        "context": {"analysis_status": "success"},
        "evidence": [
            {
                "evidence_id": "field_hotspot",
                "evidence_type": "hotspot_strength_change",
                "field_display": "electric_field",
                "region": "drain_side_ldd_near_surface",
                "quantity": "electric_field_magnitude",
                "observation": "strengthened",
                "confidence": "high",
                "eligible_for_output": True,
                "selected_for_explanation": True,
                "numeric_display": {"allowed": False, "preferred_fields": []},
                "data": {"baseline_internal_value": 123.0, "candidate_internal_value": 456.0},
            }
        ],
        "conclusions": [],
        "warnings": [],
        "interpretation": {
            "field_specific_conclusions": [
                {
                    "conclusion_id": "field_sce",
                    "concept": "drain_field_spread",
                    "assessment": "strengthened",
                    "evidence_ids": ["field_hotspot"],
                    "spatial_feature_ids": ["spatial_1"],
                }
            ]
        },
    }


def test_adapter_normalizes_metrics_observations_and_policy_safe_field_evidence() -> None:
    context = LearningAnalysisAdapter().normalize(
        baseline_conditions=CONDITIONS["baseline"],
        comparison_conditions=CONDITIONS["comparison"],
        curve_analysis=_curve_payload(),
        field_analyses={"electric_field": _field_payload()},
    )
    assert context.experiment["changed_parameter"] == "L"
    assert context.electrical_changes["ion"].direction == "increase"
    assert context.electrical_changes["ion"].change_ratio == 1.5
    assert math.isclose(context.electrical_changes["ioff"].change_ratio, 400.0)
    assert not context.electrical_changes["dibl"].available
    assert context.curve_observations[0].numeric_evidence == {"percent_difference": 42.0}
    assert context.field_observations[0].region == "drain_side_ldd_near_surface"
    assert context.field_observations[0].numeric_evidence == {}
    assert any(item["conclusion_id"] == "field_sce" for item in context.validated_observations)
    tradeoff = next(item for item in context.validated_observations if item["conclusion_id"] == "tradeoff")
    assert tradeoff["supporting_evidence_ids"] == ["ev_ion", "ev_ioff"]
    assert tradeoff["positive_target"] == "drive_current"
    assert context.in_training_range and context.analysis_status == "complete"
    json.dumps(context.to_dict(), allow_nan=False)


def test_adapter_handles_missing_analysis_and_out_of_range_conditions() -> None:
    context = LearningAnalysisAdapter().normalize(
        baseline_conditions={**CONDITIONS["baseline"], "B": 1e17},
        comparison_conditions={**CONDITIONS["comparison"], "B": 1e17},
        curve_analysis=None,
        field_analyses={"potential": None},
    )
    assert not context.in_training_range
    assert context.analysis_status == "insufficient"
    assert all(not item.available for item in context.electrical_changes.values())
    assert context.source_schema_versions == {"curve": "missing", "field:potential": "missing"}


def test_real_sce_fixture_is_strict_and_contains_expected_adapter_contract() -> None:
    path = Path(__file__).parent / "fixtures/learning/sce_channel_length_analysis.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    context = data["learning_context"]
    assert data["topic_id"] == "sce_channel_length"
    assert context["experiment"]["changed_parameter"] == "L"
    assert context["experiment"]["before"] == 700
    assert context["experiment"]["after"] == 300
    assert context["in_training_range"] is True
    assert context["analysis_status"] in {"complete", "partial"}
    assert context["electrical_changes"]["ion"]["available"] is True
    assert context["electrical_changes"]["dibl"]["available"] is True
    assert context["electrical_changes"]["dibl"]["evidence_id"] == "metric:dibl"
    assert set(data["field_analysis_ids"]) == {"potential", "electric_field"}
    json.dumps(data, allow_nan=False)
