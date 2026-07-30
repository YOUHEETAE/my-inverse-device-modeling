from __future__ import annotations

from .common import COMMON_SYSTEM, tagged_payload


def build_prompt(payload: dict) -> tuple[str, str]:
    system = COMMON_SYSTEM + """
평가 결과와 검증된 분석 결과를 교육적인 한국어 피드백으로 변환한다.
새 수치나 새 물리 원인을 만들지 않는다. evidence는 서버가 별도로 구성하므로 출력하지 않는다.
응답 key는 headline, positive_feedback, corrections, curve_focus,
field_focus, summary, next_question이다."""
    return system, tagged_payload("학습자 맞춤 피드백 JSON을 반환하라.", payload)
