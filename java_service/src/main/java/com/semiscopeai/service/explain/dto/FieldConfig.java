package com.semiscopeai.service.explain.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

// fields.dto.FieldConfig와 거의 같지만 별개 타입 — Python도 두 라우터가
// 각자 별도 모델을 쓰고 있어서 그대로 따라감.
public record FieldConfig(
        @NotBlank @Size(max = 60) String label,
        @JsonProperty("L") @NotBlank String l,
        @JsonProperty("T") @NotBlank String t,
        @JsonProperty("B") @NotBlank String b,
        @JsonProperty("SD") @NotBlank String sd,
        @JsonProperty("LDD") @NotBlank String ldd) {}
