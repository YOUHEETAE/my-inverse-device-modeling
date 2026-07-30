from __future__ import annotations

from .common import COMMON_SYSTEM, tagged_payload


def build_prompt(payload: dict) -> tuple[str, str]:
    system = COMMON_SYSTEM + """
한 세션의 학습 내용을 간결하게 정리한다.
응답 key는 headline, summary, understood_concepts, needs_review,
detected_misconceptions, recommended_next_action이다."""
    return system, tagged_payload("세션 학습 요약 JSON을 반환하라.", payload)
