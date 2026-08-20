package com.semiscopeai.service.explain.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

// label에 길이 제한을 둔 이유 — Python에서 LLM 프롬프트에 그대로 삽입됨.
public record CurveConfig(
        @NotBlank @Size(max = 60) String label,
        @JsonProperty("L") @NotBlank String l,
        @JsonProperty("T") @NotBlank String t,
        @JsonProperty("B") @NotBlank String b,
        @JsonProperty("SD") @NotBlank String sd,
        @JsonProperty("LDD") @NotBlank String ldd) {}
