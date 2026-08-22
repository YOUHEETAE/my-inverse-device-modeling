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


def _ldd_context() -> LearningAnalysisContext:
    return LearningAnalysisContext(
        experiment={
            "changed_parameter": "LDD",
            "changed_parameters": ["LDD"],
            "before": 5e17,
            "after": 5e18,
            "baseline_conditions": {
                "L": 700.0,
                "T": 20.0,
                "B": 1e16,
                "SD": 1e20,
                "LDD": 5e17,
            },
            "comparison_conditions": {
                "L": 700.0,
                "T": 20.0,
                "B": 1e16,
                "SD": 1e20,
                "LDD": 5e18,
            },
            "fixed_parameters": {
                "L": 700.0,
                "T": 20.0,
                "B": 1e16,
                "SD": 1e20,
            },
        },
        electrical_changes={
            "vth_high": _change(
                0.74355, 0.77881, "increase", "V", "metric:vth_high"
            ),
            "ion": _change(
                2.97952, 3.17858, "increase", "mA/um", "metric:ion"
            ),
            "gm_max": _change(
                0.03972, 0.04271, "increase", "mS/um", "metric:gm_max"
            ),
            "gds": _change(
                0.08243, 0.09614, "increase", "mS/um", "metric:gds"
            ),
            "ron": _change(
                0.53536, 0.49495, "decrease", "kohm um", "metric:ron"
            ),
            "lambda_clm": _change(
                0.09503, 0.10194, "increase", "1/V", "metric:lambda_clm"
            ),
        },
        field_observations=(
            LearningObservation(
                source="field",
                evidence_id="ldd_drain_potential_change",
                quantity="potential",
                observation="increase",
                confidence="high",
                field_display="potential",
                region="drain_near_surface",
            ),
            LearningObservation(
                source="field",
                evidence_id="ldd_drain_field_change",
                quantity="electric_field",
                observation="increase",
                confidence="high",
                field_display="electric_field",
                region="drain_near_surface",
            ),
        ),
        in_training_range=True,
        analysis_status="partial",
    )


def test_ldd_case_has_three_predictions_and_three_observations() -> None:
    topic = load_topic("ldd_field_resistance_tradeoff")

    assert [question.question_id for question in topic.prediction_questions] == [
        "ldd_pred_ion",
        "ldd_pred_ron",
        "ldd_pred_drain_field",
    ]
    assert [question.question_id for question in topic.observation_questions] == [
        "ldd_obs_iv_conduction",
        "ldd_obs_iv_tradeoff",
        "ldd_obs_field_tradeoff",
    ]
    assert all(question.reason_required for question in topic.prediction_questions)
    assert all(question.reason_required for question in topic.observation_questions)
    assert topic.observation_questions[0].correct_options == (
        "Ion 증가",
        "Ron 감소",
    )
    assert "gds는 포화영역" in topic.observation_questions[1].correct_options[0]
    assert "출력 저항 비용" in topic.observation_questions[1].correct_options[0]
    assert "access 경로의 유효 저항" in topic.observation_questions[2].correct_options[0]
    assert "전위 강하를 넓게 분산" in topic.observation_questions[2].correct_options[0]


def test_ldd_case_ui_content_covers_the_full_learning_flow() -> None:
    topic_id = "ldd_field_resistance_tradeoff"
    question_ids = {
        "ldd_pred_ion",
        "ldd_pred_ron",
        "ldd_pred_drain_field",
        "ldd_obs_iv_conduction",
        "ldd_obs_iv_tradeoff",
        "ldd_obs_field_tradeoff",
    }

    assert CASE_UNDERSTANDING_GUIDES[topic_id]["question"].endswith("?")
    assert len(CASE_UNDERSTANDING_GUIDES[topic_id]["evidence"]) == 3
    assert len(CASE_CORE_SUMMARIES[topic_id]) == 3
    assert question_ids <= set(QUESTION_REVIEW_GUIDES)
    assert QUESTION_REVIEW_GUIDES["ldd_obs_iv_tradeoff"]["metric_keys"] == (
        "ion",
        "gm_max",
        "ron",
        "gds",
    )
    assert QUESTION_REVIEW_GUIDES["ldd_obs_field_tradeoff"]["metric_keys"] == (
        "ion",
        "ron",
    )


def test_ldd_case_model_answer_is_grounded_in_curve_and_field() -> None:
    answer = build_grounded_model_answer(
        load_topic("ldd_field_resistance_tradeoff"),
        _ldd_context(),
    )

    assert "LDD는 Channel과 고농도 Drain 사이" in answer
    assert "Ion:" in answer
    assert "Ron:" in answer
    assert "gm max:" in answer
    assert "gds:" in answer
    assert "λ (CLM):" in answer
    assert "Drain 표면 부근의 전위" in answer
    assert "전계 완화와 access resistance" in answer
    assert "출력 저항은 감소" in answer


def test_ldd_case_tutor_uses_case_result_and_theory() -> None:
    result = LearningLLMService().ask_followup(
        load_topic("ldd_field_resistance_tradeoff"),
        "이번 결과에서 LDD doping을 높였더니 Drain Field와 Ion이 왜 함께 증가했나요?",
        _ldd_context(),
    )

    assert result.question_type == "current_result"
    assert result.uses_current_result
    assert "metric:ion" in result.evidence_ids
    assert {"ldd", "electric_field", "on_current"} <= set(
        result.theory_concepts
    )
