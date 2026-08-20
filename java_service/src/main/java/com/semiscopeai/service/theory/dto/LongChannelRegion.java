package com.semiscopeai.service.theory.dto;

import java.util.List;

// gate 같은 일부 region은 net_doping/electrons/holes를 안 가져서 null.
public record LongChannelRegion(
        List<Double> xUm,
        List<Double> yUm,
        List<List<Integer>> triangles,
        List<Double> potential,
        List<Double> netDoping,
        List<Double> electrons,
        List<Double> holes) {}
