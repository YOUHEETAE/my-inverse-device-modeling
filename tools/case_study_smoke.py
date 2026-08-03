from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.learning import (
    LearningAnalysisContext,
    LearningLLMService,
    LearningSession,
    LearningStateMachine,
    LearningStep,
    JsonSessionRepository,
    apply_observation_review,
    audit_learning_session,
    load_topic,
    review_observations,
)
from backend.learning.experiment_runner import LearningExperimentRunner


PREDICTIONS = {
    "sce_pred_ion_ioff": {
        "selected": ["Ion 증가", "Ioff 증가"],
        "reason": "채널 길이 감소 시 구동 전류와 누설 전류가 함께 증가할 수 있다.",
    },
}
OBSERVATIONS = {
    "sce_obs_subthreshold": {"selected": ["300 nm"], "reason": ""},
    "sce_obs_tradeoff": {
        "selected": ["Ioff", "DIBL", "SS"],
        "reason": "300 nm 조건에서 Ioff, DIBL, SS가 모두 증가했다.",
    },
}
FOLLOWUPS = (
    ("current_result", "이번 결과에서 Vth가 왜 감소했나요?", "answer_question"),
    ("current_result", "그건 왜 그런가요?", "answer_question"),
    ("case_theory", "SCE가 정확히 무엇인가요?", "answer_question"),
    ("hypothetical", "PN 접합에서 접합 길이가 짧아지면 어떻게 되나요?", "clarify_meaning"),
    ("hypothetical", "Body doping을 높이면 DIBL이 줄어드나요?", "separate_prediction_from_result"),
    ("new_experiment", "L을 500 nm로 바꾸면 결과가 어떻게 나오는지 시뮬레이션해줘.", "separate_prediction_from_result"),
    ("current_result", "이 실험은 길이만 바꾼 거 맞잖아.", "confirm_experiment"),
    ("out_of_scope", "오늘 날씨가 어떤가요?", "answer_question"),
)


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


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    topic = load_topic("sce_channel_length")
    session = LearningSession.create(topic)
    machine = LearningStateMachine()
    tutor = LearningLLMService()

    machine.transition(session, LearningStep.BASELINE_SETUP)
    machine.transition(session, LearningStep.PREDICTION_QUESTION)
    machine.submit_predictions(session, PREDICTIONS)

    runner = LearningExperimentRunner.from_repository(REPOSITORY_ROOT)
    result = runner.execute_for_session(session, topic, machine)
    machine.transition(session, LearningStep.OBSERVATION_QUESTION)
    machine.submit_observations(session, OBSERVATIONS)
    review = review_observations(
        topic,
        OBSERVATIONS,
        result.learning_context,
        tutor,
        prediction_answers=PREDICTIONS,
    )
    apply_observation_review(session, review, machine)

    followup_report = []
    scenario_ok = True
    for expected_type, question, expected_move in FOLLOWUPS:
        followup = tutor.ask_followup(
            topic,
            question,
            result.learning_context,
            _history(session),
            session.dialogue_state.to_dict(),
            {
                "understanding_level": session.understanding_level.value,
                "completed_concepts": session.completed_concepts,
                "remaining_concepts": session.remaining_concepts,
                "detected_misconceptions": session.detected_misconceptions,
            },
        )
        tutor.record_followup(session, question, followup)
        current_ok = (
            bool(followup.evidence_ids)
            and followup.uses_current_result
            and followup.distinguishes_current_result
        ) if expected_type == "current_result" else (
            not followup.evidence_ids and not followup.uses_current_result
        )
        experiment_ok = (
            followup.needs_new_experiment
            if expected_type in {"hypothetical", "new_experiment"}
            else not followup.needs_new_experiment
        )
        learning_ok = (
            followup.learning_move == expected_move
            and (
                expected_move != "confirm_experiment"
                or (
                    followup.claim_assessment == "supported"
                    and bool(followup.acknowledged_points)
                )
            )
        )
        passed = (
            followup.question_type == expected_type
            and current_ok
            and experiment_ok
            and learning_ok
        )
        scenario_ok = scenario_ok and passed
        followup_report.append({
            "question": question,
            "expected_type": expected_type,
            "actual_type": followup.question_type,
            "source": followup.source,
            "evidence_ids": followup.evidence_ids,
            "theory_concepts": followup.theory_concepts,
            "needs_clarification": followup.needs_clarification,
            "needs_new_experiment": followup.needs_new_experiment,
            "learning_move": followup.learning_move,
            "claim_assessment": followup.claim_assessment,
            "passed": passed,
        })
    machine.transition(session, LearningStep.NEXT_EXPERIMENT)
    machine.transition(session, LearningStep.SESSION_COMPLETE)

    with TemporaryDirectory() as directory:
        repository = JsonSessionRepository(Path(directory))
        repository.save(session)
        restored = repository.load(session.session_id)
    restored_context = (
        LearningAnalysisContext.from_dict(restored.analysis_snapshot)
        if restored is not None and restored.analysis_snapshot
        else None
    )
    persistence_ok = (
        restored is not None
        and restored_context is not None
        and restored.current_step is LearningStep.SESSION_COMPLETE
        and len(restored.followup_history) == len(FOLLOWUPS)
        and restored.followup_history[-1].question_type == "out_of_scope"
        and restored.dialogue_state.student_claims[-1]["assessment"] == "supported"
        and restored_context.experiment == result.learning_context.experiment
        and {
            name: (change.before, change.after, change.evidence_id)
            for name, change in restored_context.electrical_changes.items()
        } == {
            name: (change.before, change.after, change.evidence_id)
            for name, change in result.learning_context.electrical_changes.items()
        }
    )

    metrics = result.learning_context.electrical_changes
    tutor_quality = audit_learning_session(
        session,
        result.learning_context,
    )
    report = {
        "topic_id": topic.topic_id,
        "conditions_nm": {
            "baseline": topic.baseline_conditions["L"],
            "comparison": topic.comparison_conditions["L"],
        },
        "session_step": session.current_step.value,
        "understanding_level": session.understanding_level.value,
        "recommended_next_action": session.recommended_next_action,
        "metrics": {
            name: {
                "before": metrics[name].before,
                "after": metrics[name].after,
                "direction": metrics[name].direction,
                "unit": metrics[name].unit,
                "evidence_id": metrics[name].evidence_id,
            }
            for name in ("ion", "ioff", "ss", "dibl")
        },
        "validation": {
            "question_scenarios": followup_report,
            "session_round_trip": persistence_ok,
            "tutor_quality": tutor_quality.to_dict(),
            "all_scenarios_passed": (
                scenario_ok and persistence_ok and tutor_quality.passed
            ),
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if (
        session.current_step is LearningStep.SESSION_COMPLETE
        and scenario_ok
        and persistence_ok
        and tutor_quality.passed
        and all(metrics[name].available for name in ("ion", "ioff", "ss", "dibl"))
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
