from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from .dialogue_state import DialogueState

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LearningStep(str, Enum):
    TOPIC_SELECTION = "TOPIC_SELECTION"
    INTRODUCTION = "INTRODUCTION"
    BASELINE_SETUP = "BASELINE_SETUP"
    PREDICTION_QUESTION = "PREDICTION_QUESTION"
    PREDICTION_SUBMITTED = "PREDICTION_SUBMITTED"
    SIMULATION_RUNNING = "SIMULATION_RUNNING"
    RESULT_READY = "RESULT_READY"
    OBSERVATION_QUESTION = "OBSERVATION_QUESTION"
    OBSERVATION_SUBMITTED = "OBSERVATION_SUBMITTED"
    FEEDBACK_READY = "FEEDBACK_READY"
    NEXT_EXPERIMENT = "NEXT_EXPERIMENT"
    SESSION_COMPLETE = "SESSION_COMPLETE"
    ERROR = "ERROR"


class UnderstandingLevel(str, Enum):
    UNKNOWN = "unknown"
    CORRECT = "correct"
    PARTIAL = "partial"
    INCORRECT = "incorrect"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class QuestionSpec:
    question_id: str
    type: str
    prompt: str
    options: tuple[str, ...] = ()
    reason_required: bool = False
    correct_options: tuple[str, ...] = ()
    concepts_by_option: dict[str, tuple[str, ...]] = field(default_factory=dict)
    misconceptions_by_option: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QuestionSpec":
        return cls(
            question_id=str(data["question_id"]),
            type=str(data["type"]),
            prompt=str(data["prompt"]),
            options=tuple(str(item) for item in data.get("options", [])),
            reason_required=bool(data.get("reason_required", False)),
            correct_options=tuple(str(item) for item in data.get("correct_options", [])),
            concepts_by_option={
                str(option): tuple(str(item) for item in concepts)
                for option, concepts in data.get("concepts_by_option", {}).items()
            },
            misconceptions_by_option={
                str(option): tuple(str(item) for item in misconceptions)
                for option, misconceptions in data.get("misconceptions_by_option", {}).items()
            },
        )


@dataclass(frozen=True)
class NextActionSpec:
    action_id: str
    description: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NextActionSpec":
        return cls(str(data["action_id"]), str(data["description"]))


@dataclass(frozen=True)
class TopicConfig:
    topic_id: str
    title: str
    description: str
    learning_objectives: tuple[str, ...]
    required_outputs: tuple[str, ...]
    expected_concepts: tuple[str, ...]
    common_misconceptions: tuple[str, ...]
    baseline_conditions: dict[str, float]
    comparison_conditions: dict[str, float]
    prediction_questions: tuple[QuestionSpec, ...]
    observation_questions: tuple[QuestionSpec, ...]
    allowed_next_actions: tuple[NextActionSpec, ...]
    theory_concepts: tuple[str, ...] = ()
    theory_reference: str | None = None
    schema_version: str = "1.0"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TopicConfig":
        experiment = data["experiment"]
        return cls(
            topic_id=str(data["topic_id"]),
            title=str(data["title"]),
            description=str(data["description"]),
            learning_objectives=tuple(str(item) for item in data["learning_objectives"]),
            required_outputs=tuple(str(item) for item in data["required_outputs"]),
            expected_concepts=tuple(str(item) for item in data["expected_concepts"]),
            common_misconceptions=tuple(str(item) for item in data["common_misconceptions"]),
            baseline_conditions={str(key): float(value) for key, value in experiment["baseline"].items()},
            comparison_conditions={str(key): float(value) for key, value in experiment["comparison"].items()},
            prediction_questions=tuple(QuestionSpec.from_dict(item) for item in data["prediction_questions"]),
            observation_questions=tuple(QuestionSpec.from_dict(item) for item in data["observation_questions"]),
            allowed_next_actions=tuple(NextActionSpec.from_dict(item) for item in data["allowed_next_actions"]),
            theory_concepts=tuple(str(item) for item in data.get("theory_concepts", [])),
            theory_reference=str(data["theory_reference"]) if data.get("theory_reference") else None,
            schema_version=str(data.get("schema_version", "1.0")),
        )


