from __future__ import annotations

from .common import COMMON_SYSTEM, tagged_payload


def build_prompt(payload: dict) -> tuple[str, str]:
    system = COMMON_SYSTEM + """
사용자 답변의 의미를 분석하되 정답 선택 판정은 deterministic_evaluation을 존중한다.
응답 key는 understanding_level, correct_concepts, missing_concepts,
detected_misconceptions, unsupported_claims, feedback_strategy,
recommended_next_action이다. recommended_next_action은 항상 show_feedback이다."""
    return system, tagged_payload("사용자 답변을 평가해 지정된 JSON schema로 반환하라.", payload)
