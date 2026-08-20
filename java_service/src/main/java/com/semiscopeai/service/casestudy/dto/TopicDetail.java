package com.semiscopeai.service.casestudy.dto;

import java.util.List;

public record TopicDetail(
        String topicId,
        String title,
        String description,
        List<String> learningObjectives,
        ExperimentConditions baseline,
        ExperimentConditions comparison,
        List<SafeQuestion> predictionQuestions,
        List<SafeQuestion> observationQuestions) {}
