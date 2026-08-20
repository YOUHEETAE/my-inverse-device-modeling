package com.semiscopeai.service.casestudy.dto;

import jakarta.validation.constraints.NotBlank;
import java.util.List;

public record AnswerSubmission(@NotBlank String questionId, List<String> selected, String reason) {
    public AnswerSubmission {
        if (reason == null) reason = "";
    }
}
