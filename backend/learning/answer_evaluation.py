from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .schemas import QuestionSpec
from .tutor_schemas import AnswerEvaluation


def parse_answer(raw_answer: Any) -> tuple[tuple[str, ...], str]:
    if isinstance(raw_answer, dict):
        selected = raw_answer.get("selected", raw_answer.get("selection", []))
        if isinstance(selected, str):
            selected = [selected]
        selections = tuple(str(item).strip() for item in selected if str(item).strip())
        reason = str(raw_answer.get("reason", "")).strip()
        return selections, reason
    if isinstance(raw_answer, (list, tuple, set)):
        return tuple(str(item).strip() for item in raw_answer if str(item).strip()), ""
    return (), str(raw_answer or "").strip()


def _ordered(values: Iterable[str], reference: tuple[str, ...]) -> tuple[str, ...]:
    selected = set(values)
    return tuple(item for item in reference if item in selected)


def evaluate_structured_answer(question: QuestionSpec, raw_answer: Any) -> AnswerEvaluation:
    selected, reason = parse_answer(raw_answer)
    selected_set = set(selected)
    options = set(question.options)
    correct_options = set(question.correct_options)
    unsupported = tuple(item for item in selected if item not in options)
    valid_selected = selected_set & options
    selected_correct = valid_selected & correct_options
    selected_wrong = valid_selected - correct_options

    correct_concepts = {
        concept
        for option in selected_correct
        for concept in question.concepts_by_option.get(option, ())
    }
    expected_concepts = {
        concept
        for option in correct_options
        for concept in question.concepts_by_option.get(option, ())
    }
    misconceptions = {
        misconception
        for option in selected_wrong
        for misconception in question.misconceptions_by_option.get(option, ())
    }

    if not selected and not reason:
        level, strategy = "uncertain", "hint"
    elif correct_options:
        if valid_selected == correct_options and not unsupported:
            if question.reason_required and not reason:
                level, strategy = "partial", "hint"
            else:
                level, strategy = "correct", "reinforce"
        elif selected_correct:
            level, strategy = "partial", "correct"
        else:
            level, strategy = "incorrect", "correct"
    else:
        level, strategy = ("partial", "hint") if reason else ("uncertain", "hint")

    concept_order = tuple(dict.fromkeys(question.concepts_by_option.get(option, ()) for option in question.options))
    flat_order = tuple(concept for group in concept_order for concept in group)
    return AnswerEvaluation(
        understanding_level=level,
        correct_concepts=_ordered(correct_concepts, flat_order),
        missing_concepts=_ordered(expected_concepts - correct_concepts, flat_order),
        detected_misconceptions=tuple(sorted(misconceptions)),
        unsupported_claims=unsupported,
        feedback_strategy=strategy,
        recommended_next_action="show_feedback",
        source="local",
    )
