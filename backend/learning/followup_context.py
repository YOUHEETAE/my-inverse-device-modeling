from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from .analysis_schemas import LearningAnalysisContext
from .intent_interpreter import QuestionIntent
from .knowledge_layers import LearningKnowledgeLayers
from .question_router import QuestionRoute
from .response_planner import LearningResponsePlan


_CONCEPT_METRICS = {
    "threshold_voltage": ("vth", "vth_low", "vth_high"),
    "on_current": ("ion",),
    "off_current": ("ioff",),
    "subthreshold_swing": ("ss",),
    "dibl": ("dibl",),
    "transconductance": ("gm_max",),
    "output_conductance": ("gds",),
    "on_resistance": ("ron",),
}
_BROAD_RESULT_CONCEPTS = {
    "channel_length",
    "short_channel_effect",
    "source_drain_doping",
    "ldd",
    "oxide_thickness",
    "design_target",
}
_FIELD_CONCEPTS = {
    "potential",
    "electric_field",
    "source_barrier",
    "dibl",
    "short_channel_effect",
    "punch_through",
    "depletion_region",
    "source_drain_doping",
    "ldd",
}
_DIALOGUE_KEYS = (
    "current_topic",
    "current_focus",
    "referenced_result",
    "last_explained_concept",
    "pending_question",
    "open_experiment_request",
    "turn_count",
)
FOLLOWUP_PROMPT_BYTE_BUDGET = 16_500


def select_result_metrics(
    route: QuestionRoute,
    intent: QuestionIntent | None,
    context: LearningAnalysisContext,
) -> tuple[str, ...]:
    """Select only result metrics needed to answer this turn."""

    if not route.uses_current_result:
        return ()
    requested = list(intent.requested_metrics if intent else ())
    concepts = tuple(dict.fromkeys(
        (
            *route.matched_concepts,
            *(intent.target_concepts if intent else ()),
        )
    ))
    for concept in concepts:
        requested.extend(_CONCEPT_METRICS.get(concept, ()))
    available = tuple(
        name
        for name, change in context.electrical_changes.items()
        if change.available
    )
    if (
        route.aggregate_result
        or not requested
        or (
            route.answer_structure == "parameter_by_parameter"
            and set(concepts).intersection(_BROAD_RESULT_CONCEPTS)
        )
    ):
        return available
    expanded = []
    for name in requested:
        if name == "vth":
            expanded.extend(("vth", "vth_low", "vth_high"))
        else:
            expanded.append(name)
    selected = set(expanded)
    return tuple(name for name in available if name in selected)


def select_definition_metrics(
    route: QuestionRoute,
    intent: QuestionIntent | None,
) -> tuple[str, ...]:
    requested = list(intent.requested_metrics if intent else ())
    concepts = tuple(dict.fromkeys(
        (
            *route.matched_concepts,
            *(intent.target_concepts if intent else ()),
        )
    ))
    for concept in concepts:
        requested.extend(_CONCEPT_METRICS.get(concept, ()))
    # A generic Vth definition is backed by the high-Vd extraction contract.
    normalized = (
        "vth" if name in {"vth_low", "vth_high"} else name
        for name in requested
    )
    return tuple(dict.fromkeys(normalized))


def compact_experiment_facts(
    facts: dict[str, Any],
    route: QuestionRoute,
) -> dict[str, Any]:
    if route.question_type in {"case_theory", "adjacent_theory", "out_of_scope"}:
        return {
            "changed_parameters": facts.get("changed_parameters", ()),
            "controlled_single_parameter_comparison": facts.get(
                "controlled_single_parameter_comparison", False
            ),
        }
    return dict(facts)


def compact_knowledge_layers(
    layers: LearningKnowledgeLayers,
    route: QuestionRoute,
) -> dict[str, Any]:
    return {
        "authority_order": layers.authority_order,
        "experiment_facts": compact_experiment_facts(
            layers.experiment_facts,
            route,
        ),
        "result_facts": layers.result_facts,
        "metric_definitions": layers.metric_definitions,
        # This is the single theory representation. Do not duplicate it under
        # another top-level payload key.
        "theory_facts": layers.theory_facts,
    }


