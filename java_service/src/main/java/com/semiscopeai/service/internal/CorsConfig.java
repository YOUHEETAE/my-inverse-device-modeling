package com.semiscopeai.service.internal;

import java.util.Arrays;
import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

// backend/app/main.py와 같은 CORS_ALLOW_ORIGINS 환경변수/기본값을 씀.
//
// WebMvcConfigurer.addCorsMappings이 아니라 CorsConfigurationSource 빈으로
// 두는 이유: 전자는 스프링 MVC가 처리하는 요청에만 적용돼서, 시큐리티 필터가
// 직접 처리하는 /logout, /oauth2/** 같은 경로에는 CORS 헤더가 붙지 않는다.
// 실제로 로그아웃 요청이 브라우저에서 CORS로 차단됐다. 이 빈은 SecurityConfig의
// http.cors()가 집어가서 모든 요청에 적용된다.
@Configuration
public class CorsConfig {

    private final List<String> allowedOrigins;

    public CorsConfig(@Value("${cors.allow-origins}") String allowOrigins) {
        this.allowedOrigins =
                Arrays.stream(allowOrigins.split(",")).map(String::trim).filter(s -> !s.isEmpty()).toList();
    }

    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration config = new CorsConfiguration();
        config.setAllowedOrigins(allowedOrigins);
        config.setAllowedMethods(List.of("*"));
        config.setAllowedHeaders(List.of("*"));
        // 로그인 세션 쿠키가 오가려면 필요하다. 배포 환경은 프론트와 API가 같은
        // 출처라 CORS 자체를 타지 않지만, 로컬 개발은 포트가 달라 이것이 없으면
        // /auth/me가 항상 비로그인으로 나온다. 명세상 credentials와 "*" 출처는
        // 함께 쓸 수 없어서 allowedOrigins를 명시적으로 나열한다.
        config.setAllowCredentials(true);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", config);
        return source;
    }
}
