package com.semiscopeai.service.internal;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class RateLimitWebConfig implements WebMvcConfigurer {

    // LLM 토큰이나 모델 추론을 태우는 경로. 나머지는 STANDARD로 떨어진다.
    //
    // 케이스 스터디는 세션 경로 안에서 갈린다 — 목록·조회·이름 변경은 DB만
    // 건드리지만 실험과 채점은 추론과 LLM을 태운다.
    static final String[] HEAVY_PATHS = {
        "/explain/**",
        "/chat/**",
        "/curves/predict",
        "/fields/**",
        "/case-study/sessions/*/experiment",
        "/case-study/sessions/*/regenerate",
        "/case-study/sessions/*/evaluation",
        "/case-study/sessions/*/followup",
    };

    private final RateLimitInterceptor rateLimitInterceptor;

    public RateLimitWebConfig(RateLimitInterceptor rateLimitInterceptor) {
        this.rateLimitInterceptor = rateLimitInterceptor;
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        // 하나의 인터셉터가 전체에 붙고, 경로를 보고 그룹을 고른다. 등록을
        // 둘로 나누면 무거운 경로가 양쪽에 걸려 토큰을 두 번 먹는다.
        registry.addInterceptor(rateLimitInterceptor);
    }
}