def _compact_numeric_evidence(value: Any) -> Any:
    """Keep scalar summaries while excluding curve/field arrays."""

    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            compact = _compact_numeric_evidence(item)
            if compact not in (None, {}, []):
                result[str(key)] = compact
            if len(result) >= 12:
                break
        return result
    if isinstance(value, (list, tuple)):
        scalar = [
            item
            for item in value
            if item is None or isinstance(item, (bool, int, float, str))
        ]
        return scalar[:8] if len(scalar) <= 8 else []
    return None


def _compact_observation(item: Any) -> dict[str, Any]:
    result = {
        "source": item.source,
        "evidence_id": item.evidence_id,
        "quantity": item.quantity,
        "observation": item.observation,
        "confidence": item.confidence,
    }
    if item.field_display:
        result["field_display"] = item.field_display
    if item.region:
        result["region"] = item.region
    numeric = _compact_numeric_evidence(item.numeric_evidence)
    if numeric:
        result["numeric_evidence"] = numeric
    return result


def compact_simulation_facts(
    context: LearningAnalysisContext,
    route: QuestionRoute,
    result_metrics: Iterable[str],
) -> dict[str, Any]:
    """Return non-duplicated observations relevant to the routed question."""

    result = {
        "analysis_status": context.analysis_status,
        "in_training_range": context.in_training_range,
    }
    if not route.uses_current_result:
        result["current_result_used"] = False
        return result

    metrics = set(result_metrics)
    concepts = set(route.matched_concepts)
    broad = (
        route.aggregate_result
        or bool(concepts.intersection(_BROAD_RESULT_CONCEPTS))
    )
    curve = [
        _compact_observation(item)
        for item in context.curve_observations
        if broad
        or item.quantity in metrics
        or (
            item.quantity == "drain_current"
            and metrics.intersection({"ion", "ioff", "ss"})
        )
    ][:6]
    field = [
        _compact_observation(item)
        for item in context.field_observations
        if broad
        or concepts.intersection(_FIELD_CONCEPTS)
        or item.field_display in concepts
        or item.quantity in concepts
    ][:6]
    if curve:
        result["curve_observations"] = curve
    if field:
        result["field_observations"] = field
    selected_ids = {
        item["evidence_id"]
        for item in (*curve, *field)
        if item.get("evidence_id")
    }
    validated = [
        {
            "conclusion_id": item.get("conclusion_id"),
            "supporting_evidence_ids": [
                str(evidence_id)
                for evidence_id in item.get(
                    "supporting_evidence_ids", []
                )
                if str(evidence_id) in selected_ids
            ],
        }
        for item in context.validated_observations
        if selected_ids.intersection(
            str(evidence_id)
            for evidence_id in item.get("supporting_evidence_ids", [])
        )
    ][:6]
    if validated:
        result["validated_observations"] = validated
    relevant_warnings = [
        {
            "warning_type": item.warning_type,
            "severity": item.severity,
            "affected_quantities": item.affected_quantities,
            "affected_regions": item.affected_regions,
        }
        for item in context.warnings
        if not item.affected_quantities
        or metrics.intersection(item.affected_quantities)
    ][:4]
    if relevant_warnings:
        result["warnings"] = relevant_warnings
    return result


def compact_history(
    history: list[dict[str, Any]],
    route: QuestionRoute,
    intent: QuestionIntent | None,
    response_plan: LearningResponsePlan,
) -> list[dict[str, Any]]:
    needs_raw_context = (
        route.inherited_context
        or bool(intent and intent.references_previous)
        or response_plan.dialogue_move
        in {"evaluate_claim", "acknowledge_correction", "confirm_experiment"}
    )
    return history[-2:] if needs_raw_context else []


def compact_dialogue_state(
    dialogue_state: dict[str, Any] | None,
    response_plan: LearningResponsePlan,
) -> dict[str, Any]:
    source = dict(dialogue_state or {})
    result = {
        key: source[key]
        for key in _DIALOGUE_KEYS
        if source.get(key) not in (None, "", [], {})
    }
    if (
        response_plan.connect_to_previous_turn
        or response_plan.dialogue_move in {
        "evaluate_claim",
        "acknowledge_correction",
        "confirm_experiment",
        }
    ):
        result["student_claims"] = [
            dict(item)
            for item in source.get("student_claims", [])
            if isinstance(item, dict)
        ][-2:]
    return result


