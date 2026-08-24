package com.semiscopeai.service.internal;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.util.AntPathMatcher;
import org.springframework.web.cors.CorsUtils;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.servlet.HandlerInterceptor;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

@Component
public class RateLimitInterceptor implements HandlerInterceptor {
    private final RateLimiterService rateLimiterService;
    private final AntPathMatcher pathMatcher = new AntPathMatcher();

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
        if (!rateLimiterService.isAllowed(ip, groupOf(request))) {
            throw new ResponseStatusException(HttpStatus.TOO_MANY_REQUESTS, "Rate limit exceeded");
        }
        return true;
    }

    // 목록에 없으면 STANDARD. 새 엔드포인트가 실수로 느슨해지는 대신 실수로
    // 빡빡해지는 쪽이 낫다고 볼 수도 있지만, 대부분은 가벼운 읽기라 반대로
    // 두면 화면이 자주 막힌다. 비싼 경로를 추가할 때 여기 적는 편이 낫다.
    private RateLimitGroup groupOf(HttpServletRequest request) {
        String path = request.getRequestURI();
        for (String pattern : RateLimitWebConfig.HEAVY_PATHS) {
            if (pathMatcher.match(pattern, path)) {
                return RateLimitGroup.HEAVY;
            }
        }
        return RateLimitGroup.STANDARD;
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
