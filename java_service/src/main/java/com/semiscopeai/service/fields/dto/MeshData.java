package com.semiscopeai.service.fields.dto;

import java.util.List;

public record MeshData(
        List<List<Double>> nodeXyNm,
        List<Integer> nodeRegion,
        List<List<Integer>> triangles,
        List<List<Double>> elementCentroidXyNm,
        List<Integer> elementRegion) {}
