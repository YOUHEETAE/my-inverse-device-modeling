package com.semiscopeai.service.chat.dto;

import java.time.Instant;
import java.util.List;
import java.util.Map;

// 대화 하나를 통째로 복원할 때 쓴다. deviceConfig가 함께 오는 이유는, 그
// 대화가 어떤 소자 조건을 두고 오간 것인지 화면에 표시하거나 그 조건을
// 다시 불러오기 위해서다.
// turnsUsed/turnLimit이 함께 오는 이유: 대화가 상한에 닿으면 프론트가 입력창
// 대신 "새 대화 시작"을 보여줘야 하는데, 그 판단을 messages를 세어서 하려면
// "실패한 턴은 세지 않는다"는 규칙이 프론트에도 복제된다.
public record ChatThreadView(
        long threadId,
        String kind,
        Map<String, Object> deviceConfig,
        Instant createdAt,
        Instant updatedAt,
        List<ChatMessageView> messages,
        int turnsUsed,
        int turnLimit) {

    // 상한값은 ChatService가 쥐고 있다. 저장소가 업무 규칙을 알 필요는 없어서
    // 조회 뒤에 얹는다.
    public ChatThreadView withTurnLimit(int limit) {
        return new ChatThreadView(
                threadId, kind, deviceConfig, createdAt, updatedAt, messages, turnsUsed, limit);
    }
}
