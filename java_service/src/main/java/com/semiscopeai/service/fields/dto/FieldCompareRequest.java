package com.semiscopeai.service.fields.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import java.util.List;

public record FieldCompareRequest(
        @NotEmpty @Valid List<FieldConfig> devices, @NotBlank String display, String scaleMode, String rangeMode) {
    public FieldCompareRequest {
        if (scaleMode == null) scaleMode = "Auto";
        if (rangeMode == null) rangeMode = "Robust 1-99%";
    }
}
