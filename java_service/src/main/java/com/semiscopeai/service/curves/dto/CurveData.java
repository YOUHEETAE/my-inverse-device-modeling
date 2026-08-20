package com.semiscopeai.service.curves.dto;

import java.util.List;

// kind("idvd"/"idvg")를 enum이 아니라 String으로 둔 이유 — 별도 Jackson
// 설정 없이 Python JSON과 그대로 맞추려고.
public record CurveData(String kind, List<Double> grid, List<Double> fixedBiases, List<List<Double>> currents) {}
