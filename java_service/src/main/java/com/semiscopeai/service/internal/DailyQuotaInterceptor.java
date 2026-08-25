package com.semiscopeai.service.internal;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.core.user.OAuth2User;
import org.springframework.stereotype.Component;
import org.springframework.util.AntPathMatcher;
import org.springframework.web.cors.CorsUtils;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.servlet.HandlerInterceptor;

/**
 * 계정 하나가 하루에 태울 수 있는 LLM 호출 수를 제한한다.
 *
 * <p>초당 제한(RateLimitInterceptor)과 목적이 다르다. 그쪽은 짧은 순간의
 * 폭주를, 이쪽은 하루 총량을 막는다. 천천히 꾸준히 부르면 초당 제한에는
 * 영원히 걸리지 않는다.
 */
@Component
public class DailyQuotaInterceptor implements HandlerInterceptor {

    /**
     * 실제로 LLM 토큰을 태우는 경로만.
     *
     * <p>{@link RateLimitWebConfig#HEAVY_PATHS}와 일부러 다르다. 거기에는
     * /curves/predict 와 /fields/** 도 들어 있는데, 이 둘은 우리 서버에서
     * 도는 서로게이트 모델이라 외부 비용이 0이다. 조건을 바꿔가며 비교하는
     * 것이 이 서비스의 핵심 사용 방식이라, 돈이 나가지도 않는 호출에 하루
     * 한도를 걸면 정작 배우려는 사람만 막힌다.
     *
     * <p>케이스 스터디도 마찬가지로 갈린다 — experiment 와 regenerate 는
     * 로컬 추론이고, evaluation(채점)과 followup(추가 질문)만 LLM이다.
     *
     * <p>/explain/*&#47;prompt 는 프롬프트 문자열만 만들어 돌려주므로 빠진다.
     * 여기 적힌 것은 전부 정확히 일치하는 경로라 하위 경로가 딸려오지 않는다.
     */
    static final String[] LLM_PATHS = {
        "/explain/curves",
        "/explain/fields",
        "/chat/curves",
        "/chat/fields",
        "/case-study/sessions/*/evaluation",
        "/case-study/sessions/*/followup",
    };

    // preHandle에서 잡아둔 몫을 afterCompletion에서 되돌리기 위한 표시.
    // 요청 하나 안에서만 산다.
    private static final String RESERVED_FOR = DailyQuotaInterceptor.class.getName() + ".reservedFor";

    private final DailyQuotaRepository dailyQuotaRepository;
    private final AntPathMatcher pathMatcher = new AntPathMatcher();
    private final int dailyLimit;

    public DailyQuotaInterceptor(
            DailyQuotaRepository dailyQuotaRepository, @Value("${app.daily-llm-limit}") int dailyLimit) {
        this.dailyQuotaRepository = dailyQuotaRepository;
        this.dailyLimit = dailyLimit;
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        if (CorsUtils.isPreFlightRequest(request) || !isLlmPath(request)) {
            return true;
        }
        Long userId = currentUserId();
        // 여기 적힌 경로는 SecurityConfig가 전부 인증을 요구하므로 principal이
        // 있어야 정상이다. 없다면 두 목록이 어긋난 것인데, 그렇다고 요청을
        // 막으면 원인을 찾기 어려운 장애가 된다. 세지 않고 통과시킨다 —
        // 어긋남 자체는 DailyQuotaInterceptorTest가 잡는다.
        if (userId == null) {
            return true;
        }
        if (!dailyQuotaRepository.reserve(userId, dailyLimit)) {
            throw new ResponseStatusException(
                    HttpStatus.TOO_MANY_REQUESTS,
                    "오늘 사용할 수 있는 AI 응답 " + dailyLimit + "번을 모두 썼습니다. 내일 다시 이용해 주세요.");
        }
        request.setAttribute(RESERVED_FOR, userId);
        return true;
    }

    // 성공하지 못한 요청은 세지 않는다. 잡아두고 시작하는 이유는, 응답이
    // 끝난 뒤에 세면 동시에 들어온 요청들이 모두 한도 검사를 통과해버리기
    // 때문이다.
    @Override
    public void afterCompletion(
            HttpServletRequest request, HttpServletResponse response, Object handler, Exception ex) {
        Object reservedFor = request.getAttribute(RESERVED_FOR);
        if (reservedFor == null) {
            return;
        }
        int status = response.getStatus();
        if (ex != null || status < 200 || status >= 300) {
            dailyQuotaRepository.release((Long) reservedFor);
        }
    }

    private boolean isLlmPath(HttpServletRequest request) {
        String path = request.getRequestURI();
        for (String pattern : LLM_PATHS) {
            if (pathMatcher.match(pattern, path)) {
                return true;
            }
        }
        return false;
    }

    // 로그인 시점에 세션에 담아둔 우리 DB의 PK (CustomOAuth2UserService).
    // 컨트롤러들이 @AuthenticationPrincipal로 꺼내 쓰는 값과 같다.
    private Long currentUserId() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication == null || !(authentication.getPrincipal() instanceof OAuth2User principal)) {
            return null;
        }
        Number userId = principal.getAttribute("userId");
        return userId == null ? null : userId.longValue();
    }
}
