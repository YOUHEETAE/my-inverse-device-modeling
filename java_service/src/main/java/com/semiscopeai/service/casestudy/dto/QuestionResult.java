package com.semiscopeai.service.casestudy.dto;

import java.util.List;

public record QuestionResult(
        String questionId, String prompt, List<String> correctOptions, List<String> selected, boolean fullyCorrect) {}