@dataclass(frozen=True)
class AnswerRecord:
    question_id: str
    raw_answer: Any
    submitted_at: str
    evaluation: dict[str, Any] | None = None

    @classmethod
    def create(cls, question_id: str, raw_answer: Any, *, submitted_at: str | None = None) -> "AnswerRecord":
        # Reject values that cannot be persisted before mutating a session.
        json.dumps(raw_answer, ensure_ascii=False, allow_nan=False)
        return cls(question_id, raw_answer, submitted_at or utc_now())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnswerRecord":
        return cls(
            question_id=str(data["question_id"]),
            raw_answer=data.get("raw_answer"),
            submitted_at=str(data["submitted_at"]),
            evaluation=dict(data["evaluation"]) if data.get("evaluation") is not None else None,
        )


@dataclass(frozen=True)
class FollowupTurn:
    question: str
    answer: str
    question_type: str
    evidence_ids: tuple[str, ...]
    created_at: str
    relevance_to_case: str = "related"
    matched_concepts: tuple[str, ...] = ()
    uses_current_result: bool = False
    needs_new_experiment: bool = False
    needs_clarification: bool = False
    clarification_question: str | None = None
    theory_concepts: tuple[str, ...] = ()
    case_connection: str | None = None
    source: str = "local"
    fallback_reason: str | None = None
    interpreted_intent: dict[str, Any] = field(default_factory=dict)
    interpretation_source: str = "deterministic"
    pipeline_warnings: tuple[str, ...] = ()
    fallback_detail: str | None = None
    learning_move: str = "answer_question"
    claim_assessment: str = "not_applicable"
    acknowledged_points: tuple[str, ...] = ()
    correction_points: tuple[str, ...] = ()
    next_learning_question: str | None = None
    explanation_level: str = "foundational"
    adaptation_reasons: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FollowupTurn":
        return cls(
            question=str(data["question"]),
            answer=str(data["answer"]),
            question_type=str(data["question_type"]),
            evidence_ids=tuple(str(item) for item in data.get("evidence_ids", [])),
            created_at=str(data["created_at"]),
            relevance_to_case=str(data.get("relevance_to_case", "related")),
            matched_concepts=tuple(str(item) for item in data.get("matched_concepts", [])),
            uses_current_result=bool(data.get("uses_current_result", False)),
            needs_new_experiment=bool(data.get("needs_new_experiment", False)),
            needs_clarification=bool(data.get("needs_clarification", False)),
            clarification_question=(
                str(data["clarification_question"])
                if data.get("clarification_question")
                else None
            ),
            theory_concepts=tuple(str(item) for item in data.get("theory_concepts", [])),
            case_connection=str(data["case_connection"]) if data.get("case_connection") else None,
            source=str(data.get("source", "local")),
            fallback_reason=str(data["fallback_reason"]) if data.get("fallback_reason") else None,
            interpreted_intent=dict(data.get("interpreted_intent", {})),
            interpretation_source=str(
                data.get("interpretation_source", "deterministic")
            ),
            pipeline_warnings=tuple(
                str(item) for item in data.get("pipeline_warnings", [])
            ),
            fallback_detail=(
                str(data["fallback_detail"])
                if data.get("fallback_detail")
                else None
            ),
            learning_move=str(
                data.get("learning_move", "answer_question")
            ),
            claim_assessment=str(
                data.get("claim_assessment", "not_applicable")
            ),
            acknowledged_points=tuple(
                str(item) for item in data.get("acknowledged_points", [])
            ),
            correction_points=tuple(
                str(item) for item in data.get("correction_points", [])
            ),
            next_learning_question=(
                str(data["next_learning_question"])
                if data.get("next_learning_question")
                else None
            ),
            explanation_level=str(
                data.get("explanation_level", "foundational")
            ),
            adaptation_reasons=tuple(
                str(item) for item in data.get("adaptation_reasons", [])
            ),
        )


