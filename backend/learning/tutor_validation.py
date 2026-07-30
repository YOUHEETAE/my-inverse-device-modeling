from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Mapping
from typing import Any

from .analysis_schemas import LearningAnalysisContext
from .schemas import TopicConfig
from .question_router import QUESTION_TYPES, QuestionRoute
from .intent_interpreter import (
    ANSWER_STRUCTURES,
    INTENT_TYPES,
    REQUESTED_ACTIONS,
    UTTERANCE_TYPES,
    QuestionIntent,
)
from .tutor_schemas import (
    AnswerEvaluation,
    FollowupResponse,
    LearningFeedback,
    LearningSessionSummary,
    NextActionDecision,
)


LEVELS = {"correct", "partial", "incorrect", "uncertain"}
STRATEGIES = {"reinforce", "correct", "hint", "retry"}
CLAIM_ASSESSMENTS = {
    "supported",
    "partially_supported",
    "contradicted",
    "unverified",
    "not_applicable",
}
_NUMBER = re.compile(r"(?<![A-Za-z_])[-+]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?")


def sanitize_user_text(value: Any, *, limit: int = 1200) -> str:
    text = "".join(character for character in str(value or "") if character in "\n\t" or ord(character) >= 32).strip()
    if not text:
        raise ValueError("empty_user_text")
    if len(text) > limit:
        raise ValueError("user_text_too_long")
    return text


def _string_list(data: Any, name: str, *, maximum: int = 20) -> tuple[str, ...]:
    if not isinstance(data, list) or len(data) > maximum or any(not isinstance(item, str) for item in data):
        raise ValueError(f"invalid_{name}")
    return tuple(item.strip() for item in data if item.strip())


