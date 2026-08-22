package com.semiscopeai.service.chat.dto;

import java.util.List;
import java.util.Map;

// Python의 ChatResponse를 그대로 받는다.
public record ChatAnswer(
        String answer,
        // "external_llm" | "local_router" | "external_error"
        String source,
        String intent,
        List<String> usedEvidenceIds,
        String suggestedFollowup,
        boolean needsNewExperiment,
        Map<String, Object> intentCheckpoint) {

    // 실패한 턴은 다음 질문의 맥락으로 되돌려보내지 않는다 — Python도 같은
    // 기준으로 history에서 걸러낸다.
    public boolean isFailure() {
        return "external_error".equals(source);
    }
}
