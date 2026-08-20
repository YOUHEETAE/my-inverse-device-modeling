package com.semiscopeai.service.curves.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;

// 디바이스 파라미터는 숫자가 아니라 드롭다운 값 문자열("1e16" 등), 파싱은
// Python이 함.
//
// L/T/B/SD/LDD는 application.properties의 전역 SNAKE_CASE 전략에 안 맞는
// 이름이라, @JsonProperty가 없으면 "l"로 직렬화돼서 프론트가 조용히 깨짐.
public record CurveRequest(
        @JsonProperty("L") @NotBlank String l,
        @JsonProperty("T") @NotBlank String t,
        @JsonProperty("B") @NotBlank String b,
        @JsonProperty("SD") @NotBlank String sd,
        @JsonProperty("LDD") @NotBlank String ldd) {}
