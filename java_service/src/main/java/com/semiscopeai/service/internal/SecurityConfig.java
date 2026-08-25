package com.semiscopeai.service.internal;

import com.semiscopeai.service.auth.CustomOAuth2UserService;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.http.HttpStatus;
import org.springframework.security.web.authentication.HttpStatusEntryPoint;
import org.springframework.security.web.authentication.logout.HttpStatusReturningLogoutSuccessHandler;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.Customizer;
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
    private final String frontendUrl;

    public SecurityConfig(
            CustomOAuth2UserService customOAuth2UserService,
            @Value("${app.frontend-url}") String frontendUrl) {
        this.customOAuth2UserService = customOAuth2UserService;
        this.frontendUrl = frontendUrl;
    }

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        return http
                // CorsConfig의 CorsConfigurationSource 빈을 사용한다. 이걸
                // 켜야 시큐리티 필터가 처리하는 /logout, /oauth2/** 에도 CORS
                // 헤더가 붙는다.
                .cors(Customizer.withDefaults())
                .csrf(csrf -> csrf.disable())
                // 경계는 하나다 — LLM 비용이 나가거나 기록이 남는 일은
                // 로그인해야 하고, 나머지는 공개다. 비로그인은 계정 단위로
                // 한도를 걸 수단이 없어서(DailyQuotaInterceptor) 익명에게
                // 열어두면 총량을 막을 방법이 없다.
                //
                // 소자 조건을 바꾸고 I-V Curve·Field Map을 예측해 비교하는
                // 것까지는 로그인 없이 그대로 된다. 그건 우리 서버에서 도는
                // 서로게이트 모델이라 외부 비용이 없다.
                .authorizeHttpRequests(auth -> auth
                        // 자유질문. 대화 이력도 사용자에 묶여 저장되므로
                        // 익명이면 매번 단발 질문이 된다.
                        .requestMatchers("/chat/**").authenticated()
                        // AI 설명. /explain/**/prompt 는 프롬프트 문자열만
                        // 만들어 돌려주므로 LLM을 태우지 않아 공개로 둔다.
                        .requestMatchers("/explain/curves", "/explain/fields").authenticated()
                        // 케이스 목록과 내용은 누구나 볼 수 있다. 기록이 남는
                        // 학습 세션만 로그인을 요구한다.
                        .requestMatchers("/case-study/sessions/**", "/case-study/portfolio").authenticated()
                        .anyRequest().permitAll())
                // 인증이 필요한 요청이 막혔을 때 구글 로그인 페이지로
                // 리다이렉트하는 것이 oauth2Login의 기본 동작인데, 프론트가
                // fetch로 부르는 API에서는 그 리다이렉트를 따라갈 수 없다
                // (다른 출처라 CORS에도 막힌다). 401을 그대로 돌려준다.
                .exceptionHandling(handling -> handling.authenticationEntryPoint(
                        new HttpStatusEntryPoint(HttpStatus.UNAUTHORIZED)))
                // 브라우저 기본 인증 팝업이 뜨지 않게 — 이 서비스는 JSON API다.
                .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.IF_REQUIRED))
                .httpBasic(basic -> basic.disable())
                .formLogin(form -> form.disable())
                // userService를 지정하지 않으면 스프링 기본 구현이 쓰여서
                // 인증만 되고 users 테이블에는 아무것도 저장되지 않는다.
                .oauth2Login(oauth -> oauth
                        .userInfoEndpoint(userInfo -> userInfo.userService(customOAuth2UserService))
                        // alwaysUse=true: 스프링은 원래 "인증이 필요해서 막혔던 경로"로
                        // 되돌려보내는데, 우리는 모든 경로가 permitAll이라 막힌 요청이
                        // 없어서 그 기록이 비어있다. 항상 프론트로 보내고, 사용자가
                        // 보던 화면 복원은 프론트가 처리한다(로그인 직전 경로를
                        // sessionStorage에 저장해둔다).
                        .defaultSuccessUrl(frontendUrl, true))
                // 기본 동작은 /login?logout 으로 302 리다이렉트인데, 그런 경로가
                // 없어서 프론트의 axios 호출이 404로 실패한다(세션은 이미 끊긴
                // 뒤라 "로그아웃은 됐는데 화면은 그대로"가 된다). JSON API이므로
                // 본문 없이 상태 코드만 돌려준다.
                .logout(logout -> logout.logoutSuccessHandler(
                        new HttpStatusReturningLogoutSuccessHandler(HttpStatus.NO_CONTENT)))
                .build();
    }
}
