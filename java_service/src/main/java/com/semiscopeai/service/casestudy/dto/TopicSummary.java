package com.semiscopeai.service.casestudy.dto;

import java.util.List;

public record TopicSummary(
        String topicId, String title, String description, int catalogOrder, List<String> prerequisiteTopicIds) {}
