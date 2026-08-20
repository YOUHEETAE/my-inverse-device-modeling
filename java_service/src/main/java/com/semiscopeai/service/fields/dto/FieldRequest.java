package com.semiscopeai.service.fields.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;

// L/T/B/SD/LDD에 @JsonProperty가 필요한 이유는 CurveRequest 참고.
public record FieldRequest(
        @JsonProperty("L") @NotBlank String l,
        @JsonProperty("T") @NotBlank String t,
        @JsonProperty("B") @NotBlank String b,
        @JsonProperty("SD") @NotBlank String sd,
        @JsonProperty("LDD") @NotBlank String ldd) {}
