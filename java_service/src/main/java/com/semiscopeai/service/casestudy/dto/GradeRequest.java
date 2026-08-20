package com.semiscopeai.service.casestudy.dto;

import jakarta.validation.Valid;
import java.util.List;

public record GradeRequest(
        @Valid List<AnswerSubmission> predictionAnswers, @Valid List<AnswerSubmission> observationAnswers) {}
