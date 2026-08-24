package com.semiscopeai.service.casestudy.dto;

import java.time.Instant;
import java.util.UUID;

// "학습 기록" 목록의 한 줄. 세션 전체는 30KB에 달해서 고르는 데 필요한
// 값만 추린다.
public record SessionSummary(
        UUID sessionId,
        String topicId,
        String displayName,
        String currentStep,
        boolean completed,
        Instant updatedAt) {
}
