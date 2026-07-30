from __future__ import annotations

from collections.abc import Callable
from collections.abc import Mapping
from typing import Any

from .schemas import AnswerRecord, LearningSession, LearningStep, utc_now


class InvalidLearningTransition(RuntimeError):
    pass


TRANSITIONS: dict[LearningStep, frozenset[LearningStep]] = {
    LearningStep.TOPIC_SELECTION: frozenset({LearningStep.INTRODUCTION}),
    LearningStep.INTRODUCTION: frozenset({LearningStep.BASELINE_SETUP}),
    LearningStep.BASELINE_SETUP: frozenset({LearningStep.PREDICTION_QUESTION}),
    LearningStep.PREDICTION_QUESTION: frozenset({LearningStep.PREDICTION_SUBMITTED}),
    LearningStep.PREDICTION_SUBMITTED: frozenset({LearningStep.SIMULATION_RUNNING}),
    LearningStep.SIMULATION_RUNNING: frozenset({LearningStep.RESULT_READY}),
    LearningStep.RESULT_READY: frozenset({LearningStep.OBSERVATION_QUESTION}),
    LearningStep.OBSERVATION_QUESTION: frozenset({LearningStep.OBSERVATION_SUBMITTED}),
    LearningStep.OBSERVATION_SUBMITTED: frozenset({LearningStep.FEEDBACK_READY}),
    LearningStep.FEEDBACK_READY: frozenset({LearningStep.NEXT_EXPERIMENT, LearningStep.SESSION_COMPLETE}),
    LearningStep.NEXT_EXPERIMENT: frozenset({LearningStep.PREDICTION_QUESTION, LearningStep.SESSION_COMPLETE}),
    LearningStep.SESSION_COMPLETE: frozenset(),
    LearningStep.ERROR: frozenset(),
}


class LearningStateMachine:
    def __init__(self, clock: Callable[[], str] = utc_now) -> None:
        self.clock = clock

    def transition(self, session: LearningSession, target: LearningStep) -> LearningSession:
        if target not in TRANSITIONS[session.current_step]:
            raise InvalidLearningTransition(f"{session.current_step.value}->{target.value}")
        session.current_step = target
        session.updated_at = self.clock()
        session.error_code = None
        session.recovery_step = None
        if target is LearningStep.SESSION_COMPLETE:
            session.completed_at = session.updated_at
        return session

    def submit_prediction(self, session: LearningSession, question_id: str, raw_answer: Any) -> LearningSession:
        return self.submit_predictions(session, {question_id: raw_answer})

    def submit_predictions(self, session: LearningSession, answers: Mapping[str, Any]) -> LearningSession:
        if session.current_step is not LearningStep.PREDICTION_QUESTION:
            raise InvalidLearningTransition("prediction_submission_not_allowed")
        if not answers:
            raise InvalidLearningTransition("prediction_answers_required")
        submitted_at = self.clock()
        records = [AnswerRecord.create(question_id, raw_answer, submitted_at=submitted_at) for question_id, raw_answer in answers.items()]
        session.prediction_answers.extend(records)
        session.attempt_count += 1
        return self.transition(session, LearningStep.PREDICTION_SUBMITTED)

    def submit_observation(self, session: LearningSession, question_id: str, raw_answer: Any) -> LearningSession:
        return self.submit_observations(session, {question_id: raw_answer})

    def submit_observations(self, session: LearningSession, answers: Mapping[str, Any]) -> LearningSession:
        if session.current_step is not LearningStep.OBSERVATION_QUESTION:
            raise InvalidLearningTransition("observation_submission_not_allowed")
        if not answers:
            raise InvalidLearningTransition("observation_answers_required")
        submitted_at = self.clock()
        records = [AnswerRecord.create(question_id, raw_answer, submitted_at=submitted_at) for question_id, raw_answer in answers.items()]
        session.observation_answers.extend(records)
        return self.transition(session, LearningStep.OBSERVATION_SUBMITTED)

    def fail(self, session: LearningSession, error_code: str) -> LearningSession:
        if session.current_step in {LearningStep.ERROR, LearningStep.SESSION_COMPLETE}:
            raise InvalidLearningTransition("error_transition_not_allowed")
        session.recovery_step = session.current_step
        session.current_step = LearningStep.ERROR
        session.error_code = error_code
        session.updated_at = self.clock()
        return session

    def recover(self, session: LearningSession) -> LearningSession:
        if session.current_step is not LearningStep.ERROR or session.recovery_step is None:
            raise InvalidLearningTransition("session_is_not_recoverable")
        target = session.recovery_step
        session.current_step = target
        session.recovery_step = None
        session.error_code = None
        session.updated_at = self.clock()
        return session
