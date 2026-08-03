from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.learning import (
    ConditionValidationError,
    InMemorySessionRepository,
    InvalidLearningTransition,
    JsonSessionRepository,
    LearningSession,
    LearningStateMachine,
    LearningStep,
    compare_experiment_conditions,
    load_topic,
    load_topics,
    validate_model_conditions,
)
from backend.learning.session_repository import SessionStorageError


def _advance_to_prediction(machine: LearningStateMachine, session: LearningSession) -> None:
    machine.transition(session, LearningStep.BASELINE_SETUP)
    machine.transition(session, LearningStep.PREDICTION_QUESTION)


def test_sce_topic_is_structured_and_uses_verified_single_change() -> None:
    topic = load_topic("sce_channel_length")
    assert topic.topic_id == "sce_channel_length"
    assert {"channel_length", "dibl", "threshold_voltage"} <= set(topic.theory_concepts)
    assert topic.baseline_conditions["L"] == 700
    assert topic.comparison_conditions["L"] == 300
    comparison = compare_experiment_conditions(topic.baseline_conditions, topic.comparison_conditions)
    assert comparison.changed_parameters == ("L",)
    assert comparison.fixed_parameters == ("T", "B", "SD", "LDD")
    assert topic.prediction_questions[0].reason_required
    assert len(topic.observation_questions) == 2
    assert {item.action_id for item in topic.allowed_next_actions} == {
        "observe_potential_map", "retry_sce_prediction", "review_sce_theory",
    }
    assert load_topics()["sce_channel_length"] == topic


def test_oxide_topic_is_isolated_and_changes_only_verified_tox() -> None:
    topics = load_topics()
    assert set(topics) == {"sce_channel_length", "oxide_gate_control"}
    topic = topics["oxide_gate_control"]
    comparison = compare_experiment_conditions(
        topic.baseline_conditions,
        topic.comparison_conditions,
    )
    assert comparison.changed_parameters == ("T",)
    assert comparison.fixed_parameters == ("L", "B", "SD", "LDD")
    assert topic.baseline_conditions["T"] == 20
    assert topic.comparison_conditions["T"] == 10
    assert {"oxide_thickness", "transconductance", "electric_field"} <= set(
        topic.theory_concepts
    )
    assert all(
        question.question_id.startswith("oxide_")
        for question in (
            *topic.prediction_questions,
            *topic.observation_questions,
        )
    )

    repository = InMemorySessionRepository()
    sce_session = LearningSession.create(topics["sce_channel_length"])
    oxide_session = LearningSession.create(topic)
    repository.save(sce_session)
    repository.save(oxide_session)
    restored = repository.list_sessions()
    assert {item.topic_id for item in restored} == {
        "sce_channel_length",
        "oxide_gate_control",
    }
    assert sce_session.session_id != oxide_session.session_id


def test_condition_validation_separates_range_from_verified_values() -> None:
    continuous = {"L": 110, "T": 10, "B": 1e16, "SD": 1e20, "LDD": 1e18}
    assert validate_model_conditions(continuous)["L"] == 110
    try:
        validate_model_conditions(continuous, require_supported_value=True)
    except ConditionValidationError as error:
        assert str(error) == "unverified_parameter_value:L"
    else:
        raise AssertionError("an unverified case-study condition was accepted")

    for invalid, expected in (
        ({**continuous, "L": 99}, "outside_model_range:L"),
        ({**continuous, "B": 1e17}, "outside_model_range:B"),
        ({key: value for key, value in continuous.items() if key != "L"}, "invalid_parameter_set:missing=L"),
    ):
        try:
            validate_model_conditions(invalid)
        except ConditionValidationError as error:
            assert str(error) == expected
        else:
            raise AssertionError(f"invalid conditions accepted: {invalid}")


def test_experiment_requires_exactly_one_changed_parameter() -> None:
    topic = load_topic("sce_channel_length")
    multi_change = {**topic.comparison_conditions, "T": 20}
    try:
        compare_experiment_conditions(topic.baseline_conditions, multi_change)
    except ConditionValidationError as error:
        assert str(error) == "experiment_must_change_exactly_one_parameter"
    else:
        raise AssertionError("multi-parameter experiment accepted")


