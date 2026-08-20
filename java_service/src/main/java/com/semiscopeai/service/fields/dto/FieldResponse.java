package com.semiscopeai.service.fields.dto;

import java.util.List;
import java.util.Map;

public record FieldResponse(
        MeshData mesh,
        List<Double> netDoping,
        Map<String, List<Double>> nodeFields,
        Map<String, List<Double>> elementFields,
        String rangeWarning) {}
