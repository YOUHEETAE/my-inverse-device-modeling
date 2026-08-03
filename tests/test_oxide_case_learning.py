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
        {"selected": ["10 nm"]},
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
    assert "oxide 또는 Gate 인접 영역의 관찰이 아니므로" in feedback.model_answer
    assert "breakdown을 확정" in feedback.model_answer
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
