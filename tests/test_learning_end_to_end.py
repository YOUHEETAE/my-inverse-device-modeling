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
        "sce_pred_ion": {
            "selected": ["증가"],
            "reason": "채널이 짧아지면 구동 전류가 증가할 수 있다.",
        },
        "sce_pred_ioff": {
            "selected": ["증가"],
            "reason": "Drain의 장벽 제어 영향으로 누설 전류가 증가할 수 있다.",
        },
        "sce_pred_dibl": {
            "selected": ["DIBL 증가"],
            "reason": "Drain bias가 Source 장벽과 Vth에 미치는 영향을 나타내는 지표다.",
        },
    }
    observations = {
        "sce_obs_subthreshold": {
            "selected": ["300 nm"],
            "reason": "Drain 전위가 Source 측 장벽까지 영향을 주어 전류가 더 이른 Vg에서 증가한다.",
        },
        "sce_obs_tradeoff": {
            "selected": [
                "Ioff 증가 — 고정된 off-bias에서 누설 전류가 커졌다",
                "DIBL 증가 — Drain bias에 대한 Channel 장벽과 Vth의 민감도가 커졌다",
                "SS 증가 — subthreshold 전류 한 decade를 조절하는 데 더 큰 Gate 전압이 필요해졌다",
            ],
            "reason": "세 지표의 정의와 실제 증가 방향을 연결했다.",
        },
        "sce_obs_field_coupling": {
            "selected": [
                "Drain 쪽 전위 영향이 Channel을 따라 Source 장벽 방향으로 더 깊게 이어져 낮은 Gate bias의 장벽 제어가 약해졌다"
            ],
            "reason": "Drain 결합의 공간 분포가 DIBL과 Ioff 증가를 뒷받침한다.",
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
    assert "llm_usage" in restored.feedback_snapshot
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


def test_prediction_difference_does_not_lower_observation_understanding() -> None:
    topic = load_topic("sce_channel_length")
    context = _real_model_context()
    predictions, observations = _correct_answers()
    predictions["sce_pred_ion"] = {
        "selected": ["감소"],
        "reason": "현재 결과를 보기 전에는 저항 외 조건의 영향도 가능하다고 예상했다.",
    }

    review = review_observations(
        topic,
        observations,
        context,
        LearningLLMService(),
        prediction_answers=predictions,
    )

    assert review.evaluation.understanding_level == "correct"
    assert "ion_can_increase" not in review.evaluation.missing_concepts
    assert not review.evaluation.detected_misconceptions