def test_learning_state_machine_runs_the_happy_path_and_blocks_duplicates() -> None:
    times = iter(f"2026-07-29T00:00:{second:02d}+00:00" for second in range(30))
    machine = LearningStateMachine(lambda: next(times))
    session = LearningSession.create(load_topic("sce_channel_length"), now="2026-07-29T00:00:00+00:00")
    assert session.current_step is LearningStep.INTRODUCTION
    assert session.changed_parameters == ["L"]
    assert session.remaining_concepts

    _advance_to_prediction(machine, session)
    machine.submit_prediction(session, "sce_pred_ion_ioff", {"selected": ["Ion 증가"], "reason": "채널이 짧아짐"})
    assert session.current_step is LearningStep.PREDICTION_SUBMITTED
    assert session.attempt_count == 1
    assert session.prediction_answers[0].raw_answer["selected"] == ["Ion 증가"]
    try:
        machine.submit_prediction(session, "sce_pred_ion_ioff", "duplicate")
    except InvalidLearningTransition as error:
        assert str(error) == "prediction_submission_not_allowed"
    else:
        raise AssertionError("duplicate prediction accepted")

    for step in (
        LearningStep.SIMULATION_RUNNING,
        LearningStep.RESULT_READY,
        LearningStep.OBSERVATION_QUESTION,
    ):
        machine.transition(session, step)
    machine.submit_observations(session, {
        "sce_obs_subthreshold": "300 nm",
        "sce_obs_tradeoff": {"selected": ["Ioff", "DIBL"], "reason": "곡선 이동"},
    })
    assert [answer.question_id for answer in session.observation_answers] == [
        "sce_obs_subthreshold", "sce_obs_tradeoff",
    ]
    machine.transition(session, LearningStep.FEEDBACK_READY)
    machine.transition(session, LearningStep.SESSION_COMPLETE)
    assert session.completed_at is not None
    try:
        machine.transition(session, LearningStep.NEXT_EXPERIMENT)
    except InvalidLearningTransition:
        pass
    else:
        raise AssertionError("completed session was reopened")


def test_learning_state_machine_recovers_to_the_previous_safe_step() -> None:
    machine = LearningStateMachine(lambda: "2026-07-29T00:00:01+00:00")
    session = LearningSession.create(load_topic("sce_channel_length"))
    _advance_to_prediction(machine, session)
    machine.submit_prediction(session, "sce_pred_ion_ioff", "Ion 증가")
    machine.transition(session, LearningStep.SIMULATION_RUNNING)
    machine.fail(session, "simulation_failed")
    assert session.current_step is LearningStep.ERROR
    assert session.recovery_step is LearningStep.SIMULATION_RUNNING
    machine.recover(session)
    assert session.current_step is LearningStep.SIMULATION_RUNNING
    assert session.error_code is None and session.recovery_step is None


def test_session_round_trip_preserves_raw_answers_and_enum_values() -> None:
    machine = LearningStateMachine(lambda: "2026-07-29T00:00:01+00:00")
    session = LearningSession.create(load_topic("sce_channel_length"), now="2026-07-29T00:00:00+00:00")
    _advance_to_prediction(machine, session)
    raw_answer = {"selected": ["Ion 증가", "Ioff 증가"], "reason": "Drain 영향"}
    machine.submit_prediction(session, "sce_pred_ion_ioff", raw_answer)
    restored = LearningSession.from_dict(json.loads(json.dumps(session.to_dict(), ensure_ascii=False)))
    assert restored.to_dict() == session.to_dict()
    assert restored.current_step is LearningStep.PREDICTION_SUBMITTED
    assert restored.prediction_answers[0].raw_answer == raw_answer


