from __future__ import annotations

import json
from pathlib import Path

from backend.learning import (
    FollowupResponse,
    LearningAnalysisContext,
    LearningKnowledgeAssembler,
    LearningLLMService,
    LearningSession,
    QuestionRoute,
    build_response_plan,
    load_theory_knowledge_base,
    load_topic,
)
from tcad.data_extraction.parameter_extraction_core import (
    PARAMETER_EXTRACTION_DEFINITIONS,
)


FIXTURE = Path(__file__).parent / "fixtures" / "learning" / "sce_channel_length_analysis.json"


def _context() -> LearningAnalysisContext:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return LearningAnalysisContext.from_dict(data["learning_context"])


class _Provider:
    name = "external_llm"
    model = "learning-dialogue"

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def generate(self, system, user, payload):
        self.calls.append((system, user, payload))
        return self.responses.pop(0)


def test_metric_definitions_are_authoritative_and_bias_specific() -> None:
    ion = PARAMETER_EXTRACTION_DEFINITIONS["ion_ma_per_um"]
    ioff = PARAMETER_EXTRACTION_DEFINITIONS["ioff_ma_per_um"]
    dibl = PARAMETER_EXTRACTION_DEFINITIONS["dibl_gm_v_per_v"]
    assert "Vg=3.0 V" in ion["learning_explanation"]
    assert "Vd=3.0 V" in ion["learning_explanation"]
    assert "Vd=1.5 V" in ioff["learning_explanation"]
    assert "Vg=0 V" in ioff["learning_explanation"]
    assert "1e-4 mA/µm" in dibl["learning_explanation"]
    assert "1.45 V" in dibl["learning_explanation"]


def test_knowledge_layers_separate_experiment_result_definition_and_theory() -> None:
    topic, context = load_topic("sce_channel_length"), _context()
    theory = load_theory_knowledge_base().retrieve(
        ("channel_length", "on_current")
    )
    layers = LearningKnowledgeAssembler.build(
        topic,
        context,
        theory,
        requested_metrics=("ion",),
    )
    assert layers.authority_order == (
        "experiment_facts",
        "result_facts",
        "metric_definitions",
        "theory_facts",
    )
    assert layers.experiment_facts["changed_parameters"] == ("L",)
    assert set(layers.experiment_facts["fixed_parameters"]) == {
        "T",
        "B",
        "SD",
        "LDD",
    }
    assert layers.experiment_facts["controlled_single_parameter_comparison"]
    assert layers.result_facts["ion"]["evidence_id"] == "metric:ion"
    assert (
        layers.result_facts["ion"]["directional_implication"]
        == "favorable_for_metric"
    )
    assert (
        layers.result_facts["ioff"]["directional_implication"]
        == "unfavorable_for_metric"
    )
    assert (
        layers.result_facts["vth_high"]["directional_implication"]
        == "design_target_required"
    )
    assert set(layers.metric_definitions) == {"ion"}
    assert layers.theory_facts


def test_dialogue_state_updates_and_old_sessions_rebuild_from_history() -> None:
    topic = load_topic("sce_channel_length")
    session = LearningSession.create(topic)
    response = FollowupResponse(
        "current_result",
        "Vth 설명",
        ("metric:vth_high",),
        True,
        source="external_llm",
        matched_concepts=("threshold_voltage", "short_channel_effect"),
        uses_current_result=True,
        interpreted_intent={
            "intent": "explain_current_result",
            "requested_action": "explain",
            "conditions": {},
        },
    )
    LearningLLMService.record_followup(session, "Vth가 왜 감소했어?", response)
    state = session.dialogue_state
    assert state.current_topic == topic.topic_id
    assert state.current_focus == [
        "threshold_voltage",
        "short_channel_effect",
    ]
    assert state.last_explained_concept == "threshold_voltage"
    assert state.referenced_result == "current_experiment"
    assert state.last_intent["intent"] == "explain_current_result"
    assert state.turn_count == 1

    restored = LearningSession.from_dict(session.to_dict())
    assert restored.dialogue_state.to_dict() == state.to_dict()

    legacy = session.to_dict()
    legacy.pop("dialogue_state")
    rebuilt = LearningSession.from_dict(legacy)
    assert rebuilt.dialogue_state.current_focus == state.current_focus
    assert rebuilt.dialogue_state.referenced_result == "current_experiment"
    assert rebuilt.dialogue_state.turn_count == 1


