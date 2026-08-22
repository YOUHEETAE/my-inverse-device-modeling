package com.semiscopeai.service.internal;

import com.semiscopeai.service.auth.CustomOAuth2UserService;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;

// 스프링 시큐리티는 의존성만 추가해도 모든 엔드포인트를 잠그기 때문에,
// 기존 공개 API가 그대로 열려있도록 명시해줘야 함.
//
// 회원 기능이 아직 없어서 지금은 전부 permitAll이고 CSRF도 꺼져 있다.
// 로그인이 붙는 시점에 (1) 인증이 필요한 경로를 구분하고 (2) CSRF를 켜야
// 한다 — 세션 쿠키는 브라우저가 자동으로 붙여주기 때문에 CSRF 방어가
// 없으면 다른 사이트에서 보낸 form POST가 로그인된 사용자 권한으로
// 실행될 수 있음.
@Configuration
public class SecurityConfig {

    private final CustomOAuth2UserService customOAuth2UserService;

    public SecurityConfig(CustomOAuth2UserService customOAuth2UserService) {
        this.customOAuth2UserService = customOAuth2UserService;
    }

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        return http.csrf(csrf -> csrf.disable())
                .authorizeHttpRequests(auth -> auth.anyRequest().permitAll())
                // 브라우저 기본 인증 팝업이 뜨지 않게 — 이 서비스는 JSON API다.
                .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.IF_REQUIRED))
                .httpBasic(basic -> basic.disable())
                .formLogin(form -> form.disable())
                // userService를 지정하지 않으면 스프링 기본 구현이 쓰여서
                // 인증만 되고 users 테이블에는 아무것도 저장되지 않는다.
                .oauth2Login(oauth -> oauth
                        .userInfoEndpoint(userInfo -> userInfo.userService(customOAuth2UserService)))
                .build();
    }
}
