from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .intent_interpreter import QuestionIntent
from .question_router import QuestionRoute


_LEARNING_TARGET_SIGNALS = {
    "threshold_voltage": ("threshold", "vth"),
    "short_channel_effect": ("short_channel", "sce", "dibl", "ss", "ioff"),
    "channel_length": ("channel_length", "length"),
    "on_current": ("on_current", "ion"),
    "off_current": ("off_current", "ioff", "leak"),
    "subthreshold_swing": ("subthreshold", "ss"),
    "body_doping": ("body_doping", "doping"),
    "oxide_thickness": ("oxide", "tox"),
    "electric_field": ("electric_field", "field"),
    "potential": ("potential", "barrier"),
}


def _targets_for_focus(
    targets: tuple[str, ...],
    focus: set[str],
) -> tuple[str, ...]:
    signals = set()
    for concept in focus:
        signals.add(concept.lower())
        signals.update(part for part in concept.lower().split("_") if len(part) > 2)
        signals.update(_LEARNING_TARGET_SIGNALS.get(concept, ()))
    return tuple(
        target
        for target in targets
        if any(signal in target.lower() for signal in signals)
    )


@dataclass(frozen=True)
class LearningResponsePlan:
    """Python-owned pedagogical plan for one free-form learning turn."""

    dialogue_move: str
    structure: str
    requested_action: str
    acknowledge_before_explaining: bool
    evaluate_student_claim: bool
    correction_policy: str
    connect_to_previous_turn: bool
    organize_each_requested_metric: bool
    explanation_level: str
    detail_budget: str
    include_foundation: bool
    include_mechanism_chain: bool
    check_understanding: bool
    next_question_style: str
    known_concepts: tuple[str, ...] = ()
    review_concepts: tuple[str, ...] = ()
    misconception_targets: tuple[str, ...] = ()
    adaptation_reasons: tuple[str, ...] = ()
    prior_claims: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_response_plan(
    question: str,
    route: QuestionRoute,
    intent: QuestionIntent | None,
    dialogue_state: dict[str, Any] | None,
    learner_profile: dict[str, Any] | None = None,
) -> LearningResponsePlan:
    utterance = intent.utterance_type if intent else "concept_question"
    normalized_question = question.lower().replace(" ", "")
    if intent is None:
        confirms_setup = (
            route.uses_current_result
            and any(
                cue in normalized_question
                for cue in ("이실험", "실험조건", "길이만", "뭐만", "무엇만")
            )
            and any(
                cue in normalized_question
                for cue in ("맞아", "맞지", "맞잖", "맞나요", "맞습니까")
            )
        )
        correction = any(
            cue in normalized_question
            for cue in (
                "그게아니",
                "아니잖",
                "말했잖",
                "방금답변",
                "이전답변",
            )
        )
        claim = any(
            cue in normalized_question
            for cue in (
                "라고생각",
                "것같",
                "때문이야",
                "때문이다",
                "라는거",
            )
        )
        if confirms_setup:
            utterance = "experiment_confirmation"
        elif correction:
            utterance = "correction"
        elif claim:
            utterance = "claim"
    if utterance == "correction":
        move = "acknowledge_correction"
    elif utterance == "claim":
        move = "evaluate_claim"
    elif utterance == "experiment_confirmation":
        move = "confirm_experiment"
    elif route.needs_clarification:
        move = "clarify_meaning"
    elif route.needs_new_experiment:
        move = "separate_prediction_from_result"
    else:
        move = "answer_question"

    claims = []
    for item in (dialogue_state or {}).get("student_claims", []):
        if isinstance(item, dict):
            claims.append(dict(item))

    evaluates_claim = move in {
        "acknowledge_correction",
        "evaluate_claim",
        "confirm_experiment",
    }
    profile = dict(learner_profile or {})
    mastery = {
        str(name): dict(item)
        for name, item in (dialogue_state or {}).get(
            "concept_mastery",
            {},
        ).items()
        if isinstance(item, dict)
    }
    understanding = str(profile.get("understanding_level", "unknown"))
    completed = tuple(
        dict.fromkeys(
            (
                *(
                    str(item)
                    for item in profile.get("completed_concepts", ())
                    if str(item)
                ),
                *(
                    concept
                    for concept, item in mastery.items()
                    if item.get("status") == "demonstrated"
                ),
            )
        )
    )[:30]
    remaining = tuple(
        dict.fromkeys(
            str(item)
            for item in profile.get("remaining_concepts", ())
            if str(item)
        )
    )[:30]
    misconceptions = tuple(
        dict.fromkeys(
            (
                *(
                    str(item)
                    for item in profile.get("detected_misconceptions", ())
                    if str(item)
                ),
                *(
                    concept
                    for concept, item in mastery.items()
                    if item.get("status") == "misconception"
                ),
            )
        )
    )[:20]
    focus = set(route.matched_concepts)
    review = _targets_for_focus(remaining, focus)
    mastered_focus = _targets_for_focus(completed, focus)
    reasons = []
    if misconceptions:
        level = "foundational"
        budget = "guided"
        next_style = "diagnostic"
        reasons.append("misconception_requires_explicit_correction")
    elif understanding in {"incorrect", "unknown"}:
        level = "foundational"
        budget = "guided"
        next_style = "concept_check"
        reasons.append("core_concept_scaffolding")
    elif understanding == "partial":
        level = "intermediate"
        budget = "standard"
        next_style = "mechanism_check"
        reasons.append("connect_observation_to_mechanism")
    else:
        level = "advanced"
        budget = "deep"
        next_style = "transfer"
        reasons.append("extend_verified_understanding")
    if review:
        reasons.append("current_focus_needs_review")
    if focus and mastered_focus:
        reasons.append("avoid_repeating_mastered_definition")
    explicitly_short = any(
        cue in normalized_question
        for cue in (
            "짧게",
            "간단히",
            "간단하게",
            "한문장",
            "한줄",
            "요약만",
        )
    )
    if route.answer_structure == "concise":
        if explicitly_short:
            budget = "concise"
            reasons.append("user_requested_concise_answer")
        else:
            # Intent interpreters often classify a direct definition question
            # as concise. That must not collapse a learning answer to a single
            # dictionary sentence.
            budget = "focused"
            reasons.append("focused_question_with_mechanism")

    return LearningResponsePlan(
        dialogue_move=move,
        structure=route.answer_structure,
        requested_action=route.requested_action,
        acknowledge_before_explaining=evaluates_claim,
        evaluate_student_claim=evaluates_claim,
        correction_policy=(
            "state_what_is_right_then_correct_only_the_unsupported_part"
            if evaluates_claim
            else "correct_only_when_needed"
        ),
        connect_to_previous_turn=bool(
            (intent and intent.references_previous)
            or utterance == "correction"
            or route.inherited_context
        ),
        organize_each_requested_metric=(
            route.answer_structure == "parameter_by_parameter"
        ),
        explanation_level=level,
        detail_budget=budget,
        include_foundation=(
            level == "foundational"
            and not mastered_focus
        ),
        include_mechanism_chain=(
            route.question_type != "out_of_scope"
            and not explicitly_short
        ),
        check_understanding=route.question_type != "out_of_scope",
        next_question_style=next_style,
        known_concepts=completed,
        review_concepts=review,
        misconception_targets=misconceptions,
        adaptation_reasons=tuple(reasons),
        prior_claims=tuple(claims[-3:]),
    )
