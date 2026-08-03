from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.learning import (
    JsonSessionRepository,
    LearningAnalysisContext,
    LearningLLMService,
    LearningSession,
    load_topic,
)
from backend.learning.tutor_validation import evidence_ids


FIXTURE = Path(__file__).parent / "fixtures" / "learning" / "sce_channel_length_analysis.json"


def _context() -> LearningAnalysisContext:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return LearningAnalysisContext.from_dict(data["learning_context"])


def _history(session: LearningSession) -> list[dict]:
    return [
        {
            "question": turn.question,
            "answer": turn.answer,
            "question_type": turn.question_type,
            "matched_concepts": turn.matched_concepts,
        }
        for turn in session.followup_history
    ]


def test_free_question_matrix_stays_grounded_and_case_agnostic() -> None:
    topic, context = load_topic("sce_channel_length"), _context()
    service = LearningLLMService()
    session = LearningSession.create(topic)
    scenarios = (
        ("이번 결과에서 Vth가 왜 감소했나요?", "current_result", True, False),
        ("그건 왜 그런가요?", "current_result", True, False),
        ("SCE가 정확히 무엇인가요?", "case_theory", False, False),
        ("Potential Map에서는 무엇을 봐야 하나요?", "case_theory", False, False),
        ("PN 접합이 무엇인가요?", "adjacent_theory", False, False),
        ("PN 접합에서 접합 길이가 짧아지면 어떻게 되나요?", "hypothetical", False, True),
        ("Body doping을 높이면 DIBL이 줄어드나요?", "hypothetical", False, True),
        ("L을 500 nm로 바꾸면 결과가 어떻게 나오는지 시뮬레이션해줘.", "new_experiment", False, True),
        ("오늘 날씨가 어떤가요?", "out_of_scope", False, False),
    )

    for question, expected_type, uses_result, needs_experiment in scenarios:
        response = service.ask_followup(topic, question, context, _history(session))
        service.record_followup(session, question, response)
        assert response.question_type == expected_type
        assert response.uses_current_result is uses_result
        assert response.needs_new_experiment is needs_experiment
        assert bool(response.evidence_ids) is uses_result
        assert response.source == "local"
        if uses_result:
            assert response.distinguishes_current_result
            assert set(response.evidence_ids) <= evidence_ids(context)
        else:
            assert not response.evidence_ids
        if expected_type == "hypothetical":
            assert "현재 700 nm와 300 nm 비교에서 직접 확인한 결과가 아닙니다" in response.answer

    pn_turn = session.followup_history[5]
    assert pn_turn.needs_clarification
    assert "공핍영역" in pn_turn.answer
    assert session.followup_history[1].matched_concepts == ("threshold_voltage",)


def test_question_context_and_metadata_survive_close_and_reopen() -> None:
    topic, context = load_topic("sce_channel_length"), _context()
    service = LearningLLMService()
    session = LearningSession.create(topic)
    session.analysis_snapshot = context.to_dict()

    first = service.ask_followup(
        topic,
        "이번 결과에서 DIBL이 왜 증가했나요?",
        context,
    )
    service.record_followup(session, "이번 결과에서 DIBL이 왜 증가했나요?", first)

    with TemporaryDirectory() as directory:
        repository = JsonSessionRepository(Path(directory))
        repository.save(session)
        restored = repository.load(session.session_id)
        assert restored is not None
        restored_context = LearningAnalysisContext.from_dict(restored.analysis_snapshot)
        inherited = service.ask_followup(
            topic,
            "그건 왜 그런가요?",
            restored_context,
            _history(restored),
        )
        service.record_followup(restored, "그건 왜 그런가요?", inherited)
        repository.save(restored)
        reopened = repository.load(session.session_id)

    assert reopened is not None
    assert len(reopened.followup_history) == 2
    assert reopened.followup_history[-1].question_type == "current_result"
    assert reopened.followup_history[-1].matched_concepts == ("dibl",)
    assert reopened.followup_history[-1].uses_current_result
    assert reopened.followup_history[-1].evidence_ids == ("metric:dibl",)
    assert reopened.followup_history[-1].theory_concepts
    assert reopened.followup_history[-1].case_connection


class _Provider:
    name = "external_llm"
    model = "scenario-test"

    def __init__(self, *responses):
        self.responses = list(responses)

    def generate(self, _system, _user, _payload):
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _external_followup(*, evidence_ids: list[str] | None = None) -> dict:
    return {
        "question_type": "current_result",
        "answer": "이번 결과에서 DIBL은 증가했으며, 드레인의 소스 장벽 제어 영향이 커진 것으로 해석할 수 있습니다.",
        "evidence_ids": evidence_ids if evidence_ids is not None else ["metric:dibl"],
        "distinguishes_current_result": True,
        "needs_new_experiment": False,
        "suggested_action_id": "observe_potential_map",
    }


def _intent() -> dict:
    return {
        "intent": "explain_current_result",
        "target_concepts": ["dibl"],
        "requested_metrics": ["dibl"],
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


def test_external_success_timeout_and_invalid_response_have_visible_sources() -> None:
    topic, context = load_topic("sce_channel_length"), _context()
    question = "이번 결과에서 DIBL이 왜 증가했나요?"

    external = LearningLLMService(
        _Provider(_intent(), _external_followup())
    ).ask_followup(
        topic, question, context,
    )
    assert external.source == "external_llm"
    assert external.fallback_reason is None
    assert external.evidence_ids == ("metric:dibl",)

    timeout = LearningLLMService(
        _Provider(_intent(), TimeoutError("timeout"))
    ).ask_followup(
        topic, question, context,
    )
    assert timeout.source == "external_error"
    assert timeout.fallback_reason == "external_timeout"
    assert timeout.evidence_ids == ()
    assert "5초 후" in timeout.answer

    invalid_payload = _external_followup(evidence_ids=["invented:evidence"])
    invalid = LearningLLMService(
        _Provider(_intent(), invalid_payload, invalid_payload)
    ).ask_followup(
        topic, question, context,
    )
    assert invalid.source == "external_error"
    assert invalid.fallback_reason == "external_validation_failed"
    assert invalid.evidence_ids == ()
