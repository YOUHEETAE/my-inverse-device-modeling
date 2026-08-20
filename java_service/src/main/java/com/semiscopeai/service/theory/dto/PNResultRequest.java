package com.semiscopeai.service.theory.dto;

import jakarta.validation.constraints.NotNull;

public record PNResultRequest(@NotNull Double acceptors, @NotNull Double donors, @NotNull Double bias) {}
