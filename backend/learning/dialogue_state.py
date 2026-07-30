from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable


@dataclass
class DialogueState:
    """Compact semantic memory for a learning conversation."""

    current_topic: str | None = None
    current_focus: list[str] = field(default_factory=list)
    referenced_result: str | None = None
    last_explained_concept: str | None = None
    pending_question: str | None = None
    student_claims: list[dict[str, Any]] = field(default_factory=list)
    concept_mastery: dict[str, dict[str, Any]] = field(default_factory=dict)
    open_experiment_request: dict[str, Any] | None = None
    last_intent: dict[str, Any] = field(default_factory=dict)
    turn_count: int = 0
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "DialogueState":
        value = dict(data or {})
        if value and str(value.get("schema_version", "1.0")) != "1.0":
            raise ValueError("unsupported_dialogue_state_schema")
        return cls(
            current_topic=(
                str(value["current_topic"])
                if value.get("current_topic")
                else None
            ),
            current_focus=[
                str(item) for item in value.get("current_focus", [])
            ][:12],
            referenced_result=(
                str(value["referenced_result"])
                if value.get("referenced_result")
                else None
            ),
            last_explained_concept=(
                str(value["last_explained_concept"])
                if value.get("last_explained_concept")
                else None
            ),
            pending_question=(
                str(value["pending_question"])
                if value.get("pending_question")
                else None
            ),
            student_claims=[
                dict(item)
                for item in value.get("student_claims", [])
                if isinstance(item, dict)
            ][-30:],
            concept_mastery={
                str(name): dict(item)
                for name, item in (
                    value.get("concept_mastery", {})
                    if isinstance(value.get("concept_mastery"), dict)
                    else {}
                ).items()
                if isinstance(item, dict)
            },
            open_experiment_request=(
                dict(value["open_experiment_request"])
                if isinstance(value.get("open_experiment_request"), dict)
                else None
            ),
            last_intent=dict(value.get("last_intent", {})),
            turn_count=max(0, int(value.get("turn_count", 0))),
        )

    @classmethod
    def from_history(
        cls,
        topic_id: str | None,
        turns: Iterable[Any],
    ) -> "DialogueState":
        state = cls(current_topic=topic_id)
        for turn in turns:
            DialogueStateManager.update_from_turn(state, turn)
        return state


class DialogueStateManager:
    @staticmethod
    def update_from_turn(state: DialogueState, turn: Any) -> None:
        concepts = [
            str(item)
            for item in getattr(turn, "matched_concepts", ())
            if str(item)
        ]
        if concepts:
            state.current_focus = list(dict.fromkeys(concepts))[:12]
            state.last_explained_concept = concepts[0]
        state.referenced_result = (
            "current_experiment"
            if getattr(turn, "uses_current_result", False)
            else state.referenced_result
        )
        state.pending_question = (
            str(getattr(turn, "clarification_question", "") or "") or None
            if getattr(turn, "needs_clarification", False)
            else None
        )
        intent = dict(getattr(turn, "interpreted_intent", {}) or {})
        state.last_intent = intent
        learning_move = str(
            getattr(turn, "learning_move", "answer_question")
            or "answer_question"
        )
        if learning_move in {
            "evaluate_claim",
            "acknowledge_correction",
            "confirm_experiment",
        }:
            state.student_claims.append({
                "claim": str(getattr(turn, "question", ""))[:600],
                "dialogue_move": learning_move,
                "assessment": str(
                    getattr(turn, "claim_assessment", "unverified")
                    or "unverified"
                ),
                "concepts": concepts,
                "evidence_ids": [
                    str(item)
                    for item in getattr(turn, "evidence_ids", ())
                    if str(item)
                ][:12],
                "acknowledged_points": [
                    str(item)
                    for item in getattr(turn, "acknowledged_points", ())
                    if str(item)
                ][:6],
                "correction_points": [
                    str(item)
                    for item in getattr(turn, "correction_points", ())
                    if str(item)
                ][:6],
                "turn": state.turn_count + 1,
            })
            state.student_claims = state.student_claims[-30:]
            assessment = str(
                getattr(turn, "claim_assessment", "unverified")
                or "unverified"
            )
            mastery_status = {
                "supported": "demonstrated",
                "partially_supported": "developing",
                "contradicted": "misconception",
                "unverified": "unverified",
            }.get(assessment, "unverified")
            for concept in concepts:
                state.concept_mastery[concept] = {
                    "status": mastery_status,
                    "assessment": assessment,
                    "evidence_ids": [
                        str(item)
                        for item in getattr(turn, "evidence_ids", ())
                        if str(item)
                    ][:12],
                    "turn": state.turn_count + 1,
                }
        if getattr(turn, "needs_new_experiment", False):
            state.open_experiment_request = {
                "question": str(getattr(turn, "question", "")),
                "concepts": concepts,
                "conditions": dict(intent.get("conditions", {})),
                "requested_action": intent.get("requested_action"),
            }
        elif intent.get("requested_action") not in {
            "run_experiment",
            "add_condition",
        }:
            state.open_experiment_request = None
        state.turn_count += 1

    @staticmethod
    def update_from_response(
        state: DialogueState,
        *,
        question: str,
        response: Any,
    ) -> None:
        class TurnView:
            pass

        turn = TurnView()
        turn.question = question
        for name in (
            "matched_concepts",
            "uses_current_result",
            "needs_clarification",
            "clarification_question",
            "interpreted_intent",
            "needs_new_experiment",
            "learning_move",
            "claim_assessment",
            "evidence_ids",
            "acknowledged_points",
            "correction_points",
        ):
            setattr(turn, name, getattr(response, name, None))
        DialogueStateManager.update_from_turn(state, turn)
