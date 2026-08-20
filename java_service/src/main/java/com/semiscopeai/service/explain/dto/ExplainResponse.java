package com.semiscopeai.service.explain.dto;

import java.util.List;

public record ExplainResponse(
        List<String> descriptions,
        List<String> comparisons,
        List<String> tradeoffs,
        List<String> cautions,
        String provider,
        String model,
        boolean cached) {}
