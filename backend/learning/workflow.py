from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from backend.explanation.usage import summarize_usage

from .analysis_schemas import LearningAnalysisContext
from .llm_service import LearningLLMService
from .schemas import LearningSession, LearningStep, TopicConfig
from .state_machine import LearningStateMachine
from .tutor_schemas import (
    AnswerEvaluation,
    LearningFeedback,
    LearningSessionSummary,
    NextActionDecision,
)


@dataclass(frozen=True)
class ObservationReview:
    evaluation: AnswerEvaluation
    feedback: LearningFeedback
    next_action: NextActionDecision
    summary: LearningSessionSummary
    provider_diagnostics: tuple[dict[str, Any], ...] = ()


def combine_evaluations(evaluations: list[AnswerEvaluation]) -> AnswerEvaluation:
    if not evaluations:
        raise ValueError("observation_evaluations_required")
    correct = tuple(dict.fromkeys(
        concept for item in evaluations for concept in item.correct_concepts
    ))
    missing = tuple(dict.fromkeys(
        concept
        for item in evaluations
        for concept in item.missing_concepts
        if concept not in correct
    ))
    misconceptions = tuple(dict.fromkeys(
        concept for item in evaluations for concept in item.detected_misconceptions
    ))
    unsupported = tuple(dict.fromkeys(
        claim for item in evaluations for claim in item.unsupported_claims
    ))
    levels = {item.understanding_level for item in evaluations}
    level = (
        "incorrect" if "incorrect" in levels
        else "partial" if "partial" in levels
        else "uncertain" if "uncertain" in levels
        else "correct"
    )
    strategy = {
        "correct": "reinforce",
        "partial": "hint",
        "incorrect": "correct",
        "uncertain": "hint",
    }[level]
    source = (
        "external_llm"
        if any(item.source == "external_llm" for item in evaluations)
        else "local"
    )
    return AnswerEvaluation(
        level,
        correct,
        missing,
        misconceptions,
        unsupported,
        strategy,
        "show_feedback",
        source,
    )


def review_observations(
    topic: TopicConfig,
    answers: Mapping[str, Any],
    context: LearningAnalysisContext,
    tutor: LearningLLMService,
    *,
    prediction_answers: Mapping[str, Any] | None = None,
) -> ObservationReview:
    usage_checkpoint = tutor.usage_checkpoint()
    expected_ids = {question.question_id for question in topic.observation_questions}
    if set(answers) != expected_ids:
        raise ValueError("observation_answer_set_mismatch")
    evaluations: list[AnswerEvaluation] = []
    if prediction_answers is not None:
        prediction_ids = {question.question_id for question in topic.prediction_questions}
        if set(prediction_answers) != prediction_ids:
            raise ValueError("prediction_answer_set_mismatch")
        evaluations.extend(
            tutor.evaluate_answer(
                topic,
                question,
                prediction_answers[question.question_id],
                context,
            )
            for question in topic.prediction_questions
        )
    evaluations.extend(
        tutor.evaluate_answer(topic, question, answers[question.question_id], context)
        for question in topic.observation_questions
    )
    combined = combine_evaluations(evaluations)
    feedback = tutor.generate_feedback(topic, combined, context)
    next_action = tutor.select_local_next_action(topic, combined)
    summary = tutor.summarize_session(topic, combined, context, next_action)
    return ObservationReview(
        combined,
        feedback,
        next_action,
        summary,
        tutor.usage_since(usage_checkpoint),
    )


def apply_observation_review(
    session: LearningSession,
    review: ObservationReview,
    state_machine: LearningStateMachine,
) -> None:
    if session.current_step is not LearningStep.OBSERVATION_SUBMITTED:
        raise ValueError("observation_review_state")
    LearningLLMService.apply_evaluation(session, review.evaluation)
    session.recommended_next_action = review.next_action.action_id
    session.feedback_snapshot = review.feedback.to_dict()
    session.feedback_snapshot["llm_usage"] = summarize_usage(
        review.provider_diagnostics
    )
    session.summary_snapshot = asdict(review.summary)
    state_machine.transition(session, LearningStep.FEEDBACK_READY)
