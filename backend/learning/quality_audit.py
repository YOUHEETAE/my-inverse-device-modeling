from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from .analysis_schemas import LearningAnalysisContext
from .schemas import FollowupTurn, LearningSession
from .schemas import TopicConfig
from .tutor_validation import evidence_ids


_QUESTION_TYPES = {
    "current_result",
    "case_theory",
    "adjacent_theory",
    "hypothetical",
    "new_experiment",
    "out_of_scope",
}
_CLAIM_MOVES = {
    "evaluate_claim",
    "acknowledge_correction",
    "confirm_experiment",
}
_EXPLANATION_LEVELS = {"foundational", "intermediate", "advanced"}
_SENTENCE = re.compile(r"(?<=[.!?。！？])\s+|\n+")


@dataclass(frozen=True)
class TutorTurnAudit:
    turn_number: int
    question_type: str
    passed: bool
    checks: dict[str, bool]
    failures: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TutorQualityReport:
    passed: bool
    turn_count: int
    passed_turns: int
    grounded_result_turns: int
    separated_theory_turns: int
    claim_feedback_turns: int
    adaptive_turns: int
    fallback_turns: int
    intent_recovery_turns: int
    gate_failures: tuple[str, ...] = ()
    turns: tuple[TutorTurnAudit, ...] = field(default_factory=tuple)

    @property
    def coverage_text(self) -> str:
        return f"{self.passed_turns}/{self.turn_count}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TutorAuditScenario:
    scenario_id: str
    question: str
    expected_type: str
    uses_current_result: bool
    needs_new_experiment: bool
    expected_learning_move: str = "answer_question"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TutorAuditScenario":
        return cls(
            scenario_id=str(data["scenario_id"]),
            question=str(data["question"]),
            expected_type=str(data["expected_type"]),
            uses_current_result=bool(data["uses_current_result"]),
            needs_new_experiment=bool(data["needs_new_experiment"]),
            expected_learning_move=str(
                data.get("expected_learning_move", "answer_question")
            ),
        )


@dataclass(frozen=True)
class TutorScenarioResult:
    scenario_id: str
    passed: bool
    failures: tuple[str, ...]
    actual_type: str
    learning_move: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TutorScenarioAuditReport:
    passed: bool
    scenario_results: tuple[TutorScenarioResult, ...]
    quality: TutorQualityReport

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _cohesive(answer: str) -> bool:
    sentences = [
        " ".join(item.lower().split())
        for item in _SENTENCE.split(answer.strip())
        if item.strip()
    ]
    return bool(sentences) and len(sentences) == len(set(sentences))


def audit_followup_history(
    turns: Iterable[FollowupTurn],
    context: LearningAnalysisContext,
) -> TutorQualityReport:
    allowed_evidence = evidence_ids(context)
    audits = []
    grounded = separated = claims = adaptive = fallbacks = recoveries = 0

    for number, turn in enumerate(turns, start=1):
        checks: dict[str, bool] = {
            "valid_route": turn.question_type in _QUESTION_TYPES,
            "answer_present": bool(turn.answer.strip()),
            "answer_cohesion": _cohesive(turn.answer),
        }
        evidence = set(turn.evidence_ids)
        if turn.uses_current_result:
            checks["result_grounding"] = bool(evidence) and evidence <= allowed_evidence
            checks["result_route"] = turn.question_type == "current_result"
            if checks["result_grounding"] and checks["result_route"]:
                grounded += 1
        else:
            checks["theory_result_separation"] = not evidence
            if checks["theory_result_separation"]:
                separated += 1

        if turn.question_type in {"hypothetical", "new_experiment"}:
            checks["experiment_boundary"] = turn.needs_new_experiment
        elif turn.question_type != "out_of_scope":
            checks["experiment_boundary"] = not turn.needs_new_experiment

        if turn.learning_move in _CLAIM_MOVES:
            checks["claim_feedback"] = (
                turn.claim_assessment != "not_applicable"
                and bool(turn.acknowledged_points)
            )
            if turn.claim_assessment in {
                "supported",
                "partially_supported",
                "contradicted",
            } and turn.uses_current_result:
                checks["claim_evidence"] = bool(evidence)
            if checks["claim_feedback"]:
                claims += 1

        checks["adaptive_metadata"] = (
            turn.explanation_level in _EXPLANATION_LEVELS
            and bool(turn.adaptation_reasons)
        )
        if checks["adaptive_metadata"]:
            adaptive += 1
        if turn.question_type != "out_of_scope":
            checks["learning_continuation"] = bool(turn.next_learning_question)

        if turn.fallback_reason:
            fallbacks += 1
            checks["fallback_diagnostic"] = bool(turn.fallback_detail)
        if turn.interpretation_source == "deterministic_fallback":
            recoveries += 1
            checks["intent_recovery_diagnostic"] = bool(turn.pipeline_warnings)

        failures = tuple(name for name, passed in checks.items() if not passed)
        audits.append(TutorTurnAudit(
            turn_number=number,
            question_type=turn.question_type,
            passed=not failures,
            checks=checks,
            failures=failures,
        ))

    gate_failures = tuple(
        f"turn_{item.turn_number}:{failure}"
        for item in audits
        for failure in item.failures
    )
    return TutorQualityReport(
        passed=not gate_failures,
        turn_count=len(audits),
        passed_turns=sum(item.passed for item in audits),
        grounded_result_turns=grounded,
        separated_theory_turns=separated,
        claim_feedback_turns=claims,
        adaptive_turns=adaptive,
        fallback_turns=fallbacks,
        intent_recovery_turns=recoveries,
        gate_failures=gate_failures,
        turns=tuple(audits),
    )


def audit_learning_session(
    session: LearningSession,
    context: LearningAnalysisContext,
) -> TutorQualityReport:
    return audit_followup_history(session.followup_history, context)


def run_tutor_scenarios(
    *,
    topic: TopicConfig,
    context: LearningAnalysisContext,
    scenarios: Iterable[TutorAuditScenario],
    service: Any,
    learner_profile: dict[str, Any] | None = None,
) -> TutorScenarioAuditReport:
    session = LearningSession.create(topic)
    results = []
    for scenario in scenarios:
        history = [
            {
                "question": turn.question,
                "answer": turn.answer,
                "question_type": turn.question_type,
                "matched_concepts": turn.matched_concepts,
            }
            for turn in session.followup_history
        ]
        response = service.ask_followup(
            topic,
            scenario.question,
            context,
            history,
            session.dialogue_state.to_dict(),
            learner_profile,
        )
        service.record_followup(session, scenario.question, response)
        checks = {
            "question_type": response.question_type == scenario.expected_type,
            "uses_current_result": (
                response.uses_current_result
                is scenario.uses_current_result
            ),
            "needs_new_experiment": (
                response.needs_new_experiment
                is scenario.needs_new_experiment
            ),
            "learning_move": (
                response.learning_move
                == scenario.expected_learning_move
            ),
        }
        failures = tuple(name for name, passed in checks.items() if not passed)
        results.append(TutorScenarioResult(
            scenario_id=scenario.scenario_id,
            passed=not failures,
            failures=failures,
            actual_type=response.question_type,
            learning_move=response.learning_move,
            source=response.source,
        ))
    quality = audit_learning_session(session, context)
    return TutorScenarioAuditReport(
        passed=all(item.passed for item in results) and quality.passed,
        scenario_results=tuple(results),
        quality=quality,
    )
