package com.semiscopeai.service.chat.dto;

import java.time.Instant;
import java.util.List;
import java.util.Map;

// 대화 하나를 통째로 복원할 때 쓴다. deviceConfig가 함께 오는 이유는, 그
// 대화가 어떤 소자 조건을 두고 오간 것인지 화면에 표시하거나 그 조건을
// 다시 불러오기 위해서다.
public record ChatThreadView(
        long threadId,
        String kind,
        Map<String, Object> deviceConfig,
        Instant createdAt,
        Instant updatedAt,
        List<ChatMessageView> messages) {
}
