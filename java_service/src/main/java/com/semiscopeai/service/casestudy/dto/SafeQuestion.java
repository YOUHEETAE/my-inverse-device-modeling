package com.semiscopeai.service.casestudy.dto;

import java.util.List;

// "Safe" — 클라이언트로 내려가는 모양이라 정답 키(correct_options 등)를
// 의도적으로 뺌. 채점은 /grade에서 서버가 함.
public record SafeQuestion(
        String questionId, String type, String prompt, List<String> options, boolean reasonRequired) {}
