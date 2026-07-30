from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.learning import (
    JsonSessionRepository,
    LearningAnalysisContext,
    LearningLLMService,
    LearningSession,
    LearningStateMachine,
    LearningStep,
    apply_observation_review,
    load_topic,
    review_observations,
)
from backend.learning.experiment_runner import (
    ConditionRun,
    LearningExperimentResult,
    LearningExperimentRunner,
)


FIXTURE = Path(__file__).parent / "fixtures" / "learning" / "sce_channel_length_analysis.json"


def _real_model_context() -> LearningAnalysisContext:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return LearningAnalysisContext.from_dict(data["learning_context"])


def _result(context: LearningAnalysisContext) -> LearningExperimentResult:
    baseline = ConditionRun("Baseline", {"L": 700.0}, None, None, None, {})
    comparison = ConditionRun("Comparison", {"L": 300.0}, None, None, None, {})
    return LearningExperimentResult(baseline, comparison, None, {}, context)


def _correct_answers() -> tuple[dict, dict]:
    predictions = {
        "sce_pred_ion_ioff": {
            "selected": ["Ion 증가", "Ioff 증가"],
            "reason": "채널이 짧아지면 구동 전류와 누설 전류가 함께 증가할 수 있다.",
        },
    }
    observations = {
        "sce_obs_subthreshold": {"selected": ["300 nm"], "reason": ""},
        "sce_obs_tradeoff": {
            "selected": ["Ioff", "DIBL", "SS"],
            "reason": "300 nm 조건에서 세 지표가 모두 증가했다.",
        },
    }
    return predictions, observations


def test_complete_case_journey_persists_feedback_followup_and_completion() -> None:
    topic = load_topic("sce_channel_length")
    context = _real_model_context()
    predictions, observations = _correct_answers()
    machine = LearningStateMachine()
    tutor = LearningLLMService()
    session = LearningSession.create(topic)

    machine.transition(session, LearningStep.BASELINE_SETUP)
    machine.transition(session, LearningStep.PREDICTION_QUESTION)
    machine.submit_predictions(session, predictions)

    runner = LearningExperimentRunner(None, None, Path("unused"))
    runner.execute = lambda _topic: _result(context)
    runner.execute_for_session(session, topic, machine)
    assert session.current_step is LearningStep.RESULT_READY

    machine.transition(session, LearningStep.OBSERVATION_QUESTION)
    machine.submit_observations(session, observations)
    review = review_observations(
        topic,
        observations,
        context,
        tutor,
        prediction_answers=predictions,
    )
    apply_observation_review(session, review, machine)
    assert session.current_step is LearningStep.FEEDBACK_READY
    assert session.understanding_level.value == "correct"
    assert {"ion_can_increase", "ioff_increases", "dibl_increases", "ss_increases"} <= set(
        session.completed_concepts
    )
    assert review.next_action.action_id in {
        action.action_id for action in topic.allowed_next_actions
    }

    response = tutor.ask_followup(
        topic,
        "그럼 여기서 SCE가 DIBL에 주는 영향은 뭔가요?",
        context,
    )
    tutor.record_followup(session, "그럼 여기서 SCE가 DIBL에 주는 영향은 뭔가요?", response)
    assert response.question_type == "current_result"
    assert response.evidence_ids

    machine.transition(session, LearningStep.NEXT_EXPERIMENT)
    machine.transition(session, LearningStep.SESSION_COMPLETE)
    with TemporaryDirectory() as directory:
        repository = JsonSessionRepository(Path(directory))
        repository.save(session)
        restored = repository.load(session.session_id)

    assert restored is not None
    assert restored.current_step is LearningStep.SESSION_COMPLETE
    assert restored.feedback_snapshot["evidence"]
    assert restored.summary_snapshot["headline"]
    assert restored.followup_history[-1].evidence_ids == response.evidence_ids
    assert restored.completed_at is not None


def test_review_rejects_incomplete_answer_sets_before_feedback() -> None:
    topic = load_topic("sce_channel_length")
    context = _real_model_context()
    predictions, observations = _correct_answers()
    observations.pop("sce_obs_tradeoff")
    try:
        review_observations(
            topic,
            observations,
            context,
            LearningLLMService(),
            prediction_answers=predictions,
        )
    except ValueError as error:
        assert str(error) == "observation_answer_set_mismatch"
    else:
        raise AssertionError("incomplete observation answers were accepted")
