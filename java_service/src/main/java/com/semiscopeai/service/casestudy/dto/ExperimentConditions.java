package com.semiscopeai.service.casestudy.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

// 다른 device-parameter DTO들과 달리 L/T/B/SD/LDD가 문자열이 아니라 숫자 —
// 사용자 입력이 아니라 서버가 내려주는 값이라서.
public record ExperimentConditions(
        @JsonProperty("L") double l,
        @JsonProperty("T") double t,
        @JsonProperty("B") double b,
        @JsonProperty("SD") double sd,
        @JsonProperty("LDD") double ldd) {}
