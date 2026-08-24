package com.semiscopeai.service.casestudy.dto;

import jakarta.validation.constraints.NotBlank;
import com.fasterxml.jackson.annotation.JsonProperty;

public record NewSessionRequest(@JsonProperty("topic_id") @NotBlank String topicId) {
}
