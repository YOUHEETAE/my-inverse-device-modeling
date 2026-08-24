package com.semiscopeai.service.chat.dto;

import java.util.List;

// 프론트에 돌려주는 응답. Python 응답에 threadId를 얹은 형태다 — 프론트는
// 이 값을 다음 질문에 실어 보내 같은 대화를 이어간다.
//
// turnsUsed/turnLimit을 매 응답에 실어, 상한이 가까워지면 다음 질문을 던지기
// 전에 미리 안내할 수 있게 한다. 질문 도중에 갑자기 막히면 안 된다.
public record ChatReply(
        Long threadId,
        String answer,
        String source,
        String intent,
        List<String> usedEvidenceIds,
        String suggestedFollowup,
        boolean needsNewExperiment,
        int turnsUsed,
        int turnLimit) {

    public static ChatReply of(Long threadId, ChatAnswer answer, int turnsUsed, int turnLimit) {
        return new ChatReply(
                threadId,
                answer.answer(),
                answer.source(),
                answer.intent(),
                answer.usedEvidenceIds(),
                answer.suggestedFollowup(),
                answer.needsNewExperiment(),
                turnsUsed,
                turnLimit);
    }
}
