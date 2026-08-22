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


def _body_context() -> LearningAnalysisContext:
    return LearningAnalysisContext(
        experiment={
            "changed_parameter": "B",
            "changed_parameters": ["B"],
            "before": 1e16,
            "after": 5e16,
            "baseline_conditions": {
                "L": 700.0,
                "T": 20.0,
                "B": 1e16,
                "SD": 1e20,
                "LDD": 1e18,
            },
            "comparison_conditions": {
                "L": 700.0,
                "T": 20.0,
                "B": 5e16,
                "SD": 1e20,
                "LDD": 1e18,
            },
            "fixed_parameters": {
                "L": 700.0,
                "T": 20.0,
                "SD": 1e20,
                "LDD": 1e18,
            },
        },
        electrical_changes={
            "vth_low": _change(
                0.16759, 0.56699, "increase", "V", "metric:vth_low"
            ),
            "vth_high": _change(
                0.74484, 1.36449, "increase", "V", "metric:vth_high"
            ),
            "ion": _change(
                3.06334, 1.84477, "decrease", "mA/um", "metric:ion"
            ),
            "ioff": _change(
                2.713e-4, 9.687e-9, "decrease", "mA/um", "metric:ioff"
            ),
            "ion_ioff_ratio": _change(
                1.1291e4,
                1.9044e8,
                "increase",
                "ratio",
                "metric:ion_ioff_ratio",
            ),
            "ss": _change(
                77.3249, 88.9206, "increase", "mV/dec", "metric:ss"
            ),
        },
        field_observations=(
            LearningObservation(
                source="field",
                evidence_id="body_channel_potential_change",
                quantity="potential",
                observation="increase",
                confidence="high",
                field_display="potential",
                region="channel_near_surface",
            ),
            LearningObservation(
                source="field",
                evidence_id="body_channel_field_change",
                quantity="electric_field",
                observation="increase",
                confidence="high",
                field_display="electric_field",
                region="channel_near_surface",
            ),
        ),
        in_training_range=True,
        analysis_status="partial",
    )


def test_body_case_has_three_predictions_and_two_iv_plus_one_field_question() -> None:
    topic = load_topic("body_doping_design_window")

    assert [question.question_id for question in topic.prediction_questions] == [
        "body_pred_vth",
        "body_pred_ioff",
        "body_pred_ion",
    ]
    assert [question.question_id for question in topic.observation_questions] == [
        "body_obs_iv_shift",
        "body_obs_iv_tradeoff",
        "body_obs_field_evidence",
    ]
    assert all(question.reason_required for question in topic.prediction_questions)
    assert all(question.reason_required for question in topic.observation_questions)
    assert topic.observation_questions[0].correct_options == (
        "Vth 증가",
        "Ioff 감소",
    )
    assert "Ioff의 상대 감소폭" in topic.observation_questions[1].correct_options[0]
    assert "구동 성능 비용" in topic.observation_questions[1].correct_options[0]
    assert "공핍 전하" in topic.observation_questions[2].correct_options[0]
    assert "Gate bias" in topic.observation_questions[2].correct_options[0]


def test_body_case_ui_content_covers_the_full_learning_flow() -> None:
    topic_id = "body_doping_design_window"
    question_ids = {
        "body_pred_vth",
        "body_pred_ioff",
        "body_pred_ion",
        "body_obs_iv_shift",
        "body_obs_iv_tradeoff",
        "body_obs_field_evidence",
    }

    assert CASE_UNDERSTANDING_GUIDES[topic_id]["question"].endswith("?")
    assert len(CASE_UNDERSTANDING_GUIDES[topic_id]["evidence"]) == 3
    assert len(CASE_CORE_SUMMARIES[topic_id]) == 3
    assert question_ids <= set(QUESTION_REVIEW_GUIDES)
    assert QUESTION_REVIEW_GUIDES["body_obs_iv_shift"]["metric_keys"] == (
        "vth_low",
        "vth_high",
        "ioff",
    )
    assert QUESTION_REVIEW_GUIDES["body_obs_iv_tradeoff"]["metric_keys"] == (
        "ion",
        "ioff",
        "ion_ioff_ratio",
    )


def test_body_case_model_answer_is_grounded_in_curve_and_field_results() -> None:
    answer = build_grounded_model_answer(
        load_topic("body_doping_design_window"),
        _body_context(),
    )

    assert "Body doping을 높이면" in answer
    assert "Vth (낮은 Vd):" in answer
    assert "Ion:" in answer
    assert "Ioff:" in answer
    assert "Ioff의 상대 감소폭이 더 커" in answer
    assert "채널 표면 부근의 전위" in answer
    assert "Field 크기를 전류 크기로 직접 치환하지 않는다" in answer
    assert "목표 누설, 요구 구동 전류와 허용 Vth 범위" in answer


def test_body_case_tutor_receives_current_result_and_body_theory() -> None:
    result = LearningLLMService().ask_followup(
        load_topic("body_doping_design_window"),
        "이번 결과에서 Body doping을 높였더니 Vth가 왜 증가했나요?",
        _body_context(),
    )

    assert result.question_type == "current_result"
    assert result.uses_current_result
    assert {"metric:vth_low", "metric:vth_high"}.intersection(
        result.evidence_ids
    )
    assert {"body_doping", "threshold_voltage"} <= set(result.theory_concepts)
