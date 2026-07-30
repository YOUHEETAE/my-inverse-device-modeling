from __future__ import annotations

import json
from pathlib import Path

from backend.learning import (
    LearningAnalysisContext,
    LearningLLMService,
    LearningSession,
    load_topic,
)
from backend.learning.tutor_validation import validate_question_intent


FIXTURE = Path(__file__).parent / "fixtures" / "learning" / "sce_channel_length_analysis.json"


def _context() -> LearningAnalysisContext:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return LearningAnalysisContext.from_dict(data["learning_context"])


def _intent(**changes) -> dict:
    data = {
        "intent": "explain_current_result",
        "target_concepts": ["threshold_voltage"],
        "requested_metrics": ["vth"],
        "requested_action": "explain",
        "conditions": {},
        "references_previous": False,
        "needs_current_result": True,
        "needs_theory": True,
        "needs_new_experiment": False,
        "needs_clarification": False,
        "clarification_question": None,
        "answer_structure": "cause_and_effect",
    }
    data.update(changes)
    return data


class _Provider:
    name = "external_llm"
    model = "intent-pipeline"

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def generate(self, system, user, payload):
        self.calls.append((system, user, payload))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_external_question_uses_interpreter_then_grounded_writer() -> None:
    provider = _Provider(
        _intent(answer_structure="parameter_by_parameter"),
        {
            "question_type": "current_result",
            "answer": "이번 결과의 Vth 감소는 채널 장벽에 대한 Drain 영향 증가와 연결됩니다.",
            "evidence_ids": ["metric:vth_high"],
            "distinguishes_current_result": True,
            "needs_new_experiment": False,
            "suggested_action_id": "observe_potential_map",
        },
    )
    response = LearningLLMService(provider).ask_followup(
        load_topic("sce_channel_length"),
        "문턱이 내려간 까닭을 항목별로 풀어줘.",
        _context(),
    )

    assert len(provider.calls) == 2
    intent_payload = provider.calls[0][2]
    answer_payload = provider.calls[1][2]
    assert "simulation_facts" not in intent_payload
    assert answer_payload["simulation_facts"]
    assert answer_payload["knowledge_layers"]["experiment_facts"]
    assert (
        answer_payload["knowledge_layers"]["metric_definitions"]["vth"]
        ["source_curve"]
        == "Id–Vg at Vd=1.5 V"
    )
    assert answer_payload["interpreted_intent"]["intent"] == "explain_current_result"
    assert answer_payload["answer_plan"]["organize_each_requested_metric"]
    assert response.source == "external_llm"
    assert response.question_type == "current_result"
    assert response.matched_concepts == ("threshold_voltage",)
    assert response.interpreted_intent["answer_structure"] == "parameter_by_parameter"
    session = LearningSession.create(load_topic("sce_channel_length"))
    LearningLLMService.record_followup(session, "문턱이 왜 내려가?", response)
    restored = LearningSession.from_dict(session.to_dict())
    assert (
        restored.followup_history[-1]
        .interpreted_intent["intent"]
        == "explain_current_result"
    )


def test_python_keeps_explicit_result_and_experiment_cues_authoritative() -> None:
    topic, context = load_topic("sce_channel_length"), _context()
    misleading_theory = _intent(
        intent="explain_theory",
        needs_current_result=False,
    )
    provider = _Provider(
        misleading_theory,
        {
            "question_type": "current_result",
            "answer": "현재 결과의 DIBL 증가를 근거로 설명합니다.",
            "evidence_ids": ["metric:dibl"],
            "distinguishes_current_result": True,
            "needs_new_experiment": False,
            "suggested_action_id": None,
        },
    )
    result = LearningLLMService(provider).ask_followup(
        topic,
        "이번 결과에서 DIBL이 왜 증가했나요?",
        context,
    )
    assert result.question_type == "current_result"

    experiment_intent = _intent(
        intent="explain_theory",
        target_concepts=["channel_length"],
        requested_metrics=[],
        needs_current_result=False,
    )
    provider = _Provider(
        experiment_intent,
        {
            "question_type": "new_experiment",
            "answer": "요청한 조건은 새 실험으로 실행해야 합니다.",
            "evidence_ids": [],
            "distinguishes_current_result": True,
            "needs_new_experiment": True,
            "suggested_action_id": None,
        },
    )
    experiment = LearningLLMService(provider).ask_followup(
        topic,
        "L을 500 nm로 추가해서 시뮬레이션해줘.",
        context,
    )
    assert experiment.question_type == "new_experiment"
    assert experiment.needs_new_experiment


