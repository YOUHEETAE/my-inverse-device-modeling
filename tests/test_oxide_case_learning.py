from __future__ import annotations

from backend.learning import LearningLLMService, load_topic
from backend.learning.analysis_schemas import (
    ElectricalChange,
    LearningAnalysisContext,
    LearningObservation,
)


def _oxide_context() -> LearningAnalysisContext:
    return LearningAnalysisContext(
        experiment={
            "changed_parameter": "T",
            "changed_parameters": ["T"],
            "before": 20.0,
            "after": 10.0,
            "baseline_conditions": {
                "L": 700.0, "T": 20.0, "B": 1e16,
                "SD": 1e20, "LDD": 1e18,
            },
            "comparison_conditions": {
                "L": 700.0, "T": 10.0, "B": 1e16,
                "SD": 1e20, "LDD": 1e18,
            },
            "fixed_parameters": {
                "L": 700.0, "B": 1e16, "SD": 1e20, "LDD": 1e18,
            },
        },
        electrical_changes={
            "gm_max": ElectricalChange(
                before=0.042476, after=0.075430, change_percent=77.58,
                direction="increase", unit="mS/um", available=True,
                evidence_id="metric:gm_max",
            ),
            "ss": ElectricalChange(
                before=77.32, after=69.27, change_percent=-10.42,
                direction="decrease", unit="mV/dec", available=True,
                evidence_id="metric:ss",
            ),
            "ioff": ElectricalChange(
                before=0.000271, after=0.006652, change_percent=2351.96,
                direction="increase", unit="mA/um", available=True,
                evidence_id="metric:ioff",
            ),
        },
        field_observations=(
            LearningObservation(
                source="field",
                evidence_id="oxide_drain_field_change",
                quantity="electric_field",
                observation="decrease",
                confidence="high",
                field_display="electric_field",
                region="drain_near_surface",
            ),
        ),
        in_training_range=True,
        analysis_status="partial",
    )


def test_oxide_case_uses_three_predictions_and_three_core_observations() -> None:
    topic = load_topic("oxide_gate_control")

    assert [question.question_id for question in topic.prediction_questions] == [
        "oxide_pred_gm",
        "oxide_pred_ss",
        "oxide_pred_ioff",
    ]
    assert [question.question_id for question in topic.observation_questions] == [
        "oxide_obs_iv_gate_control",
        "oxide_obs_iv_tradeoff",
        "oxide_obs_field_evidence",
    ]
    assert all(question.reason_required for question in topic.prediction_questions)
    assert all(question.reason_required for question in topic.observation_questions)
    assert topic.observation_questions[0].correct_options == ("gm 증가", "SS 감소")
    assert topic.observation_questions[1].correct_options == (
        "SS 감소로 subthreshold 기울기는 가팔라졌지만 Vth의 낮은 Vg 방향 이동이 더 크게 작용해 off-bias가 전도 시작점에 가까워졌다",
    )
    assert "Gate–Oxide–Channel" in topic.observation_questions[2].correct_options[0]


def test_oxide_case_tutor_uses_current_metrics_and_case_theory() -> None:
    service = LearningLLMService()
    topic = load_topic("oxide_gate_control")
    context = _oxide_context()

    result = service.ask_followup(
        topic,
        "이번 결과에서 gm은 증가하고 SS는 감소했는데 왜 그런가요?",
        context,
    )
    assert result.question_type == "current_result"
    assert result.uses_current_result
    assert {"metric:gm_max", "metric:ss"} <= set(result.evidence_ids)
    assert {"oxide_thickness", "transconductance", "subthreshold_swing"} <= set(
        result.theory_concepts
    )

    theory = service.ask_followup(
        topic,
        "Oxide thickness가 Gate control에 중요한 이유가 뭐야?",
        context,
    )
    assert theory.question_type == "case_theory"
    assert not theory.uses_current_result
    assert "정전기적 결합" in theory.answer
    assert "oxide_thickness" in theory.theory_concepts


def test_oxide_case_feedback_has_detailed_grounded_model_answer() -> None:
    service = LearningLLMService()
    topic = load_topic("oxide_gate_control")
    context = _oxide_context()
    evaluation = service.evaluate_answer(
        topic,
        topic.observation_questions[0],
        {
            "selected": ["gm 증가", "SS 감소"],
            "reason": "얇은 Oxide가 Gate-to-channel 결합을 강화하기 때문이다.",
        },
        context,
    )
    feedback = service.generate_feedback(topic, evaluation, context)
    assert "Gate oxide가 얇아지면" in feedback.model_answer
    assert "gm max:" in feedback.model_answer
    assert "SS:" in feedback.model_answer
    assert "Ioff:" in feedback.model_answer
    assert "[현재 Case의 I–V 근거]" in feedback.model_answer
    assert "[현재 Case의 Field Map 근거]" in feedback.model_answer
    assert "d(log10 Id)/dVg가 가팔라" in feedback.model_answer
    assert "Drain-side channel 제어" in feedback.model_answer
    assert "Gate–oxide 경계" in feedback.model_answer
    assert "Vth 이동의 영향이 더 커" in feedback.model_answer
    assert "metric:" not in feedback.model_answer


def test_oxide_case_keeps_field_observation_and_breakdown_claim_separate() -> None:
    response = LearningLLMService().ask_followup(
        load_topic("oxide_gate_control"),
        "현재 Drain 부근 전계가 변했으니 breakdown이 발생한 거지?",
        _oxide_context(),
    )
    assert response.question_type == "current_result"
    assert response.uses_current_result
    assert "oxide_drain_field_change" in response.evidence_ids
    assert "단정" in response.answer or "확정" in response.answer