@dataclass
class LearningSession:
    session_id: str
    topic_id: str | None
    current_step: LearningStep
    baseline_conditions: dict[str, float] = field(default_factory=dict)
    comparison_conditions: dict[str, float] = field(default_factory=dict)
    changed_parameters: list[str] = field(default_factory=list)
    fixed_parameters: list[str] = field(default_factory=list)
    prediction_answers: list[AnswerRecord] = field(default_factory=list)
    observation_answers: list[AnswerRecord] = field(default_factory=list)
    followup_history: list[FollowupTurn] = field(default_factory=list)
    analysis_snapshot: dict[str, Any] = field(default_factory=dict)
    feedback_snapshot: dict[str, Any] = field(default_factory=dict)
    summary_snapshot: dict[str, Any] = field(default_factory=dict)
    dialogue_state: DialogueState = field(default_factory=DialogueState)
    understanding_level: UnderstandingLevel = UnderstandingLevel.UNKNOWN
    detected_misconceptions: list[str] = field(default_factory=list)
    completed_concepts: list[str] = field(default_factory=list)
    remaining_concepts: list[str] = field(default_factory=list)
    attempt_count: int = 0
    recommended_next_action: str | None = None
    error_code: str | None = None
    recovery_step: LearningStep | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    completed_at: str | None = None
    schema_version: str = "1.0"

    @classmethod
    def create(cls, topic: TopicConfig | None = None, *, now: str | None = None) -> "LearningSession":
        timestamp = now or utc_now()
        if topic is None:
            return cls(str(uuid4()), None, LearningStep.TOPIC_SELECTION, created_at=timestamp, updated_at=timestamp)
        changed = [name for name in topic.baseline_conditions if topic.baseline_conditions[name] != topic.comparison_conditions[name]]
        fixed = [name for name in topic.baseline_conditions if topic.baseline_conditions[name] == topic.comparison_conditions[name]]
        return cls(
            session_id=str(uuid4()),
            topic_id=topic.topic_id,
            current_step=LearningStep.INTRODUCTION,
            baseline_conditions=dict(topic.baseline_conditions),
            comparison_conditions=dict(topic.comparison_conditions),
            changed_parameters=changed,
            fixed_parameters=fixed,
            remaining_concepts=list(topic.expected_concepts),
            dialogue_state=DialogueState(current_topic=topic.topic_id),
            created_at=timestamp,
            updated_at=timestamp,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["current_step"] = self.current_step.value
        data["understanding_level"] = self.understanding_level.value
        data["recovery_step"] = self.recovery_step.value if self.recovery_step else None
        json.dumps(data, ensure_ascii=False, allow_nan=False)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LearningSession":
        if str(data.get("schema_version", "")) != "1.0":
            raise ValueError("unsupported_learning_session_schema")
        session_id = str(data["session_id"])
        UUID(session_id)
        followup_history = [
            FollowupTurn.from_dict(item)
            for item in data.get("followup_history", [])
        ]
        dialogue_state = (
            DialogueState.from_dict(data.get("dialogue_state"))
            if data.get("dialogue_state")
            else DialogueState.from_history(
                str(data["topic_id"]) if data.get("topic_id") else None,
                followup_history,
            )
        )
        session = cls(
            session_id=session_id,
            topic_id=str(data["topic_id"]) if data.get("topic_id") else None,
            current_step=LearningStep(data["current_step"]),
            baseline_conditions={str(key): float(value) for key, value in data.get("baseline_conditions", {}).items()},
            comparison_conditions={str(key): float(value) for key, value in data.get("comparison_conditions", {}).items()},
            changed_parameters=[str(item) for item in data.get("changed_parameters", [])],
            fixed_parameters=[str(item) for item in data.get("fixed_parameters", [])],
            prediction_answers=[AnswerRecord.from_dict(item) for item in data.get("prediction_answers", [])],
            observation_answers=[AnswerRecord.from_dict(item) for item in data.get("observation_answers", [])],
            followup_history=followup_history,
            analysis_snapshot=dict(data.get("analysis_snapshot", {})),
            feedback_snapshot=dict(data.get("feedback_snapshot", {})),
            summary_snapshot=dict(data.get("summary_snapshot", {})),
            dialogue_state=dialogue_state,
            understanding_level=UnderstandingLevel(data.get("understanding_level", "unknown")),
            detected_misconceptions=[str(item) for item in data.get("detected_misconceptions", [])],
            completed_concepts=[str(item) for item in data.get("completed_concepts", [])],
            remaining_concepts=[str(item) for item in data.get("remaining_concepts", [])],
            attempt_count=int(data.get("attempt_count", 0)),
            recommended_next_action=str(data["recommended_next_action"]) if data.get("recommended_next_action") else None,
            error_code=str(data["error_code"]) if data.get("error_code") else None,
            recovery_step=LearningStep(data["recovery_step"]) if data.get("recovery_step") else None,
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
            completed_at=str(data["completed_at"]) if data.get("completed_at") else None,
            schema_version="1.0",
        )
        if session.attempt_count < 0:
            raise ValueError("invalid_attempt_count")
        return session
