from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ai.curve_model.inference import (
    FinalCurvePredictor,
    device_features,
    extract_electrical_parameters,
)
from ai.field_map_model.inference import (
    FieldMapPredictor,
    GeneratedMesh,
    generate_gmsh_mesh,
)
from ai.shared.field_data import GeneratedFieldMap
from backend.explanation.curve_analyzer import build_curve_payload
from backend.explanation.field_analyzer import build_field_payload
from backend.explanation.schemas import AnalysisPayload

from .analysis_adapter import LearningAnalysisAdapter
from .analysis_schemas import LearningAnalysisContext
from .schemas import LearningSession, LearningStep, TopicConfig
from .state_machine import LearningStateMachine
from .validation import compare_experiment_conditions


FIELD_DISPLAY_BY_OUTPUT = {
    "potential": "Potential",
    "electric_field": "Electric field",
}


class ExperimentExecutionError(RuntimeError):
    def __init__(self, stage: str) -> None:
        super().__init__(f"learning_experiment_failed:{stage}")
        self.stage = stage


@dataclass(frozen=True)
class ConditionRun:
    label: str
    conditions: dict[str, float]
    idvd: Any
    idvg: Any
    field_map: GeneratedFieldMap
    electrical_parameters: dict[str, float]


@dataclass(frozen=True)
class LearningExperimentResult:
    baseline: ConditionRun
    comparison: ConditionRun
    curve_analysis: AnalysisPayload
    field_analyses: dict[str, AnalysisPayload]
    learning_context: LearningAnalysisContext
    references: tuple[ConditionRun, ...] = ()

    @property
    def display_runs(self) -> tuple[ConditionRun, ...]:
        return (*self.references, self.baseline, self.comparison)