def compact_answer_plan(
    response_plan: LearningResponsePlan,
) -> dict[str, Any]:
    result = response_plan.to_dict()
    prior_claims = list(result.pop("prior_claims", ()) or ())
    if (
        response_plan.connect_to_previous_turn
        or response_plan.dialogue_move in {
        "evaluate_claim",
        "acknowledge_correction",
        "confirm_experiment",
        }
    ):
        result["prior_claims"] = prior_claims[-2:]
    result["write_cohesive_korean"] = True
    result["depth_policy"] = (
        "질문에 직접 답하되 정의, 물리 과정, 결과, 조건 의존성 및 "
        "Case 연결 중 관련된 요소를 충분히 설명한다."
    )
    return result


def selected_evidence_ids(
    context: LearningAnalysisContext,
    route: QuestionRoute,
    result_facts: dict[str, Any],
    simulation_facts: dict[str, Any],
) -> tuple[str, ...]:
    if not route.uses_current_result:
        return ()
    selected = {
        str(item["evidence_id"])
        for item in result_facts.values()
        if item.get("evidence_id")
    }
    for group in ("curve_observations", "field_observations"):
        selected.update(
            str(item["evidence_id"])
            for item in simulation_facts.get(group, [])
            if item.get("evidence_id")
        )
    for item in simulation_facts.get("validated_observations", []):
        selected.update(
            str(evidence_id)
            for evidence_id in item.get("supporting_evidence_ids", [])
        )
    if context.experiment:
        selected.add("experiment:conditions")
    return tuple(sorted(selected))


def fit_followup_prompt_budget(
    payload: dict[str, Any],
    build_prompt: Any,
    *,
    maximum_bytes: int = FOLLOWUP_PROMPT_BYTE_BUDGET,
) -> dict[str, Any]:
    """Bound free-tier input without cutting the user's question or facts.

    Rich metric definitions and verified result facts have priority. Only
    repeated explanatory detail and optional navigation metadata are reduced.
    """

    result = deepcopy(payload)

    def size() -> int:
        system, user = build_prompt(result)
        return len((system + user).encode("utf-8"))

    if size() <= maximum_bytes:
        return result

    layers = dict(result.get("knowledge_layers", {}))
    theory = []
    for item in layers.get("theory_facts", ()):
        value = dict(item)
        theory.append({
            "concept_id": value.get("concept_id"),
            "title": value.get("title"),
            "summary": value.get("summary"),
            "principles": tuple(value.get("principles", ()))[:2],
            "general_effects": tuple(value.get("general_effects", ()))[:2],
            "case_connection": value.get("case_connection"),
            "caveats": tuple(value.get("caveats", ()))[:1],
        })
    layers["theory_facts"] = tuple(theory)
    result["knowledge_layers"] = layers
    if size() <= maximum_bytes:
        return result

    # Action descriptions are useful only when an action is selected. IDs are
    # sufficient for answer validation under a tight input budget.
    result["allowed_next_actions"] = [
        {"action_id": item.get("action_id")}
        for item in result.get("allowed_next_actions", ())
        if isinstance(item, dict) and item.get("action_id")
    ]
    result["conversation_history"] = list(
        result.get("conversation_history", ())
    )[-1:]
    if size() <= maximum_bytes:
        return result

    # Seed concepts are ordered before graph neighbours by the retriever.
    layers["theory_facts"] = tuple(theory[:6])
    result["knowledge_layers"] = layers
    if size() <= maximum_bytes:
        return result

    simulation = dict(result.get("simulation_facts", {}))
    simulation.pop("validated_observations", None)
    simulation.pop("warnings", None)
    result["simulation_facts"] = simulation
    layers["theory_facts"] = tuple(theory[:4])
    result["knowledge_layers"] = layers
    return result