def test_intent_validator_rejects_invented_conditions() -> None:
    try:
        validate_question_intent(
            _intent(
                intent="add_experiment_condition",
                requested_action="add_condition",
                conditions={"L": 500},
                needs_new_experiment=True,
            ),
            question="채널 조건을 하나 추가해줘.",
            allowed_concepts={"threshold_voltage"},
            allowed_metrics={"vth"},
            allowed_parameters={"L"},
        )
    except ValueError as error:
        assert str(error) == "invented_intent_condition"
    else:
        raise AssertionError("LLM-invented experiment condition was accepted")


def test_intent_validator_normalizes_common_model_variants() -> None:
    normalized = validate_question_intent(
        {
            "intent": "confirm_setup",
            "utterance_type": "confirmation",
            "confidence": "0.91",
            "alternative_intents": ["explain_result"],
            "target_concepts": ["channel"],
            "requested_metrics": ["VTH_HIGH_V"],
            "requested_action": "confirm_setup",
            "conditions": None,
            "clarification_question": "",
            "answer_structure": "cause_effect",
        },
        question="이 실험 조건이 맞아?",
        allowed_concepts={"channel_length"},
        allowed_metrics={"vth_high"},
        allowed_parameters={"L"},
    )
    assert normalized.intent == "confirm_experiment_setup"
    assert normalized.utterance_type == "experiment_confirmation"
    assert normalized.target_concepts == ("channel_length",)
    assert normalized.requested_metrics == ("vth_high",)
    assert normalized.requested_action == "confirm"
    assert normalized.conditions == {}
    assert normalized.clarification_question is None
    assert normalized.answer_structure == "cause_and_effect"
    assert normalized.confidence == 0.91


def test_invalid_intent_uses_python_route_but_keeps_answer_llm() -> None:
    provider = _Provider(
        {},
        {},
        {
            "question_type": "case_theory",
            "answer": (
                "이 프로젝트의 Ion은 Vg=3.0 V로 켠 Id–Vd 곡선에서 "
                "Vd=3.0 V일 때의 |Id|입니다."
            ),
            "evidence_ids": [],
            "distinguishes_current_result": False,
            "needs_new_experiment": False,
            "suggested_action_id": None,
        },
    )
    response = LearningLLMService(provider).ask_followup(
        load_topic("sce_channel_length"),
        "혹시 Ion은 언제의 전류야?",
        _context(),
    )
    assert len(provider.calls) == 3
    assert response.source == "external_llm"
    assert response.fallback_reason is None
    assert response.interpretation_source == "deterministic_fallback"
    assert response.pipeline_warnings == (
        "intent_validation_failed:invalid_question_intent_type",
    )
    assert "Vg=3.0 V" in response.answer


def test_real_failure_phrases_route_without_expression_specific_fallbacks() -> None:
    topic, context = load_topic("sce_channel_length"), _context()
    service = LearningLLMService()

    ion = service.ask_followup(
        topic,
        "혹시 Ion은 언제의 전류야?",
        context,
    )
    assert ion.question_type == "case_theory"
    assert "Vg=3.0 V" in ion.answer and "Vd=3.0 V" in ion.answer

    vth = service.ask_followup(
        topic,
        "채널길이가 짧아지는데 vth가 작아지는 이유가 뭐야?",
        context,
    )
    assert vth.question_type == "current_result"
    assert vth.uses_current_result
    assert not vth.needs_new_experiment
    assert {
        "experiment:conditions",
        "metric:vth_high",
    } <= set(vth.evidence_ids)

    confirmation = service.ask_followup(
        topic,
        "이 실험은 700과 300nm만, 즉 길이만 바꾼거 맞잖아.",
        context,
    )
    assert confirmation.question_type == "current_result"
    assert confirmation.evidence_ids == ("experiment:conditions",)
    assert "T, B, SD, LDD는 동일하게 고정" in confirmation.answer
