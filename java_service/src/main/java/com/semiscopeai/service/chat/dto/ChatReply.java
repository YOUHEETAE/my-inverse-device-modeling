package com.semiscopeai.service.chat.dto;

import java.util.List;

// 프론트에 돌려주는 응답. Python 응답에 threadId를 얹은 형태다 — 프론트는
// 이 값을 다음 질문에 실어 보내 같은 대화를 이어간다.
//
// 비로그인 사용자는 저장되지 않으므로 threadId가 null이고, 그때는 프론트가
// 직접 이력을 들고 있어야 한다.
public record ChatReply(
        Long threadId,
        String answer,
        String source,
        String intent,
        List<String> usedEvidenceIds,
        String suggestedFollowup,
        boolean needsNewExperiment) {

    public static ChatReply of(Long threadId, ChatAnswer answer) {
        return new ChatReply(
                threadId,
                answer.answer(),
                answer.source(),
                answer.intent(),
                answer.usedEvidenceIds(),
                answer.suggestedFollowup(),
                answer.needsNewExperiment());
    }
}