def validate_question_intent(
    data: Any,
    *,
    question: str,
    allowed_concepts: set[str],
    allowed_metrics: set[str],
    allowed_parameters: set[str],
) -> QuestionIntent:
    if not isinstance(data, dict):
        raise ValueError("invalid_question_intent")
    intent_aliases = {
        "explain": "explain_theory",
        "explain_concept": "explain_theory",
        "explain_metric": "explain_theory",
        "explain_result": "explain_current_result",
        "current_result": "explain_current_result",
        "confirm_setup": "confirm_experiment_setup",
        "confirm_experiment": "confirm_experiment_setup",
        "experiment_setup_confirmation": "confirm_experiment_setup",
        "add_condition": "add_experiment_condition",
    }
    action_aliases = {
        "answer": "explain",
        "describe": "explain",
        "execute": "run_experiment",
        "add_experiment": "add_condition",
        "confirm_setup": "confirm",
    }
    structure_aliases = {
        "cause_effect": "cause_and_effect",
        "parameter_by_parameters": "parameter_by_parameter",
        "per_parameter": "parameter_by_parameter",
        "compare": "comparison",
        "steps": "step_by_step",
    }
    intent = str(data.get("intent", "")).strip().lower()
    intent = intent_aliases.get(intent, intent)
    action = str(data.get("requested_action", "explain")).strip().lower()
    action = action_aliases.get(action, action)
    structure = str(
        data.get("answer_structure", "cause_and_effect")
    ).strip().lower()
    structure = structure_aliases.get(structure, structure)
    if intent not in INTENT_TYPES:
        raise ValueError("invalid_question_intent_type")
    if action not in REQUESTED_ACTIONS:
        raise ValueError("invalid_question_action")
    if structure not in ANSWER_STRUCTURES:
        raise ValueError("invalid_answer_structure")
    concept_aliases = {
        "vth": "threshold_voltage",
        "threshold": "threshold_voltage",
        "ion": "on_current",
        "ioff": "off_current",
        "ss": "subthreshold_swing",
        "sce": "short_channel_effect",
        "channel": "channel_length",
        "electric field": "electric_field",
    }
    metric_aliases = {
        "ion_ma_per_um": "ion",
        "ioff_ma_per_um": "ioff",
        "vth_high_v": "vth_high",
        "vth_low_v": "vth_low",
        "ss_mv_per_dec": "ss",
        "dibl_gm_v_per_v": "dibl",
        "gm": "gm_max",
        "gm max": "gm_max",
    }
    raw_concepts = _string_list(
        data.get("target_concepts", []),
        "intent_concepts",
        maximum=12,
    )
    concepts = tuple(dict.fromkeys(
        concept_aliases.get(item.strip().lower(), item.strip().lower())
        for item in raw_concepts
    ))
    raw_metrics = _string_list(
        data.get("requested_metrics", []),
        "intent_metrics",
        maximum=12,
    )
    metrics = tuple(dict.fromkeys(
        metric_aliases.get(item.strip().lower(), item.strip().lower())
        for item in raw_metrics
    ))
    if not set(concepts).issubset(allowed_concepts):
        raise ValueError("unknown_intent_concept")
    if not set(metrics).issubset(allowed_metrics):
        raise ValueError("unknown_intent_metric")
    conditions_data = data.get("conditions") or {}
    if not isinstance(conditions_data, dict):
        raise ValueError("invalid_intent_conditions")
    conditions: dict[str, float] = {}
    question_numbers = {
        float(item) for item in _NUMBER.findall(question)
    }
    parameter_names = {name.lower(): name for name in allowed_parameters}
    for raw_name, value in conditions_data.items():
        name = parameter_names.get(str(raw_name).strip().lower())
        if name is None or isinstance(value, bool):
            raise ValueError("invalid_intent_parameter")
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            matches = _NUMBER.findall(str(value))
            if not matches:
                raise ValueError("invalid_intent_condition_value")
            numeric = float(matches[0])
        if not math.isfinite(numeric) or numeric not in question_numbers:
            raise ValueError("invented_intent_condition")
        conditions[name] = numeric
    intent_defaults = {
        "references_previous": False,
        "needs_current_result": intent in {
            "explain_current_result",
            "compare_results",
            "confirm_experiment_setup",
        },
        "needs_theory": intent not in {
            "navigate_result",
            "out_of_scope",
            "confirm_experiment_setup",
        },
        "needs_new_experiment": intent in {
            "predict_change",
            "run_experiment",
            "add_experiment_condition",
        },
        "needs_clarification": False,
    }
    flags = {}
    for name in (
        "references_previous",
        "needs_current_result",
        "needs_theory",
        "needs_new_experiment",
        "needs_clarification",
    ):
        value = data.get(name, intent_defaults[name])
        if not isinstance(value, bool):
            raise ValueError(f"invalid_intent_flag:{name}")
        flags[name] = value
    clarification = data.get("clarification_question")
    if clarification is not None:
        clarification = str(clarification).strip()
        if not clarification:
            clarification = None
        elif len(clarification) > 500:
            raise ValueError("invalid_intent_clarification")
    if flags["needs_clarification"] and not clarification:
        raise ValueError("missing_intent_clarification")
    utterance_aliases = {
        "question": "concept_question",
        "theory_question": "concept_question",
        "result_question": "current_result_question",
        "confirmation": "experiment_confirmation",
        "experiment_setup_confirmation": "experiment_confirmation",
        "request_experiment": "experiment_request",
        "navigation": "navigation_request",
    }
    utterance = str(data.get("utterance_type", "")).strip().lower()
    if not utterance:
        utterance = {
            "confirm_experiment_setup": "experiment_confirmation",
            "explain_current_result": "current_result_question",
            "run_experiment": "experiment_request",
            "add_experiment_condition": "experiment_request",
            "navigate_result": "navigation_request",
            "out_of_scope": "out_of_scope",
        }.get(intent, "concept_question")
    utterance = utterance_aliases.get(utterance, utterance)
    if utterance not in UTTERANCE_TYPES:
        raise ValueError("invalid_utterance_type")
    try:
        confidence = float(data.get("confidence", 0.5))
    except (TypeError, ValueError) as error:
        raise ValueError("invalid_intent_confidence") from error
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("invalid_intent_confidence")
    raw_alternatives = data.get("alternative_intents", [])
    alternatives = _string_list(
        raw_alternatives if isinstance(raw_alternatives, list) else [],
        "alternative_intents",
        maximum=4,
    )
    alternatives = tuple(
        intent_aliases.get(item.strip().lower(), item.strip().lower())
        for item in alternatives
    )
    if not set(alternatives).issubset(INTENT_TYPES):
        raise ValueError("invalid_alternative_intent")
    return QuestionIntent(
        intent=intent,
        utterance_type=utterance,
        confidence=confidence,
        alternative_intents=alternatives,
        target_concepts=concepts,
        requested_metrics=metrics,
        requested_action=action,
        conditions=conditions,
        clarification_question=clarification,
        answer_structure=structure,
        source="external_llm",
        **flags,
    )


def validate_evaluation(data: Any, topic: TopicConfig) -> AnswerEvaluation:
    if not isinstance(data, dict):
        raise ValueError("invalid_evaluation")
    level = str(data.get("understanding_level", ""))
    strategy = str(data.get("feedback_strategy", ""))
    if level not in LEVELS or strategy not in STRATEGIES:
        raise ValueError("invalid_evaluation_enum")
    correct = _string_list(data.get("correct_concepts"), "correct_concepts")
    missing = _string_list(data.get("missing_concepts"), "missing_concepts")
    misconceptions = _string_list(data.get("detected_misconceptions"), "detected_misconceptions")
    unsupported = _string_list(data.get("unsupported_claims"), "unsupported_claims", maximum=10)
    if not set((*correct, *missing)).issubset(topic.expected_concepts):
        raise ValueError("unknown_evaluation_concept")
    if not set(misconceptions).issubset(topic.common_misconceptions):
        raise ValueError("unknown_evaluation_misconception")
    if data.get("recommended_next_action") != "show_feedback":
        raise ValueError("invalid_evaluation_next_action")
    return AnswerEvaluation(level, correct, missing, misconceptions, unsupported, strategy, "show_feedback", "external_llm")


