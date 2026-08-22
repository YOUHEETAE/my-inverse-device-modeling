package com.semiscopeai.service.chat.dto;

import java.time.Instant;

// 저장된 한 턴. source가 external_error인 턴도 그대로 돌려준다 — 사용자가
// 이미 화면에서 본 내용이라, 다시 열었을 때 사라지면 대화가 어긋나 보인다.
// 프론트는 source로 실패한 답변을 구분해 표시하면 된다.
public record ChatMessageView(
        long id, String question, String answer, String source, String intent, Instant createdAt) {
}
