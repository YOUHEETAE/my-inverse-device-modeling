from __future__ import annotations

import json
from pathlib import Path

from backend.learning import (
    LearningAnalysisContext,
    LearningLLMService,
    LearningSession,
    TutorQuestionRouter,
    load_topic,
)
from backend.learning.intent_interpreter import QuestionIntent


FIXTURE = Path(__file__).parent / "fixtures" / "learning" / "sce_channel_length_analysis.json"


def _context() -> LearningAnalysisContext:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return LearningAnalysisContext.from_dict(data["learning_context"])


def test_router_separates_current_result_case_theory_and_adjacent_theory() -> None:
    router = TutorQuestionRouter()
    topic, context = load_topic("sce_channel_length"), _context()

    result = router.route("결과에서 Vth가 왜 감소했어?", topic, context)
    assert result.question_type == "current_result"
    assert result.relevance_to_case == "direct"
    assert result.uses_current_result
    assert result.matched_concepts == ("threshold_voltage",)

    theory = router.route("SCE가 정확히 뭐야?", topic, context)
    assert theory.question_type == "case_theory"
    assert theory.relevance_to_case == "direct"
    assert not theory.uses_current_result

    adjacent = router.route(
        "PN 접합에서 접합 길이가 짧아지면 어떻게 돼?",
        topic,
        context,
    )
    assert adjacent.question_type == "hypothetical"
    assert adjacent.relevance_to_case == "domain_adjacent"
    assert adjacent.needs_clarification
    assert "공핍영역" in adjacent.clarification_question

    pn_example = router.route(
        "PN 접합이 무엇이며 공핍영역은 어떻게 형성되나요?",
        topic,
        context,
    )
    assert pn_example.question_type == "adjacent_theory"
    assert pn_example.relevance_to_case == "domain_adjacent"


def test_router_distinguishes_hypothetical_new_experiment_and_out_of_scope() -> None:
    router = TutorQuestionRouter()
    topic, context = load_topic("sce_channel_length"), _context()

    hypothetical = router.route(
        "Body doping을 높이면 DIBL이 줄어?",
        topic,
        context,
    )
    assert hypothetical.question_type == "hypothetical"
    assert hypothetical.needs_new_experiment
    assert not hypothetical.uses_current_result

    experiment = router.route(
        "L을 200 nm로 하면 시뮬레이션 결과가 어떻게 나와?",
        topic,
        context,
    )
    assert experiment.question_type == "new_experiment"
    assert experiment.matched_concepts == ("channel_length",)
    assert experiment.needs_new_experiment

    ambiguous = router.route("길이가 짧아지면 어떻게 돼?", topic, context)
    assert ambiguous.question_type == "out_of_scope"
    assert ambiguous.needs_clarification

    unrelated = router.route("오늘 날씨가 어때?", topic, context)
    assert unrelated.question_type == "out_of_scope"
    assert unrelated.relevance_to_case == "unrelated"


def test_router_treats_broad_current_simulation_questions_as_current_result() -> None:
    router = TutorQuestionRouter()
    topic, context = load_topic("sce_channel_length"), _context()

    meaning = router.route(
        "지금 내가 돌린 시뮬레이션이 정확히 뭐를 의미하는거야?",
        topic,
        context,
    )
    assert meaning.question_type == "current_result"
    assert meaning.relevance_to_case == "direct"
    assert meaning.uses_current_result
    assert meaning.aggregate_result

    judgment = router.route(
        "각 파라미터의 변화가 좋은쪽으로 변화한건지 아닌지 알려줘.",
        topic,
        context,
        interpreted_intent=QuestionIntent(
            intent="predict_change",
            utterance_type="concept_question",
            confidence=0.88,
            requested_action="predict",
            needs_theory=True,
            answer_structure="cause_and_effect",
        ),
    )
    assert judgment.question_type == "current_result"
    assert judgment.uses_current_result
    assert judgment.aggregate_result
    assert judgment.answer_structure == "parameter_by_parameter"


def test_explicit_current_result_intent_survives_empty_targets() -> None:
    router = TutorQuestionRouter()
    topic, context = load_topic("sce_channel_length"), _context()
    route = router.route(
        "지금 내가 돌린 시뮬레이션이 정확히 뭐를 의미하는거야?",
        topic,
        context,
        interpreted_intent=QuestionIntent(
            intent="explain_current_result",
            utterance_type="current_result_question",
            confidence=0.93,
            requested_action="explain",
            needs_current_result=True,
            needs_theory=True,
        ),
    )
    assert route.question_type == "current_result"
    assert route.uses_current_result
    assert route.relevance_to_case == "direct"


