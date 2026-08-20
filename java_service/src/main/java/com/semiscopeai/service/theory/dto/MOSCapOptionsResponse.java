package com.semiscopeai.service.theory.dto;

import java.util.List;

public record MOSCapOptionsResponse(
        List<Double> acceptorDopings, List<Double> oxideThicknessesNm, List<Double> gateVoltages) {}
