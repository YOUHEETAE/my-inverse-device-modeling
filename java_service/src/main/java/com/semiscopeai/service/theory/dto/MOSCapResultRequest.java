package com.semiscopeai.service.theory.dto;

import jakarta.validation.constraints.NotNull;

public record MOSCapResultRequest(
        @NotNull Double acceptorDoping, @NotNull Double oxideThicknessNm, @NotNull Double gateVoltage) {}
