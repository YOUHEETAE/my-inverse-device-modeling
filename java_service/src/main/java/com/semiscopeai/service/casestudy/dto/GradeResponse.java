package com.semiscopeai.service.casestudy.dto;

import java.util.List;

public record GradeResponse(
        List<String> positiveFeedback, List<String> corrections, String summary, List<QuestionResult> questionResults) {}
