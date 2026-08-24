package com.semiscopeai.service.casestudy.dto;

import jakarta.validation.constraints.NotEmpty;
import java.util.Map;

// question_id -> 학습자 답변. 답변의 모양(선택지, 근거)은 케이스 설정이
// 정하므로 자바는 검사하지 않는다 — Python의 상태머신이 질문 집합과 대조해
// 거른다. 여기서 형식을 한 번 더 정의하면 두 곳이 어긋난다.
public record SessionAnswers(@NotEmpty Map<String, Object> answers) {
}
