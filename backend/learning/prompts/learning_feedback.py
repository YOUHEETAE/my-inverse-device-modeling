from __future__ import annotations

from .common import COMMON_SYSTEM, tagged_payload


def build_prompt(payload: dict) -> tuple[str, str]:
    system = COMMON_SYSTEM + """
평가 결과와 검증된 분석 결과를 교육적인 한국어 피드백으로 변환한다.
새 수치나 새 물리 원인을 만들지 않는다. evidence는 서버가 별도로 구성하므로 출력하지 않는다.
curve_focus와 field_focus는 모든 학습자에게 반복하는 일반 관찰 가이드가 아니다.
평가 결과에서 학습자가 놓쳤거나 잘못 연결한 부분이 있을 때에만, 현재 Case에서
다시 볼 구체적인 Curve 구간 또는 Field 영역을 한 문장으로 안내한다.
해당 자료에서 다시 확인할 내용이 없으면 "추가로 다시 확인할 위치 없음"이라고 쓴다.
응답 key는 headline, positive_feedback, corrections, curve_focus,
field_focus, summary, next_question이다."""
    return system, tagged_payload("학습자 맞춤 피드백 JSON을 반환하라.", payload)
