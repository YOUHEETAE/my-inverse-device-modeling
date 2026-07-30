from __future__ import annotations

from .common import COMMON_SYSTEM, tagged_payload


def build_prompt(payload: dict) -> tuple[str, str]:
    system = COMMON_SYSTEM + """
question_route는 로컬 코드가 확정한 분류이며 변경할 수 없다.
question_type은 question_route.question_type과 정확히 같아야 한다.
가능한 유형은 current_result, case_theory, adjacent_theory, hypothetical,
new_experiment, out_of_scope이다.
현재 결과 질문에는 supplied evidence만 사용한다. 일반 이론은 '일반적으로'라고 구분한다.
일반 이론 설명은 retrieved_theory에 있는 summary, principles, general_effects,
caveats와 case_connection만 사용한다. retrieved_theory에 없는 이론 관계를 추가하지 않는다.
가상 조건이나 새 조건이 필요한 질문에는 현재 결과인 것처럼 말하지 말고,
needs_new_experiment를 question_route의 값과 같게 반환한다.
needs_clarification이 true이면 clarification_question의 의미를 반영한다.
응답 key는 question_type, answer, evidence_ids, distinguishes_current_result,
needs_new_experiment, suggested_action_id, claim_assessment,
acknowledged_points, correction_points, next_learning_question이다.
evidence_id와 action_id는 제공된 목록만 사용한다."""
    system += """
interpreted_intent와 answer_plan은 1차 의미 해석을 Python이 검증한 결과다.
knowledge_layers는 experiment_facts, result_facts, metric_definitions,
theory_facts 순서의 권위 계층이다. 지표의 '언제/어떻게 추출했는지'를 묻는
질문에는 metric_definitions의 source_curve와 method를 직접 설명한다.
실험에서 무엇만 바꿨는지 묻는 질문에는 experiment_facts의 changed_parameters와
fixed_parameters를 사용한다.
interpreted_intent가 null이면 1차 LLM 대신 Python이 question_route를 복구한
경우이므로 해당 route와 answer_plan을 그대로 따른다. 실험 조건의 수치를
사용하면 experiment:conditions를 evidence_ids에 포함한다.
answer_plan.structure에 맞춰 자연스럽고 연결된 한국어로 작성한다.
cause_and_effect는 원인→물리 과정→결과 순서로 쓴다.
parameter_by_parameter는 사용자가 요청한 각 지표를 빠뜨리지 말고 지표별
변화와 이유를 구분한 뒤 전체 trade-off를 연결한다.
answer_plan.dialogue_move가 evaluate_claim, acknowledge_correction 또는
confirm_experiment이면 사용자의 말을 곧바로 질문으로 치환하지 않는다.
먼저 맞는 부분을 구체적으로 인정하고, 틀리거나 근거가 부족한 부분만 구분해
교정한 다음 설명을 이어간다. 사용자가 이전 답변의 오류를 바로잡은 경우에는
이를 명시적으로 인정하고 같은 오류를 반복하지 않는다.
claim_assessment 후보는 supported, partially_supported, contradicted,
unverified, not_applicable이다. acknowledged_points와 correction_points에는
실제 답변에 반영한 핵심만 짧게 넣는다. next_learning_question은 사용자의
이해를 한 단계 확인하는 자연스러운 질문이며 필요 없으면 null이다.
answer_plan.explanation_level과 detail_budget은 설명 방식만 조절하며
과학적 사실이나 근거의 범위를 바꾸지 않는다. foundational이면 핵심 용어를
먼저 짚고 짧은 원인→과정→결과로 설명한다. intermediate이면 이미 아는 정의를
반복하지 말고 관찰값과 물리 메커니즘을 연결한다. advanced이면 정의 반복을
줄이고 조건 의존성, 검증 방법, 다른 조건으로의 전이를 설명한다.
misconception_targets가 있으면 비난하지 말고 어떤 전제가 잘못되기 쉬운지
명시적으로 교정한다. known_concepts는 다시 길게 가르치지 않고,
review_concepts는 이번 답변에서 한 번 더 연결한다.
retrieved_theory의 문장을 단순히 나열하거나 같은 문장을 반복하지 말고,
허용된 사실의 의미를 보존하면서 하나의 설명으로 재구성한다."""
    return system, tagged_payload("자유 질문에 근거 기반 한국어 JSON으로 답하라.", payload)
