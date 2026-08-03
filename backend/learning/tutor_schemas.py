from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class AnswerEvaluation:
    understanding_level: str
    correct_concepts: tuple[str, ...] = ()
    missing_concepts: tuple[str, ...] = ()
    detected_misconceptions: tuple[str, ...] = ()
    unsupported_claims: tuple[str, ...] = ()
    feedback_strategy: str = "hint"
    recommended_next_action: str = "show_feedback"
    source: str = "local"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FeedbackEvidence:
    label: str
    before: float
    after: float
    unit: str | None
    interpretation: str
    evidence_id: str | None = None


@dataclass(frozen=True)
class LearningFeedback:
    headline: str
    model_answer: str = ""
    positive_feedback: tuple[str, ...] = ()
    corrections: tuple[str, ...] = ()
    evidence: tuple[FeedbackEvidence, ...] = ()
    curve_focus: str = ""
    field_focus: str = ""
    summary: str = ""
    next_question: str = ""
    source: str = "local"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        json.dumps(data, ensure_ascii=False, allow_nan=False)
        return data


@dataclass(frozen=True)
class NextActionDecision:
    action_id: str
    reason: str
    source: str = "local"


@dataclass(frozen=True)
class LearningSessionSummary:
    headline: str
    summary: str
    understood_concepts: tuple[str, ...] = ()
    needs_review: tuple[str, ...] = ()
    detected_misconceptions: tuple[str, ...] = ()
    recommended_next_action: str | None = None
    source: str = "local"


@dataclass(frozen=True)
class FollowupResponse:
    question_type: str
    answer: str
    evidence_ids: tuple[str, ...] = ()
    distinguishes_current_result: bool = False
    needs_new_experiment: bool = False
    suggested_action_id: str | None = None
    source: str = "local"
    relevance_to_case: str = "related"
    matched_concepts: tuple[str, ...] = ()
    uses_current_result: bool = False
    needs_clarification: bool = False
    clarification_question: str | None = None
    theory_concepts: tuple[str, ...] = ()
    case_connection: str | None = None
    fallback_reason: str | None = None
    interpreted_intent: dict[str, Any] = field(default_factory=dict)
    interpretation_source: str = "deterministic"
    pipeline_warnings: tuple[str, ...] = ()
    pipeline_diagnostics: tuple[dict[str, Any], ...] = ()
    fallback_detail: str | None = None
    learning_move: str = "answer_question"
    claim_assessment: str = "not_applicable"
    acknowledged_points: tuple[str, ...] = ()
    correction_points: tuple[str, ...] = ()
    next_learning_question: str | None = None
    explanation_level: str = "foundational"
    adaptation_reasons: tuple[str, ...] = ()
