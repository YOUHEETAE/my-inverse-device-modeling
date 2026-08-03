from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.learning import LearningAnalysisContext, LearningLLMService, load_topic
from backend.learning.followup_context import FOLLOWUP_PROMPT_BYTE_BUDGET
from backend.learning.session_repository import JsonSessionRepository


def _json_bytes(value: Any) -> int:
    return len(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
    )


class CapturingProvider:
    """Records both tutor calls without sending anything to Groq."""

    name = "request_inspector"

    def __init__(self, model: str) -> None:
        self.model = model
        self.calls: list[dict[str, Any]] = []

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        payload: dict,
    ) -> dict:
        call_number = len(self.calls) + 1
        if call_number == 1:
            response = {
                "intent": "explain_theory",
                "utterance_type": "concept_question",
                "confidence": 0.98,
                "alternative_intents": [],
                "target_concepts": ["off_current"],
                "requested_metrics": ["ioff"],
                "requested_action": "explain",
                "conditions": {},
                "references_previous": False,
                "needs_current_result": False,
                "needs_theory": True,
                "needs_new_experiment": False,
                "needs_clarification": False,
                "clarification_question": None,
                "answer_structure": "concise",
            }
        else:
            route = dict(payload.get("question_route", {}))
            response = {
                "question_type": route.get("question_type", "case_theory"),
                "answer": (
                    "Ioff는 소자가 꺼진 바이어스 조건에서 측정하는 "
                    "드레인 누설 전류입니다."
                ),
                "evidence_ids": [],
                "distinguishes_current_result": False,
                "needs_new_experiment": bool(
                    route.get("needs_new_experiment", False)
                ),
                "suggested_action_id": None,
                "claim_assessment": "not_applicable",
                "acknowledged_points": [],
                "correction_points": [],
                "next_learning_question": None,
            }
        self.calls.append(
            {
                "stage": (
                    "intent_interpretation"
                    if call_number == 1
                    else "answer_generation"
                ),
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "payload": payload,
                "received_example": response,
            }
        )
        return response


def _latest_session(
    root: Path,
    requested: str,
):
    repository = JsonSessionRepository(root)
    if requested == "latest":
        sessions = repository.list_sessions()
        if not sessions:
            raise RuntimeError(f"저장된 세션이 없습니다: {root}")
        return sessions[0]
    session = repository.load(requested)
    if session is None:
        raise RuntimeError(f"세션을 찾을 수 없습니다: {requested}")
    return session


def _http_request_bytes(
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> int:
    envelope = {
        "model": model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    return len(json.dumps(envelope, ensure_ascii=False).encode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Groq에 전송하지 않고 Case Study 튜터 요청을 재구성합니다."
    )
    parser.add_argument(
        "--question",
        default="Ioff는 어떤 파라미터야?",
    )
    parser.add_argument("--session", default="latest")
    parser.add_argument(
        "--session-root",
        type=Path,
        default=REPOSITORY_ROOT / "runtime" / "learning_sessions",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("LLM_MODEL", "openai/gpt-oss-120b"),
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="system/user prompt와 payload 전문을 포함합니다.",
    )
    args = parser.parse_args()

    session = _latest_session(args.session_root, args.session)
    if not session.topic_id or not session.analysis_snapshot:
        raise RuntimeError("선택한 세션에 Case 분석 결과가 없습니다.")
    topic = load_topic(session.topic_id)
    context = LearningAnalysisContext.from_dict(session.analysis_snapshot)
    history = [
        {
            "question": turn.question,
            "answer": turn.answer,
            "question_type": turn.question_type,
            "matched_concepts": turn.matched_concepts,
            "source": turn.source,
            "interpreted_intent": turn.interpreted_intent,
            "pipeline_diagnostics": turn.pipeline_diagnostics,
        }
        for turn in session.followup_history
    ]
    profile = {
        "understanding_level": session.understanding_level.value,
        "completed_concepts": session.completed_concepts,
        "remaining_concepts": session.remaining_concepts,
        "detected_misconceptions": session.detected_misconceptions,
    }
    provider = CapturingProvider(args.model)
    response = LearningLLMService(provider).ask_followup(
        topic,
        args.question,
        context,
        history,
        session.dialogue_state.to_dict(),
        profile,
    )

    stages = []
    for call in provider.calls:
        payload = call["payload"]
        item = {
            "stage": call["stage"],
            "http_request_utf8_bytes": _http_request_bytes(
                args.model,
                call["system_prompt"],
                call["user_prompt"],
            ),
            "system_prompt_utf8_bytes": len(
                call["system_prompt"].encode("utf-8")
            ),
            "user_prompt_utf8_bytes": len(
                call["user_prompt"].encode("utf-8")
            ),
            "payload_section_utf8_bytes": {
                key: _json_bytes(value)
                for key, value in payload.items()
            },
            "sent_payload_keys": list(payload),
            "received_json_example": call["received_example"],
        }
        if call["stage"] == "answer_generation":
            prompt_bytes = (
                item["system_prompt_utf8_bytes"]
                + item["user_prompt_utf8_bytes"]
            )
            item["configured_prompt_budget_utf8_bytes"] = (
                FOLLOWUP_PROMPT_BYTE_BUDGET
            )
            item["within_configured_prompt_budget"] = (
                prompt_bytes <= FOLLOWUP_PROMPT_BYTE_BUDGET
            )
        if args.full:
            item.update(
                {
                    "system_prompt": call["system_prompt"],
                    "user_prompt": call["user_prompt"],
                    "sent_payload": payload,
                }
            )
        stages.append(item)
    report = {
        "note": "검사 전용 재구성이며 Groq API를 호출하지 않습니다.",
        "question": args.question,
        "session_id": session.session_id,
        "history_turns_supplied": min(len(history), 6),
        "model": args.model,
        "stages": stages,
        "validated_final_response": asdict(response),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
