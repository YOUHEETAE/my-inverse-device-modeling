package com.semiscopeai.service.theory.dto;

import jakarta.validation.constraints.NotNull;

public record LongChannelResultRequest(@NotNull Double gateVoltage, @NotNull Double drainVoltage) {}
