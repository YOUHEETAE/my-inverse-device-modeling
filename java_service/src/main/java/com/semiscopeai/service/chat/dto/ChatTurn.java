package com.semiscopeai.service.chat.dto;

// Python이 history 항목으로 받는 모양 그대로 (backend/app/routers/explain.py).
public record ChatTurn(String question, String answer, String source, String comparisonFocus) {

    public static ChatTurn of(String question, String answer, String source) {
        return new ChatTurn(question, answer, source, null);
    }
}