def test_local_definition_answer_uses_project_ion_extraction_contract() -> None:
    response = LearningLLMService().ask_followup(
        load_topic("sce_channel_length"),
        "혹시 Ion은 언제의 전류야?",
        _context(),
    )
    assert response.question_type == "case_theory"
    assert "Vg=3.0 V" in response.answer
    assert "Vd=3.0 V" in response.answer
    assert "|Id|" in response.answer


def test_experiment_confirmation_is_acknowledged_and_saved_as_student_claim() -> None:
    topic = load_topic("sce_channel_length")
    question = "이 실험은 700과 300nm만, 즉 길이만 바꾼 거 맞잖아."
    response = LearningLLMService().ask_followup(
        topic,
        question,
        _context(),
    )
    assert response.learning_move == "confirm_experiment"
    assert response.claim_assessment == "supported"
    assert response.evidence_ids == ("experiment:conditions",)
    assert response.answer.startswith("네, 현재 실험 설정을 기준으로 맞습니다.")
    assert response.next_learning_question

    session = LearningSession.create(topic)
    LearningLLMService.record_followup(session, question, response)
    claim = session.dialogue_state.student_claims[-1]
    assert claim["assessment"] == "supported"
    assert claim["dialogue_move"] == "confirm_experiment"
    assert claim["evidence_ids"] == ["experiment:conditions"]
    assert (
        session.dialogue_state.concept_mastery["channel_length"]["status"]
        == "demonstrated"
    )

    restored = LearningSession.from_dict(session.to_dict())
    assert restored.dialogue_state.student_claims == session.dialogue_state.student_claims
    assert restored.followup_history[-1].claim_assessment == "supported"
    assert restored.followup_history[-1].next_learning_question


def test_correction_plan_reaches_answer_writer_and_later_turn_context() -> None:
    topic, context = load_topic("sce_channel_length"), _context()
    intent = {
        "intent": "confirm_experiment_setup",
        "utterance_type": "correction",
        "confidence": 0.96,
        "alternative_intents": [],
        "target_concepts": ["channel_length"],
        "requested_metrics": [],
        "requested_action": "confirm",
        "conditions": {},
        "references_previous": True,
        "needs_current_result": True,
        "needs_theory": False,
        "needs_new_experiment": False,
        "needs_clarification": False,
        "clarification_question": None,
        "answer_structure": "concise",
    }
    provider = _Provider(
        intent,
        {
            "question_type": "current_result",
            "answer": (
                "맞습니다. 현재 비교에서는 채널 길이만 변경했고 "
                "나머지 소자 조건은 고정했습니다."
            ),
            "evidence_ids": ["experiment:conditions"],
            "distinguishes_current_result": True,
            "needs_new_experiment": False,
            "suggested_action_id": None,
            "claim_assessment": "supported",
            "acknowledged_points": ["채널 길이만 변경했다는 지적이 맞습니다."],
            "correction_points": [],
            "next_learning_question": "고정 조건이 필요한 이유도 확인해 볼까요?",
        },
    )
    response = LearningLLMService(provider).ask_followup(
        topic,
        "아니, 이 실험은 길이만 바꾼 거잖아.",
        context,
        dialogue_state={"student_claims": []},
    )
    answer_plan = provider.calls[1][2]["answer_plan"]
    assert answer_plan["dialogue_move"] == "acknowledge_correction"
    assert answer_plan["acknowledge_before_explaining"]
    assert response.claim_assessment == "supported"
    assert response.acknowledged_points

    session = LearningSession.create(topic)
    LearningLLMService.record_followup(
        session,
        "아니, 이 실험은 길이만 바꾼 거잖아.",
        response,
    )
    next_provider = _Provider(
        {
            **intent,
            "intent": "explain_theory",
            "utterance_type": "concept_question",
            "requested_action": "explain",
            "references_previous": True,
            "needs_current_result": False,
            "needs_theory": True,
        },
        {
            "question_type": "case_theory",
            "answer": "통제 비교는 관찰된 차이를 변경 변수와 연결하기 위한 조건입니다.",
            "evidence_ids": [],
            "distinguishes_current_result": False,
            "needs_new_experiment": False,
            "suggested_action_id": None,
            "claim_assessment": "not_applicable",
            "acknowledged_points": [],
            "correction_points": [],
            "next_learning_question": None,
        },
    )
    LearningLLMService(next_provider).ask_followup(
        topic,
        "그게 왜 중요해?",
        context,
        dialogue_state=session.dialogue_state.to_dict(),
    )
    next_intent_payload = next_provider.calls[0][2]
    next_answer_plan = next_provider.calls[1][2]["answer_plan"]
    assert next_intent_payload["dialogue_state"]["student_claims"]
    assert next_answer_plan["prior_claims"][-1]["assessment"] == "supported"
    assert "channel_length" in next_answer_plan["known_concepts"]


