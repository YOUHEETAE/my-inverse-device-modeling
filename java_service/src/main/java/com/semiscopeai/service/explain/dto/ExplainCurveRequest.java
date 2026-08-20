package com.semiscopeai.service.explain.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotEmpty;
import java.util.List;

public record ExplainCurveRequest(@NotEmpty @Valid List<CurveConfig> curves) {}
