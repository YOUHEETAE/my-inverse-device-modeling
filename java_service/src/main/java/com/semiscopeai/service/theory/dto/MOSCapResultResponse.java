package com.semiscopeai.service.theory.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public record MOSCapResultResponse(
        double acceptorDoping,
        double oxideThicknessNm,
        double gateVoltage,
        String regime,
        @JsonProperty("gate_charge_c_per_cm2") double gateChargeCPerCm2,
        @JsonProperty("oxide_x_nm") List<Double> oxideXNm,
        List<Double> oxidePotential,
        @JsonProperty("oxide_field_x_nm") List<Double> oxideFieldXNm,
        List<Double> oxideField,
        List<Double> siliconDepthNm,
        List<Double> siliconPotential,
        List<Double> electrons,
        List<Double> holes,
        List<Double> chargeDensity) {}
