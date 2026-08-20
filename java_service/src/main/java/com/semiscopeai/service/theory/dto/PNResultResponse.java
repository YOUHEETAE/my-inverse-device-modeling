package com.semiscopeai.service.theory.dto;

import java.util.List;

public record PNResultResponse(
        List<Double> xUm,
        List<Double> yUm,
        List<List<Integer>> triangles,
        List<Double> netDoping,
        List<Double> potential,
        List<Double> electrons,
        List<Double> holes,
        List<Double> electricField,
        List<Double> electricFieldX,
        List<Double> voltages,
        List<Double> currents,
        double selectedBias) {}
