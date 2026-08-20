package com.semiscopeai.service.fields.dto;

import java.util.List;

// linthresh는 SymLog norm일 때만 값이 있고 그 외엔 null.
public record FieldDisplayResponse(
        String domain,
        List<Double> values,
        String title,
        String label,
        String normType,
        double vmin,
        double vmax,
        Double linthresh,
        String modeLabel,
        String cmap) {}
