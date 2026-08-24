package com.semiscopeai.service.casestudy.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

// Python도 800자에서 자르므로(learning/llm_service.py) 같은 한도를 둔다.
public record FollowupRequest(@NotBlank @Size(max = 800) String question) {
}
