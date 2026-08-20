package com.semiscopeai.service.internal;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.cors.CorsUtils;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.servlet.HandlerInterceptor;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

@Component
public class RateLimitInterceptor implements HandlerInterceptor {
    private final RateLimiterService rateLimiterService;

    public RateLimitInterceptor(RateLimiterService rateLimiterService) {
        this.rateLimiterService = rateLimiterService;

    }

    // 직접 응답을 쓰지 않고 예외를 던지는 이유 — ApiExceptionHandler가 받아서
    // 다른 API 에러와 같은 {"detail": "..."} 형태로 통일해줌.
    public boolean preHandle(HttpServletRequest request,
            HttpServletResponse response, Object handler) throws Exception {
        if (CorsUtils.isPreFlightRequest(request)) {
            return true;
        }
        String ip = getClientIp(request);
        if (!rateLimiterService.isAllowed(ip)) {
            throw new ResponseStatusException(HttpStatus.TOO_MANY_REQUESTS, "Rate limit exceeded");
        }
        return true;
    }

    // Caddy 뒤에서는 getRemoteAddr()가 방문자가 아니라 Caddy의 내부 IP를
    // 주기 때문에, Caddy가 넣어주는 X-Forwarded-For를 우선 사용. 프록시가
    // 없는 로컬 개발용으로 폴백을 둠.
    private String getClientIp(HttpServletRequest request) {
        String ip = request.getHeader("X-Forwarded-For");
        if (ip == null || ip.isEmpty() || "unknown".equalsIgnoreCase(ip)) {
            ip = request.getRemoteAddr();
        }
        return ip.contains(",") ? ip.split(",")[0].trim() : ip;
    }

}
