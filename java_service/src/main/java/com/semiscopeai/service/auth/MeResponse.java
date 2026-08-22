package com.semiscopeai.service.auth;

// 프론트가 페이지를 열 때마다 "지금 로그인 상태인가"를 물어보는 용도.
//
// 비로그인일 때 401이 아니라 200 + authenticated=false로 답하는 이유:
// 이 엔드포인트는 매 페이지 진입마다 호출되는데, 비로그인이 "오류"는 아니다.
// 401로 주면 프론트가 정상 흐름을 try/catch로 감싸야 하고 콘솔에도 에러가
// 쌓인다.
public record MeResponse(boolean authenticated, Long userId, String name, String email) {

    public static MeResponse anonymous() {
        return new MeResponse(false, null, null, null);
    }
}
