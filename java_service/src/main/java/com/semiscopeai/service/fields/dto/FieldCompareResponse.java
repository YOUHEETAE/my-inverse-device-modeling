package com.semiscopeai.service.fields.dto;

import java.util.List;

public record FieldCompareResponse(
        String domain,
        String title,
        String label,
        String normType,
        double vmin,
        double vmax,
        Double linthresh,
        String modeLabel,
        String cmap,
        List<FieldCompareItem> items) {}
