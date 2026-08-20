package com.semiscopeai.service.fields.dto;

import java.util.List;

public record FieldCompareItem(String label, MeshData mesh, List<Double> values) {}
