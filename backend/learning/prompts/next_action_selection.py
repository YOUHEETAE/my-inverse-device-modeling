from __future__ import annotations

from .common import COMMON_SYSTEM, tagged_payload


def build_prompt(payload: dict) -> tuple[str, str]:
    system = COMMON_SYSTEM + """
allowed_next_actions 중 하나만 선택한다. 새로운 action_id를 만들지 않는다.
응답 key는 action_id와 reason이다."""
    return system, tagged_payload("학습 상태에 맞는 다음 행동 하나를 선택하라.", payload)