def test_response_plan_adapts_depth_without_changing_scientific_route() -> None:
    route = QuestionRoute(
        question_type="current_result",
        relevance_to_case="direct",
        matched_concepts=("threshold_voltage",),
        uses_current_result=True,
        answer_structure="cause_and_effect",
    )
    beginner = build_response_plan(
        "Vth가 왜 감소했나요?",
        route,
        None,
        None,
        {"understanding_level": "unknown"},
    )
    partial = build_response_plan(
        "Vth가 왜 감소했나요?",
        route,
        None,
        None,
        {"understanding_level": "partial"},
    )
    advanced = build_response_plan(
        "Vth가 왜 감소했나요?",
        route,
        None,
        None,
        {
            "understanding_level": "correct",
            "completed_concepts": ["threshold_voltage"],
        },
    )
    misconception = build_response_plan(
        "Vth가 왜 감소했나요?",
        route,
        None,
        None,
        {
            "understanding_level": "correct",
            "detected_misconceptions": ["gate_alone_controls_barrier"],
        },
    )

    assert all(
        item.dialogue_move == "answer_question"
        for item in (beginner, partial, advanced, misconception)
    )
    assert beginner.explanation_level == "foundational"
    assert beginner.include_foundation
    assert partial.explanation_level == "intermediate"
    assert partial.next_question_style == "mechanism_check"
    assert advanced.explanation_level == "advanced"
    assert advanced.next_question_style == "transfer"
    assert "avoid_repeating_mastered_definition" in advanced.adaptation_reasons
    assert misconception.explanation_level == "foundational"
    assert misconception.next_question_style == "diagnostic"


def test_adaptive_profile_reaches_writer_and_persists_level() -> None:
    intent = {
        "intent": "explain_current_result",
        "utterance_type": "current_result_question",
        "confidence": 0.95,
        "alternative_intents": [],
        "target_concepts": ["threshold_voltage"],
        "requested_metrics": ["vth_high"],
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
    provider = _Provider(
        intent,
        {
            "question_type": "current_result",
            "answer": "현재 Vth 감소를 장벽 제어와 연결해 설명할 수 있습니다.",
            "evidence_ids": ["metric:vth_high"],
            "distinguishes_current_result": True,
            "needs_new_experiment": False,
            "suggested_action_id": None,
            "claim_assessment": "not_applicable",
            "acknowledged_points": [],
            "correction_points": [],
            "next_learning_question": None,
        },
    )
    response = LearningLLMService(provider).ask_followup(
        load_topic("sce_channel_length"),
        "Vth가 왜 감소했나요?",
        _context(),
        learner_profile={
            "understanding_level": "partial",
            "completed_concepts": ["ion_can_increase"],
            "remaining_concepts": ["vth_decreases"],
            "detected_misconceptions": [],
        },
    )
    payload = provider.calls[1][2]
    assert payload["answer_plan"]["explanation_level"] == "intermediate"
    assert payload["answer_plan"]["include_mechanism_chain"]
    assert payload["answer_plan"]["review_concepts"] == ("vth_decreases",)
    assert payload["learner_profile"]["completed_concepts"] == (
        "ion_can_increase",
    )
    assert response.explanation_level == "intermediate"
    assert response.next_learning_question is None

    session = LearningSession.create(load_topic("sce_channel_length"))
    LearningLLMService.record_followup(
        session,
        "Vth가 왜 감소했나요?",
        response,
    )
    restored = LearningSession.from_dict(session.to_dict())
    assert restored.followup_history[-1].explanation_level == "intermediate"
    assert (
        "connect_observation_to_mechanism"
        in restored.followup_history[-1].adaptation_reasons
    )
