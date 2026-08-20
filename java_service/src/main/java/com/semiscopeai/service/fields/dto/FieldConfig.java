package com.semiscopeai.service.fields.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;

public record FieldConfig(
        @NotBlank String label,
        @JsonProperty("L") @NotBlank String l,
        @JsonProperty("T") @NotBlank String t,
        @JsonProperty("B") @NotBlank String b,
        @JsonProperty("SD") @NotBlank String sd,
        @JsonProperty("LDD") @NotBlank String ldd) {}
