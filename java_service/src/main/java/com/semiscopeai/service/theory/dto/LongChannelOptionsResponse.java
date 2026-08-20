package com.semiscopeai.service.theory.dto;

import java.util.List;

public record LongChannelOptionsResponse(List<Double> gateVoltages, List<Double> drainVoltages) {}
