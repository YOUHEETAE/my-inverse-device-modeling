package com.semiscopeai.service.explain.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import java.util.List;

// fields의 FieldDisplayRequest와 달리 scaleMode/rangeMode에 기본값이 없음
// — Python 쪽에서도 필수 필드라서.
public record ExplainFieldRequest(
        @NotEmpty @Valid List<FieldConfig> fields,
        @NotBlank String display,
        @NotBlank String scaleMode,
        @NotBlank String rangeMode) {}
