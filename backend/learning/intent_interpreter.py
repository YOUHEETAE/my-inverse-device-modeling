from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


INTENT_TYPES = {
    "explain_current_result",
    "explain_theory",
    "compare_results",
    "predict_change",
    "run_experiment",
    "add_experiment_condition",
    "navigate_result",
    "out_of_scope",
    "confirm_experiment_setup",
}
REQUESTED_ACTIONS = {
    "explain",
    "compare",
    "predict",
    "run_experiment",
    "add_condition",
    "navigate",
    "clarify",
    "confirm",
}
ANSWER_STRUCTURES = {
    "concise",
    "cause_and_effect",
    "parameter_by_parameter",
    "comparison",
    "step_by_step",
}
UTTERANCE_TYPES = {
    "concept_question",
    "current_result_question",
    "experiment_confirmation",
    "claim",
    "correction",
    "experiment_request",
    "navigation_request",
    "out_of_scope",
}


@dataclass(frozen=True)
class QuestionIntent:
    intent: str
    utterance_type: str = "concept_question"
    confidence: float = 0.5
    alternative_intents: tuple[str, ...] = ()
    target_concepts: tuple[str, ...] = ()
    requested_metrics: tuple[str, ...] = ()
    requested_action: str = "explain"
    conditions: dict[str, float] | None = None
    references_previous: bool = False
    needs_current_result: bool = False
    needs_theory: bool = True
    needs_new_experiment: bool = False
    needs_clarification: bool = False
    clarification_question: str | None = None
    answer_structure: str = "cause_and_effect"
    source: str = "external_llm"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
