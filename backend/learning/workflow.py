from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any, Mapping

from backend.explanation.usage import summarize_usage

from .analysis_schemas import LearningAnalysisContext
from .answer_evaluation import parse_answer
from .llm_service import LearningLLMService
from .schemas import AnswerRecord, LearningSession, LearningStep, QuestionSpec, TopicConfig
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


def as_prediction_reflection(
    evaluation: AnswerEvaluation,
) -> AnswerEvaluation:
    """Keep recognized prediction concepts without grading a hypothesis."""

    return AnswerEvaluation(
        understanding_level="correct",
        correct_concepts=evaluation.correct_concepts,
        missing_concepts=(),
        detected_misconceptions=(),
        unsupported_claims=(),
        feedback_strategy="reinforce",
        recommended_next_action="show_feedback",
        source=evaluation.source,
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
            as_prediction_reflection(
                tutor.evaluate_answer(
                    topic,
                    question,
                    prediction_answers[question.question_id],
                    context,
                )
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


def question_verdict(question: QuestionSpec, raw_answer: Any) -> str:
    """고른 답이 정답과 얼마나 겹치는지. Tk 앱의 _question_verdict와 같은 계산이다.

    집합 비교라 LLM을 부르지 않는다. 채점 결과를 하나로 합치기 전에 문항마다
    남겨두려는 것으로, 요약 화면이 "어느 예측이 맞았나"를 보여주려면 이 값이
    있어야 한다 — 화면에는 정답 자체를 내려보내지 않기 때문이다.
    """
    selected = set(parse_answer(raw_answer)[0]) & set(question.options)
    correct = set(question.correct_options)
    if not correct:
        return "unknown"
    if selected == correct:
        return "match"
    return "partial" if selected & correct else "different"


def _with_verdicts(
    records: list[AnswerRecord], questions: tuple[QuestionSpec, ...]
) -> list[AnswerRecord]:
    specs = {question.question_id: question for question in questions}
    updated = []
    for record in records:
        question = specs.get(record.question_id)
        if question is None or record.evaluation is not None:
            updated.append(record)
            continue
        updated.append(replace(
            record,
            evaluation={"verdict": question_verdict(question, record.raw_answer)},
        ))
    return updated


def apply_observation_review(
    session: LearningSession,
    review: ObservationReview,
    state_machine: LearningStateMachine,
    topic: TopicConfig | None = None,
) -> None:
    if session.current_step is not LearningStep.OBSERVATION_SUBMITTED:
        raise ValueError("observation_review_state")
    if topic is not None:
        # 합쳐진 평가만 남기면 문항별로 무엇이 맞았는지 알 수 없게 된다.
        session.prediction_answers = _with_verdicts(
            session.prediction_answers, topic.prediction_questions
        )
        session.observation_answers = _with_verdicts(
            session.observation_answers, topic.observation_questions
        )
    LearningLLMService.apply_evaluation(session, review.evaluation)
    session.recommended_next_action = review.next_action.action_id
    session.feedback_snapshot = review.feedback.to_dict()
    session.feedback_snapshot["llm_usage"] = summarize_usage(
        review.provider_diagnostics
    )
    session.summary_snapshot = asdict(review.summary)
    state_machine.transition(session, LearningStep.FEEDBACK_READY)
