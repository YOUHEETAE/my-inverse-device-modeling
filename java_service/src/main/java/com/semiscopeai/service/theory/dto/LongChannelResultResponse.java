package com.semiscopeai.service.theory.dto;

import java.util.List;
import java.util.Map;

public record LongChannelResultResponse(
        Map<String, LongChannelRegion> regions,
        List<Double> gateVoltages,
        List<Double> drainCurrents,
        double idvgDrainVoltage,
        List<Double> idvdGateVoltages,
        List<Double> idvdDrainVoltages,
        List<List<Double>> idvdCurrents,
        double selectedGateVoltage,
        double selectedDrainVoltage) {}
