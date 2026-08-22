from __future__ import annotations

from backend.learning import LearningLLMService, load_topic
from backend.learning.analysis_schemas import (
    ElectricalChange,
    LearningAnalysisContext,
    LearningObservation,
)
from backend.learning.model_answer import build_grounded_model_answer
from frontend.visualization.case_study.panel import (
    CASE_CORE_SUMMARIES,
    CASE_UNDERSTANDING_GUIDES,
    QUESTION_REVIEW_GUIDES,
)


def _change(
    before: float,
    after: float,
    direction: str,
    unit: str,
    evidence_id: str,
) -> ElectricalChange:
    return ElectricalChange(
        before=before,
        after=after,
        difference=after - before,
        change_percent=((after - before) / before * 100.0),
        change_ratio=after / before,
        direction=direction,
        unit=unit,
        available=True,
        evidence_id=evidence_id,
    )


def _source_drain_context() -> LearningAnalysisContext:
    return LearningAnalysisContext(
        experiment={
            "changed_parameter": "SD",
            "changed_parameters": ["SD"],
            "before": 1e19,
            "after": 1e20,
            "baseline_conditions": {
                "L": 700.0,
                "T": 20.0,
                "B": 1e16,
                "SD": 1e19,
                "LDD": 1e18,
            },
            "comparison_conditions": {
                "L": 700.0,
                "T": 20.0,
                "B": 1e16,
                "SD": 1e20,
                "LDD": 1e18,
            },
            "fixed_parameters": {
                "L": 700.0,
                "T": 20.0,
                "B": 1e16,
                "LDD": 1e18,
            },
        },
        electrical_changes={
            "ion": _change(
                2.97390, 3.06334, "increase", "mA/um", "metric:ion"
            ),
            "ron": _change(
                0.53620, 0.52014, "decrease", "kohm um", "metric:ron"
            ),
            "dibl": _change(
                23.1314, 24.8276, "increase", "mV/V", "metric:dibl"
            ),
            "gds": _change(
                0.08215, 0.08602, "increase", "mS/um", "metric:gds"
            ),
        },
        field_observations=(
            LearningObservation(
                source="field",
                evidence_id="sd_drain_potential_change",
                quantity="potential",
                observation="increase",
                confidence="high",
                field_display="potential",
                region="drain_side_ldd_near_surface",
            ),
            LearningObservation(
                source="field",
                evidence_id="sd_drain_field_change",
                quantity="electric_field",
                observation="increase",
                confidence="high",
                field_display="electric_field",
                region="drain_side_ldd_near_surface",
            ),
        ),
        in_training_range=True,
        analysis_status="partial",
    )


def test_source_drain_case_has_three_predictions_and_three_observations() -> None:
    topic = load_topic("source_drain_on_state_conduction")

    assert [question.question_id for question in topic.prediction_questions] == [
        "sd_pred_ion",
        "sd_pred_ron",
        "sd_pred_dibl",
    ]
    assert [question.question_id for question in topic.observation_questions] == [
        "sd_obs_iv_conduction",
        "sd_obs_iv_tradeoff",
        "sd_obs_field_evidence",
    ]
    assert all(question.reason_required for question in topic.prediction_questions)
    assert all(question.reason_required for question in topic.observation_questions)
    assert topic.observation_questions[0].correct_options == (
        "Ion 증가",
        "Ron 감소",
    )
    assert "DIBL은 Drain bias" in topic.observation_questions[1].correct_options[0]
    assert "gds는 포화영역" in topic.observation_questions[1].correct_options[0]
    assert "Drain 인접 분포" in topic.observation_questions[2].correct_options[0]
    assert "on-state I–V" in topic.observation_questions[2].correct_options[0]


def test_source_drain_case_ui_content_covers_the_full_learning_flow() -> None:
    topic_id = "source_drain_on_state_conduction"
    question_ids = {
        "sd_pred_ion",
        "sd_pred_ron",
        "sd_pred_dibl",
        "sd_obs_iv_conduction",
        "sd_obs_iv_tradeoff",
        "sd_obs_field_evidence",
    }

    assert CASE_UNDERSTANDING_GUIDES[topic_id]["question"].endswith("?")
    assert len(CASE_UNDERSTANDING_GUIDES[topic_id]["evidence"]) == 3
    assert len(CASE_CORE_SUMMARIES[topic_id]) == 3
    assert question_ids <= set(QUESTION_REVIEW_GUIDES)
    assert QUESTION_REVIEW_GUIDES["sd_obs_iv_conduction"]["metric_keys"] == (
        "ion",
        "ron",
    )
    assert QUESTION_REVIEW_GUIDES["sd_obs_iv_tradeoff"]["metric_keys"] == (
        "ion",
        "ron",
        "dibl",
        "gds",
    )


def test_source_drain_case_model_answer_is_grounded_in_curve_and_field() -> None:
    answer = build_grounded_model_answer(
        load_topic("source_drain_on_state_conduction"),
        _source_drain_context(),
    )

    assert "Source/Drain doping은" in answer
    assert "Ion:" in answer
    assert "Ron:" in answer
    assert "DIBL:" in answer
    assert "gds:" in answer
    assert "접촉저항만이 아니라" in answer
    assert "Drain-side LDD 표면 부근의 전위" in answer
    assert "Drain bias의 Channel 장벽 영향" in answer
    assert "포화영역 출력 저항 감소" in answer


def test_source_drain_case_tutor_uses_case_result_and_theory() -> None:
    result = LearningLLMService().ask_followup(
        load_topic("source_drain_on_state_conduction"),
        "이번 결과에서 Source/Drain doping을 높였더니 Ion과 DIBL이 왜 함께 증가했나요?",
        _source_drain_context(),
    )

    assert result.question_type == "current_result"
    assert result.uses_current_result
    assert {"metric:ion", "metric:dibl"} <= set(result.evidence_ids)
    assert {"source_drain_doping", "on_current", "dibl"} <= set(
        result.theory_concepts
    )
