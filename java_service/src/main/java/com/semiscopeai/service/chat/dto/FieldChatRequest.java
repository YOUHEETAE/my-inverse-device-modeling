package com.semiscopeai.service.chat.dto;

import com.semiscopeai.service.explain.dto.FieldConfig;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Size;
import java.util.List;

// Field 질문은 소자가 2개 이상이어야 한다. 근거(evidence)가 비교에서 만들어지는
// 설계라 1개면 인용할 근거가 없어 Python 검증이 거부한다
// (docs/explanation_system_architecture.md). @Size(min = 2)로 여기서 먼저
// 걸러 LLM 호출 비용을 낭비하지 않고, 이유가 분명한 400을 돌려준다.
public record FieldChatRequest(
        @NotEmpty @Size(min = 2, message = "Field 질문은 비교할 소자가 2개 이상 필요합니다.")
        @Valid List<FieldConfig> fields,
        @NotBlank String display,
        @NotBlank String scaleMode,
        @NotBlank String rangeMode,
        @NotBlank @Size(max = 800) String question,
        Long threadId) {
}
