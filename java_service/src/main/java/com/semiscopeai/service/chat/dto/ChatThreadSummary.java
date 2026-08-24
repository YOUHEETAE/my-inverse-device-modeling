package com.semiscopeai.service.chat.dto;

import java.time.Instant;
import java.util.Map;

// 목록 화면용.
//
// deviceConfig가 들어 있는 이유: 질문 문장만으로는 대화를 구분할 수 없다.
// 같은 화면을 보며 "이 커브 분석해줘"를 여러 번 물으면 미리보기가 전부
// 똑같아지고, 정작 다른 건 소자 조건이다.
//
// 마지막 질문이 아니라 첫 질문을 주는 것도 같은 이유다. 주제를 정한 건 첫
// 질문이고, 마지막 질문은 곁가지("감기에 걸렸어" 같은 범위 밖 질문)일 수
// 있어서 대화를 대표하지 못한다.
public record ChatThreadSummary(
        long threadId,
        String kind,
        Instant updatedAt,
        String firstQuestion,
        Map<String, Object> deviceConfig,
        // 실패한 턴은 뺀 수 — 상한(turn_limit)과 같은 기준이라야 "2/20"처럼
        // 이어서 보여줄 수 있다.
        int turnsUsed) {
}
