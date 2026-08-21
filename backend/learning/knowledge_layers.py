from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from backend.explanation.evidence import METRIC_MAP, PREFERENCES
from tcad.data_extraction.parameter_extraction_core import (
    PARAMETER_EXTRACTION_DEFINITIONS,
)

from .analysis_schemas import LearningAnalysisContext
from .knowledge_base import TheoryConcept
from .schemas import TopicConfig


LEARNING_TO_EXTRACTION_METRIC = {
    "vth": "vth_high_v",
    "vth_low": "vth_low_v",
    "vth_high": "vth_high_v",
    "ion": "ion_ma_per_um",
    "ioff": "ioff_ma_per_um",
    "ss": "ss_mv_per_dec",
    "dibl": "dibl_gm_v_per_v",
    "gm_max": "gm_max_ms_per_um",
    "gds": "gds_ms_per_um",
    "ron": "ron_kohm_um",
    "lambda_clm": "lambda_per_v",
}

METRIC_PERFORMANCE_AREAS = {
    "vth": "threshold_target",
    "vth_low": "threshold_target",
    "vth_high": "threshold_target",
    "ion": "drive_performance",
    "ioff": "off_state_leakage",
    "ion_ioff_ratio": "current_separation",
    "ss": "subthreshold_control",
    "dibl": "short_channel_control",
    "gm_max": "gate_response",
    "gds": "output_saturation_control",
    "ron": "conduction_loss",
    "lambda_clm": "output_saturation_control",
}


def metric_directional_implication(direction: str, preference: str) -> str:
    """Interpret a direction within one metric, not overall device quality."""

    if preference == "context_dependent":
        return "design_target_required"
    if direction == "stable":
        return "no_clear_gain_or_loss"
    if direction not in {"increase", "decrease"}:
        return "indeterminate"
    favorable = (
        preference == "higher_is_better" and direction == "increase"
    ) or (
        preference == "lower_is_better" and direction == "decrease"
    )
    return "favorable_for_metric" if favorable else "unfavorable_for_metric"


def metric_preference(name: str) -> str:
    extraction_name = LEARNING_TO_EXTRACTION_METRIC.get(name, name)
    canonical_name = METRIC_MAP.get(extraction_name, extraction_name)
    return PREFERENCES.get(canonical_name, "context_dependent")


@dataclass(frozen=True)
class LearningKnowledgeLayers:
    experiment_facts: dict[str, Any]
    result_facts: dict[str, Any]
    metric_definitions: dict[str, dict[str, Any]]
    theory_facts: tuple[dict[str, Any], ...]
    authority_order: tuple[str, ...] = (
        "experiment_facts",
        "result_facts",
        "metric_definitions",
        "theory_facts",
    )

    def to_prompt_dict(self) -> dict[str, Any]:
        return asdict(self)


class LearningKnowledgeAssembler:
    @staticmethod
    def build(
        topic: TopicConfig,
        context: LearningAnalysisContext,
        theory: Iterable[TheoryConcept],
        *,
        requested_metrics: Iterable[str] = (),
        result_metrics: Iterable[str] | None = None,
    ) -> LearningKnowledgeLayers:
        experiment = dict(context.experiment)
        changed = tuple(experiment.get("changed_parameters", ()))
        if not changed and experiment.get("changed_parameter"):
            changed = (str(experiment["changed_parameter"]),)
        fixed = dict(experiment.get("fixed_parameters", {}))
        experiment_facts = {
            "baseline_conditions": dict(topic.baseline_conditions),
            "comparison_conditions": dict(topic.comparison_conditions),
            "changed_parameters": changed,
            "fixed_parameters": fixed,
            "controlled_single_parameter_comparison": (
                len(changed) == 1
                and not experiment.get("condition_results")
            ),
            "comparison_design": (
                experiment.get("comparison_design", topic.comparison_design)
            ),
            "in_training_range": context.in_training_range,
        }
        if experiment.get("condition_results"):
            experiment_facts["condition_results"] = list(
                experiment["condition_results"]
            )
        selected_results = (
            None
            if result_metrics is None
            else set(str(item) for item in result_metrics)
        )
        result_facts = {
            name: {
                "before": change.before,
                "after": change.after,
                "direction": change.direction,
                "unit": change.unit,
                "evidence_id": change.evidence_id,
                "performance_area": METRIC_PERFORMANCE_AREAS.get(
                    name,
                    "해당 전기적 특성",
                ),
                "directional_implication": metric_directional_implication(
                    change.direction,
                    metric_preference(name),
                ),
            }
            for name, change in context.electrical_changes.items()
            if change.available
            and (
                selected_results is None
                or name in selected_results
            )
        }
        requested = tuple(dict.fromkeys(str(item) for item in requested_metrics))
        names = requested or tuple(result_facts)
        definitions = {}
        for name in names:
            extraction_name = LEARNING_TO_EXTRACTION_METRIC.get(name, name)
            definition = PARAMETER_EXTRACTION_DEFINITIONS.get(extraction_name)
            if definition:
                definitions[name] = dict(definition)
        return LearningKnowledgeLayers(
            experiment_facts=experiment_facts,
            result_facts=result_facts,
            metric_definitions=definitions,
            theory_facts=tuple(item.to_prompt_dict() for item in theory),
        )
