package com.semiscopeai.service.casestudy.dto;

// 갱신된 세션은 서버가 이미 저장했으므로 프론트에 되돌려주지 않는다 —
// 30KB짜리 세션을 답변 한 줄과 함께 실어보낼 이유가 없다. 화면에 필요한
// 대화 이력은 세션 조회로 가져간다.
public record FollowupReply(String answer, String source) {
}