def test_local_tutor_explains_aggregate_result_as_metric_tradeoff() -> None:
    topic, context = load_topic("sce_channel_length"), _context()
    meaning = LearningLLMService().ask_followup(
        topic,
        "지금 내가 돌린 시뮬레이션이 정확히 뭐를 의미하는거야?",
        context,
    )
    assert meaning.question_type == "current_result"
    assert meaning.uses_current_result
    assert "700 nm" in meaning.answer and "300 nm" in meaning.answer
    assert "T, B, SD, LDD" in meaning.answer
    assert "trade-off" in meaning.answer

    response = LearningLLMService().ask_followup(
        topic,
        "각 파라미터의 변화가 좋은쪽으로 변화한건지 아닌지 알려줘.",
        context,
    )

    assert response.question_type == "current_result"
    assert response.uses_current_result
    assert response.next_learning_question is None
    assert all(
        label in response.answer
        for label in ("Ion", "Ioff", "Vth", "DIBL", "SS")
    )
    assert "이득" in response.answer
    assert "손실" in response.answer
    assert "목표값" in response.answer
    assert "trade-off" in response.answer


def test_router_inherits_elliptical_followup_context() -> None:
    router = TutorQuestionRouter()
    topic, context = load_topic("sce_channel_length"), _context()
    route = router.route(
        "그건 왜?",
        topic,
        context,
        history=[{
            "question": "이번 결과에서 DIBL이 왜 증가했어?",
            "answer": "Drain 영향이 증가했습니다.",
            "question_type": "current_result",
        }],
    )
    assert route.question_type == "current_result"
    assert route.inherited_context
    assert route.uses_current_result
    assert route.matched_concepts == ("dibl",)

    physical_reason = router.route(
        "그 변화가 생기는 물리적 이유는 무엇인가요?",
        topic,
        context,
        history=[{
            "question": "이번 결과에서 Vth가 왜 감소했어?",
            "answer": "Vth가 감소했습니다.",
            "question_type": "current_result",
            "matched_concepts": ("threshold_voltage",),
        }],
    )
    assert physical_reason.question_type == "current_result"
    assert physical_reason.inherited_context
    assert physical_reason.matched_concepts == ("threshold_voltage",)

    broad_channel_question = router.route(
        "채널 줄어들면 생기는 일들 설명해줘. 각 파라미터 별로 왜 그런지도 함께.",
        topic,
        context,
        history=[{
            "question": "그러면 DIBL 설명해줘",
            "answer": "DIBL 설명",
            "question_type": "case_theory",
            "matched_concepts": ("dibl",),
        }],
    )
    assert broad_channel_question.question_type == "case_theory"
    assert broad_channel_question.matched_concepts == ("channel_length",)
    assert not broad_channel_question.inherited_context


def test_followup_service_uses_router_as_classification_authority() -> None:
    topic, context = load_topic("sce_channel_length"), _context()
    service = LearningLLMService()

    current = service.ask_followup(
        topic,
        "결과에서 Vth가 왜 감소했어?",
        context,
    )
    assert current.question_type == "current_result"
    assert current.relevance_to_case == "direct"
    assert current.uses_current_result
    assert current.matched_concepts == ("threshold_voltage",)

    adjacent = service.ask_followup(
        topic,
        "PN 접합에서 접합 길이가 짧아지면 어떻게 돼?",
        context,
    )
    assert adjacent.question_type == "hypothetical"
    assert adjacent.relevance_to_case == "domain_adjacent"
    assert adjacent.needs_clarification
    assert adjacent.clarification_question in adjacent.answer

    first = service.ask_followup(
        topic,
        "이번 결과에서 DIBL이 왜 증가했어?",
        context,
    )
    inherited = service.ask_followup(
        topic,
        "그건 왜?",
        context,
        history=[{
            "question": "이번 결과에서 DIBL이 왜 증가했어?",
            "answer": first.answer,
            "question_type": first.question_type,
        }],
    )
    assert inherited.question_type == "current_result"
    assert inherited.matched_concepts == ("dibl",)
    assert inherited.evidence_ids == ("metric:dibl",)
    assert "DIBL" in inherited.answer


def test_routing_context_survives_session_round_trip() -> None:
    topic, context = load_topic("sce_channel_length"), _context()
    service = LearningLLMService()
    session = LearningSession.create(topic)
    first = service.ask_followup(
        topic,
        "이번 결과에서 DIBL이 왜 증가했어?",
        context,
    )
    service.record_followup(
        session,
        "이번 결과에서 DIBL이 왜 증가했어?",
        first,
    )
    restored = LearningSession.from_dict(session.to_dict())
    turn = restored.followup_history[-1]
    assert turn.matched_concepts == ("dibl",)
    assert turn.uses_current_result
    assert "dibl" in turn.theory_concepts
    assert turn.case_connection
    assert turn.source == "local"
    assert turn.fallback_reason is None

    inherited = service.ask_followup(
        topic,
        "그건 왜?",
        context,
        history=[{
            "question": turn.question,
            "answer": turn.answer,
            "question_type": turn.question_type,
            "matched_concepts": turn.matched_concepts,
        }],
    )
    assert inherited.matched_concepts == ("dibl",)
    assert inherited.uses_current_result
