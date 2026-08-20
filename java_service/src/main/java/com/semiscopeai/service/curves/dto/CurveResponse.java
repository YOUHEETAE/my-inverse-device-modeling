package com.semiscopeai.service.curves.dto;

import java.util.Map;

public record CurveResponse(
        CurveData idvd, CurveData idvg, Map<String, Double> electricalParameters, String rangeWarning) {}