def validate_feedback(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("invalid_feedback")
    result = {}
    for name in ("headline", "curve_focus", "field_focus", "summary", "next_question"):
        value = data.get(name)
        if not isinstance(value, str) or not value.strip() or len(value) > 800:
            raise ValueError(f"invalid_feedback_{name}")
        result[name] = value.strip()
    result["positive_feedback"] = _string_list(data.get("positive_feedback"), "positive_feedback", maximum=6)
    result["corrections"] = _string_list(data.get("corrections"), "corrections", maximum=6)
    return result


def validate_next_action(data: Any, topic: TopicConfig) -> NextActionDecision:
    if not isinstance(data, dict):
        raise ValueError("invalid_next_action")
    action_id = str(data.get("action_id", ""))
    allowed = {item.action_id for item in topic.allowed_next_actions}
    if action_id not in allowed:
        raise ValueError("disallowed_next_action")
    reason = str(data.get("reason", "")).strip()
    if not reason or len(reason) > 500:
        raise ValueError("invalid_next_action_reason")
    return NextActionDecision(action_id, reason, "external_llm")


def validate_summary(data: Any, topic: TopicConfig) -> LearningSessionSummary:
    if not isinstance(data, dict):
        raise ValueError("invalid_session_summary")
    headline, summary = str(data.get("headline", "")).strip(), str(data.get("summary", "")).strip()
    if not headline or not summary or len(headline) > 300 or len(summary) > 1200:
        raise ValueError("invalid_session_summary_text")
    understood = _string_list(data.get("understood_concepts"), "understood_concepts")
    needs_review = _string_list(data.get("needs_review"), "needs_review")
    misconceptions = _string_list(data.get("detected_misconceptions"), "detected_misconceptions")
    if not set((*understood, *needs_review)).issubset(topic.expected_concepts):
        raise ValueError("unknown_summary_concept")
    if not set(misconceptions).issubset(topic.common_misconceptions):
        raise ValueError("unknown_summary_misconception")
    action = data.get("recommended_next_action")
    if action is not None and action not in {item.action_id for item in topic.allowed_next_actions}:
        raise ValueError("disallowed_summary_action")
    return LearningSessionSummary(headline, summary, understood, needs_review, misconceptions, action, "external_llm")


def evidence_ids(context: LearningAnalysisContext) -> set[str]:
    ids = {
        item.evidence_id
        for item in (*context.curve_observations, *context.field_observations)
        if item.evidence_id
    }
    ids.update(item.evidence_id for item in context.electrical_changes.values() if item.evidence_id)
    for conclusion in context.validated_observations:
        ids.update(str(item) for item in conclusion.get("supporting_evidence_ids", []))
    if context.experiment:
        ids.add("experiment:conditions")
    return ids


def _number_variants(
    context: LearningAnalysisContext,
    additional_facts: Any = None,
) -> set[str]:
    values = []

    def collect(value: Any) -> None:
        if isinstance(value, bool) or value is None:
            return
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            values.append(float(value))
        elif isinstance(value, Mapping):
            for item in value.values():
                collect(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                collect(item)

    def collect_additional(value: Any) -> None:
        if isinstance(value, str):
            for token in _NUMBER.findall(value):
                try:
                    values.append(float(token))
                except ValueError:
                    continue
        elif isinstance(value, Mapping):
            for item in value.values():
                collect_additional(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                collect_additional(item)
        else:
            collect(value)

    collect(context.to_dict())
    collect_additional(additional_facts)
    variants = set()
    for value in values:
        variants.update({f"{value:g}", f"{value:.1f}", f"{value:.2f}", f"{value:.3f}", f"{value:.2e}"})
        if value.is_integer():
            variants.add(str(int(value)))
    return variants


def validate_followup(
    data: Any,
    topic: TopicConfig,
    context: LearningAnalysisContext,
    route: QuestionRoute | None = None,
    *,
    theory_concepts: tuple[str, ...] = (),
    case_connection: str | None = None,
    interpreted_intent: dict[str, Any] | None = None,
    additional_numeric_facts: Any = None,
    learning_move: str = "answer_question",
    explanation_level: str = "foundational",
    adaptation_reasons: tuple[str, ...] = (),
) -> FollowupResponse:
    if not isinstance(data, dict):
        raise ValueError("invalid_followup")
    question_type = str(data.get("question_type", ""))
    answer = str(data.get("answer", "")).strip()
    if question_type not in QUESTION_TYPES or not answer or len(answer) > 1800:
        raise ValueError("invalid_followup_content")
    if route is not None and question_type != route.question_type:
        raise ValueError("followup_route_mismatch")
    response_evidence = _string_list(data.get("evidence_ids"), "evidence_ids", maximum=20)
    if not set(response_evidence).issubset(evidence_ids(context)):
        raise ValueError("unknown_followup_evidence")
    action = data.get("suggested_action_id")
    if action is not None and action not in {item.action_id for item in topic.allowed_next_actions}:
        raise ValueError("disallowed_followup_action")
    needs_new = data.get("needs_new_experiment")
    distinguishes = data.get("distinguishes_current_result")
    if not isinstance(needs_new, bool) or not isinstance(distinguishes, bool):
        raise ValueError("invalid_followup_flags")
    if question_type in {"new_experiment", "hypothetical"} and not needs_new:
        raise ValueError("experiment_flag_required")
    if route is not None and needs_new != route.needs_new_experiment:
        raise ValueError("followup_experiment_flag_mismatch")
    allowed_numbers = _number_variants(context, additional_numeric_facts)
    answer_numbers = _NUMBER.findall(answer)
    if any(token not in allowed_numbers for token in answer_numbers):
        raise ValueError("ungrounded_followup_number")
    if route is not None:
        if not route.uses_current_result and response_evidence:
            raise ValueError("unexpected_current_result_evidence")
        if route.uses_current_result and answer_numbers and not response_evidence:
            raise ValueError("numeric_followup_evidence_required")
    claim_default = (
        "supported"
        if learning_move == "confirm_experiment"
        else (
            "unverified"
            if learning_move in {"evaluate_claim", "acknowledge_correction"}
            else "not_applicable"
        )
    )
    claim_assessment = str(
        data.get("claim_assessment", claim_default)
    ).strip()
    if claim_assessment not in CLAIM_ASSESSMENTS:
        raise ValueError("invalid_claim_assessment")
    acknowledged = _string_list(
        data.get("acknowledged_points", []),
        "acknowledged_points",
        maximum=6,
    )
    corrections = _string_list(
        data.get("correction_points", []),
        "correction_points",
        maximum=6,
    )
    next_question_value = data.get("next_learning_question")
    next_question = (
        str(next_question_value).strip()
        if next_question_value is not None
        else None
    )
    if next_question == "":
        next_question = None
    if next_question and len(next_question) > 500:
        raise ValueError("invalid_next_learning_question")
    metadata_text = " ".join(
        (*acknowledged, *corrections, next_question or "")
    )
    if any(
        token not in allowed_numbers
        for token in _NUMBER.findall(metadata_text)
    ):
        raise ValueError("ungrounded_followup_metadata_number")
    if (
        learning_move in {
            "evaluate_claim",
            "acknowledge_correction",
            "confirm_experiment",
        }
        and (
            claim_assessment == "not_applicable"
            or not acknowledged
        )
    ):
        raise ValueError("missing_claim_feedback")
    if (
        claim_assessment in {"partially_supported", "contradicted"}
        and not corrections
    ):
        raise ValueError("missing_claim_correction")
    if (
        learning_move in {
            "evaluate_claim",
            "acknowledge_correction",
            "confirm_experiment",
        }
        and claim_assessment in {
            "supported",
            "partially_supported",
            "contradicted",
        }
        and route is not None
        and route.uses_current_result
        and not response_evidence
    ):
        raise ValueError("claim_assessment_evidence_required")
    return FollowupResponse(
        question_type=question_type,
        answer=answer,
        evidence_ids=response_evidence,
        distinguishes_current_result=distinguishes,
        needs_new_experiment=needs_new,
        suggested_action_id=action,
        source="external_llm",
        relevance_to_case=route.relevance_to_case if route else "related",
        matched_concepts=route.matched_concepts if route else (),
        uses_current_result=route.uses_current_result if route else bool(response_evidence),
        needs_clarification=route.needs_clarification if route else False,
        clarification_question=route.clarification_question if route else None,
        theory_concepts=theory_concepts,
        case_connection=case_connection,
        interpreted_intent=dict(interpreted_intent or {}),
        interpretation_source=(
            route.intent_source if route else "deterministic"
        ),
        learning_move=learning_move,
        claim_assessment=claim_assessment,
        acknowledged_points=acknowledged,
        correction_points=corrections,
        next_learning_question=next_question,
        explanation_level=explanation_level,
        adaptation_reasons=adaptation_reasons,
    )


def strict_json(data: Any) -> None:
    json.dumps(data, ensure_ascii=False, allow_nan=False)