@dataclass
class LearningExperimentRunner:
    curve_predictor: FinalCurvePredictor
    field_predictor: FieldMapPredictor
    geo_template: Path
    adapter: LearningAnalysisAdapter = field(default_factory=LearningAnalysisAdapter)
    mesh_generator: Callable[[float, float, Path], GeneratedMesh] = generate_gmsh_mesh
    mesh_cache: dict[tuple[float, float], GeneratedMesh] = field(default_factory=dict)

    @classmethod
    def from_repository(cls, repository_root: Path) -> "LearningExperimentRunner":
        root = Path(repository_root)
        return cls(
            curve_predictor=FinalCurvePredictor(root / "ai/model_artifacts/curve_model/final/pca_xgboost"),
            field_predictor=FieldMapPredictor(root / "ai/model_artifacts/field_map_model/final/coordinate_mlp_physics"),
            geo_template=root / "tcad/data_extraction/base_case/gmsh_mos2d.geo",
        )

    @staticmethod
    def _config(conditions: dict[str, float]) -> dict[str, str]:
        return {name: format(value, ".15g") for name, value in conditions.items()}

    def _mesh(self, conditions: dict[str, float]) -> GeneratedMesh:
        key = (conditions["L"], conditions["T"])
        mesh = self.mesh_cache.get(key)
        if mesh is None:
            mesh = self.mesh_generator(conditions["L"], conditions["T"], self.geo_template)
            self.mesh_cache[key] = mesh
        return mesh

    def _run_condition(self, label: str, conditions: dict[str, float]) -> ConditionRun:
        config = self._config(conditions)
        features = device_features(config)
        idvd = self.curve_predictor.predict("idvd", features)
        idvg = self.curve_predictor.predict("idvg", features)
        mesh = self._mesh(conditions)
        field_prediction = self.field_predictor.predict(
            mesh,
            conditions["L"],
            conditions["T"],
            conditions["B"],
            conditions["SD"],
            conditions["LDD"],
        )
        field_map = GeneratedFieldMap(
            mesh,
            field_prediction,
            conditions["L"],
            conditions["T"],
            conditions["B"],
            conditions["SD"],
            conditions["LDD"],
        )
        electrical_parameters = extract_electrical_parameters(idvd, idvg)
        ion = electrical_parameters.get("ion_ma_per_um")
        ioff = electrical_parameters.get("ioff_ma_per_um")
        if (
            ion is not None
            and ioff is not None
            and math.isfinite(float(ion))
            and math.isfinite(float(ioff))
            and float(ioff) != 0.0
        ):
            electrical_parameters["ion_ioff_ratio"] = float(ion) / float(ioff)
        return ConditionRun(
            label=label,
            conditions=dict(conditions),
            idvd=idvd,
            idvg=idvg,
            field_map=field_map,
            electrical_parameters=electrical_parameters,
        )

    def execute(self, topic: TopicConfig) -> LearningExperimentResult:
        try:
            comparison = compare_experiment_conditions(
                topic.baseline_conditions,
                topic.comparison_conditions,
                require_single_change=True,
            )
        except (TypeError, ValueError) as error:
            raise ExperimentExecutionError("condition_validation") from error
        if tuple(comparison.changed_parameters) != ("L",) and topic.topic_id == "sce_channel_length":
            raise ExperimentExecutionError("condition_validation")
        unknown_outputs = set(topic.required_outputs) - {"idvd", "idvg", *FIELD_DISPLAY_BY_OUTPUT}
        if unknown_outputs:
            raise ExperimentExecutionError("required_output_validation")

        stage = "prediction"
        try:
            references = tuple(
                self._run_condition(reference.label, dict(reference.conditions))
                for reference in topic.reference_conditions
            )
            baseline = self._run_condition(
                topic.baseline_label,
                dict(topic.baseline_conditions),
            )
            comparison_run = self._run_condition(
                topic.comparison_label,
                dict(topic.comparison_conditions),
            )
            configs = [self._config(baseline.conditions), self._config(comparison_run.conditions)]
            curve_results = [
                (baseline.label, baseline.idvd, baseline.idvg),
                (comparison_run.label, comparison_run.idvd, comparison_run.idvg),
            ]
            stage = "curve_analysis"
            curve_analysis = build_curve_payload(curve_results, configs)
            stage = "field_analysis"
            field_outputs = [
                (baseline.label, baseline.field_map),
                (comparison_run.label, comparison_run.field_map),
            ]
            field_analyses = {
                output_name: build_field_payload(
                    field_outputs,
                    display,
                    "Auto",
                    "Robust 1-99%",
                )
                for output_name, display in (
                    (name, FIELD_DISPLAY_BY_OUTPUT[name])
                    for name in topic.required_outputs
                    if name in FIELD_DISPLAY_BY_OUTPUT
                )
            }
            stage = "analysis_adapter"
            context = self.adapter.normalize(
                baseline_conditions=baseline.conditions,
                comparison_conditions=comparison_run.conditions,
                curve_analysis=curve_analysis,
                field_analyses=field_analyses,
            )
            experiment = dict(context.experiment)
            experiment["display_electrical_parameters"] = {
                "baseline": {
                    "label": baseline.label,
                    "values": dict(baseline.electrical_parameters),
                },
                "comparison": {
                    "label": comparison_run.label,
                    "values": dict(comparison_run.electrical_parameters),
                },
            }
            if references:
                experiment["comparison_design"] = topic.comparison_design
                experiment["condition_results"] = [
                    {
                        "condition_id": reference.condition_id,
                        "label": run.label,
                        "conditions": dict(run.conditions),
                        "electrical_parameters": dict(
                            run.electrical_parameters
                        ),
                    }
                    for reference, run in zip(
                        topic.reference_conditions,
                        references,
                    )
                ] + [
                    {
                        "condition_id": "baseline",
                        "label": baseline.label,
                        "conditions": dict(baseline.conditions),
                        "electrical_parameters": dict(
                            baseline.electrical_parameters
                        ),
                    },
                    {
                        "condition_id": "comparison",
                        "label": comparison_run.label,
                        "conditions": dict(comparison_run.conditions),
                        "electrical_parameters": dict(
                            comparison_run.electrical_parameters
                        ),
                    },
                ]
            context = LearningAnalysisContext(
                experiment=experiment,
                electrical_changes=context.electrical_changes,
                curve_observations=context.curve_observations,
                field_observations=context.field_observations,
                validated_observations=context.validated_observations,
                warnings=context.warnings,
                in_training_range=context.in_training_range,
                analysis_status=context.analysis_status,
                source_schema_versions=context.source_schema_versions,
            )
            return LearningExperimentResult(
                baseline=baseline,
                comparison=comparison_run,
                curve_analysis=curve_analysis,
                field_analyses=field_analyses,
                learning_context=context,
                references=references,
            )
        except ExperimentExecutionError:
            raise
        except Exception as error:
            raise ExperimentExecutionError(stage) from error

    def execute_for_session(
        self,
        session: LearningSession,
        topic: TopicConfig,
        state_machine: LearningStateMachine,
    ) -> LearningExperimentResult:
        if session.topic_id != topic.topic_id:
            raise ExperimentExecutionError("topic_mismatch")
        if session.current_step is not LearningStep.PREDICTION_SUBMITTED:
            raise ExperimentExecutionError("session_state")
        if (
            session.baseline_conditions != topic.baseline_conditions
            or session.comparison_conditions != topic.comparison_conditions
        ):
            raise ExperimentExecutionError("session_conditions")
        state_machine.transition(session, LearningStep.SIMULATION_RUNNING)
        try:
            result = self.execute(topic)
        except ExperimentExecutionError as error:
            state_machine.fail(session, error.args[0])
            raise
        session.analysis_snapshot = result.learning_context.to_dict()
        state_machine.transition(session, LearningStep.RESULT_READY)
        return result
