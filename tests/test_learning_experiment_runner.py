from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ai.field_map_model.inference import generate_gmsh_mesh
from backend.learning import LearningSession, LearningStateMachine, LearningStep, load_topic
from backend.learning.analysis_schemas import LearningAnalysisContext
from backend.learning.experiment_runner import (
    ConditionRun,
    ExperimentExecutionError,
    LearningExperimentResult,
    LearningExperimentRunner,
)


def _empty_context() -> LearningAnalysisContext:
    return LearningAnalysisContext(
        experiment={"changed_parameter": "L"},
        electrical_changes={},
        in_training_range=True,
        analysis_status="complete",
    )


def _result() -> LearningExperimentResult:
    condition = ConditionRun("Baseline", {}, None, None, None, {})
    return LearningExperimentResult(condition, condition, None, {}, _empty_context())


def _prediction_submitted_session():
    topic = load_topic("sce_channel_length")
    session = LearningSession.create(topic)
    machine = LearningStateMachine(lambda: "2026-07-29T00:00:00+00:00")
    machine.transition(session, LearningStep.BASELINE_SETUP)
    machine.transition(session, LearningStep.PREDICTION_QUESTION)
    machine.submit_prediction(session, "sce_pred_ion_ioff", "Ion과 Ioff 증가")
    return topic, session, machine


def test_runner_updates_session_only_after_successful_normalized_analysis() -> None:
    topic, session, machine = _prediction_submitted_session()
    runner = LearningExperimentRunner(None, None, Path("unused"))
    runner.execute = lambda _topic: _result()
    result = runner.execute_for_session(session, topic, machine)
    assert result.learning_context.analysis_status == "complete"
    assert session.current_step is LearningStep.RESULT_READY
    assert session.analysis_snapshot["experiment"]["changed_parameter"] == "L"


def test_runner_moves_failed_execution_to_recoverable_error_state() -> None:
    topic, session, machine = _prediction_submitted_session()
    runner = LearningExperimentRunner(None, None, Path("unused"))

    def fail(_topic):
        raise ExperimentExecutionError("field_analysis")

    runner.execute = fail
    try:
        runner.execute_for_session(session, topic, machine)
    except ExperimentExecutionError as error:
        assert error.stage == "field_analysis"
    else:
        raise AssertionError("failed experiment was reported as success")
    assert session.current_step is LearningStep.ERROR
    assert session.recovery_step is LearningStep.SIMULATION_RUNNING
    machine.recover(session)
    assert session.current_step is LearningStep.SIMULATION_RUNNING


def test_runner_rejects_wrong_topic_or_session_state_before_model_execution() -> None:
    topic = load_topic("sce_channel_length")
    session = LearningSession.create(topic)
    runner = LearningExperimentRunner(None, None, Path("unused"))
    for changed, expected in (
        (session, "session_state"),
        (LearningSession.create(), "topic_mismatch"),
    ):
        try:
            runner.execute_for_session(changed, topic, LearningStateMachine())
        except ExperimentExecutionError as error:
            assert error.stage == expected
        else:
            raise AssertionError(f"{expected} was accepted")


def test_gmsh_mesh_generation_supports_case_study_worker_thread() -> None:
    template = (
        Path(__file__).parents[1]
        / "tcad"
        / "data_extraction"
        / "base_case"
        / "gmsh_mos2d.geo"
    )
    with ThreadPoolExecutor(max_workers=1) as executor:
        mesh = executor.submit(generate_gmsh_mesh, 300.0, 10.0, template).result()
    assert len(mesh.node_xy_nm) > 0
    assert len(mesh.triangles) > 0