def test_session_v1_migrates_and_clone_preserves_learning_state() -> None:
    session = LearningSession.create(
        load_topic("sce_channel_length"),
        now="2026-07-29T00:00:00+00:00",
    )
    legacy = session.to_dict()
    legacy["schema_version"] = "1.0"
    legacy.pop("display_name")
    legacy.pop("ui_state")
    migrated = LearningSession.from_dict(legacy)
    assert migrated.schema_version == "2.0"
    assert migrated.display_name == "기존 학습 세션"
    assert migrated.ui_state == {}

    migrated.rename("SCE 복습", now="2026-07-29T00:01:00+00:00")
    migrated.remember_ui(
        result_view_tab="Field Map",
        completion_view_tab="AI 자유 질문",
        field_display="Electric field",
        unsupported="ignored",
    )
    clone = migrated.clone(now="2026-07-29T00:02:00+00:00")
    assert clone.session_id != migrated.session_id
    assert clone.display_name == "SCE 복습 복사본"
    assert clone.ui_state == migrated.ui_state
    assert clone.topic_id == migrated.topic_id
    assert clone.created_at == clone.updated_at == "2026-07-29T00:02:00+00:00"


def test_memory_and_json_repositories_return_restorable_copies() -> None:
    session = LearningSession.create(load_topic("sce_channel_length"))
    memory = InMemorySessionRepository()
    memory.save(session)
    session.topic_id = "mutated"
    restored = memory.load(session.session_id)
    assert restored is not None and restored.topic_id == "sce_channel_length"
    assert [item.session_id for item in memory.list_sessions()] == [restored.session_id]

    with TemporaryDirectory() as directory:
        repository = JsonSessionRepository(Path(directory))
        repository.save(restored)
        disk_session = repository.load(restored.session_id)
        assert disk_session is not None and disk_session.to_dict() == restored.to_dict()
        assert [item.session_id for item in repository.list_sessions()] == [restored.session_id]
        assert repository.load("00000000-0000-0000-0000-000000000000") is None
        repository.delete(restored.session_id)
        assert repository.load(restored.session_id) is None
        repository.delete(restored.session_id)

    memory.delete(restored.session_id)
    assert memory.load(restored.session_id) is None


def test_json_repository_rejects_invalid_ids_and_corrupt_sessions() -> None:
    with TemporaryDirectory() as directory:
        repository = JsonSessionRepository(Path(directory))
        try:
            repository.load("../escape")
        except SessionStorageError as error:
            assert str(error) == "invalid_session_id"
        else:
            raise AssertionError("unsafe session id accepted")

        session = LearningSession.create(load_topic("sce_channel_length"))
        path = Path(directory) / f"{session.session_id}.json"
        path.write_text("{not-json", encoding="utf-8")
        try:
            repository.load(session.session_id)
        except SessionStorageError as error:
            assert str(error) == "session_read_failed"
        else:
            raise AssertionError("corrupt session accepted")


def test_json_repository_recovers_last_valid_backup_and_skips_unrecoverable() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        repository = JsonSessionRepository(root)
        session = LearningSession.create(load_topic("sce_channel_length"))
        session.rename("첫 저장")
        repository.save(session)
        session.rename("두 번째 저장")
        repository.save(session)
        path = root / f"{session.session_id}.json"
        path.write_text("{broken-primary", encoding="utf-8")

        recovered = repository.load(session.session_id)
        assert recovered is not None
        assert recovered.display_name == "첫 저장"
        notices = repository.consume_recovery_notices()
        assert notices == [{
            "session_id": session.session_id,
            "code": "session_recovered_from_backup",
        }]
        assert json.loads(path.read_text(encoding="utf-8"))[
            "display_name"
        ] == "첫 저장"

        broken = LearningSession.create(load_topic("sce_channel_length"))
        (root / f"{broken.session_id}.json").write_text(
            "{unrecoverable",
            encoding="utf-8",
        )
        listed = repository.list_sessions()
        assert [item.session_id for item in listed] == [session.session_id]
        assert any(
            item["session_id"] == broken.session_id
            and item["code"] == "session_skipped_unrecoverable"
            for item in repository.consume_recovery_notices()
        )
