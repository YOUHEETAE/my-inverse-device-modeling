package com.semiscopeai.service.auth;

import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.core.user.OAuth2User;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

// 로그인/로그아웃/회원가입 엔드포인트는 스프링 시큐리티가 이미 제공하므로
// (각각 /oauth2/authorization/{provider}, /logout, 그리고 최초 로그인 시
// CustomOAuth2UserService가 저장) 여기서 만들지 않는다. 프론트가 필요로 하는
// "현재 로그인 상태" 조회만 둔다.
@RestController
public class AuthController {

    @GetMapping("/auth/me")
    public MeResponse me(@AuthenticationPrincipal OAuth2User principal) {
        // 모든 경로가 permitAll이라 비로그인 요청도 여기까지 들어온다.
        if (principal == null) {
            return MeResponse.anonymous();
        }

        // 로그인 시점에 세션에 담아둔 우리 DB의 PK — 덕분에 매 요청마다
        // users를 다시 조회하지 않아도 된다 (CustomOAuth2UserService 참고).
        Long userId = ((Number) principal.getAttribute("userId")).longValue();

        return new MeResponse(true, userId, principal.getAttribute("name"), principal.getAttribute("email"));
    }
}
