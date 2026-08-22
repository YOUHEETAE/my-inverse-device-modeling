package com.semiscopeai.service.chat.dto;

import java.time.Instant;

// 목록 화면용. 메시지 전체를 싣지 않고 마지막 질문만 미리보기로 준다.
public record ChatThreadSummary(
        long threadId, String kind, Instant updatedAt, String lastQuestion, int messageCount) {
}
