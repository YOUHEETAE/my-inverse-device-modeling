package com.semiscopeai.service.fields.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;

public record FieldDisplayRequest(
        @JsonProperty("L") @NotBlank String l,
        @JsonProperty("T") @NotBlank String t,
        @JsonProperty("B") @NotBlank String b,
        @JsonProperty("SD") @NotBlank String sd,
        @JsonProperty("LDD") @NotBlank String ldd,
        @NotBlank String display,
        String scaleMode,
        String rangeMode) {
    public FieldDisplayRequest {
        if (scaleMode == null) scaleMode = "Auto";
        if (rangeMode == null) rangeMode = "Robust 1-99%";
    }
}
