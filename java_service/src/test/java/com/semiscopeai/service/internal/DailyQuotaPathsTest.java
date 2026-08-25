package com.semiscopeai.service.internal;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.util.AntPathMatcher;

// 하루 한도가 어디에 걸리는지. 초당 제한(RateLimitGroupTest)과 목록이 다른
// 것이 핵심이라, 새 엔드포인트가 늘 때 둘 중 어디에 넣을지 여기서 정해진다.
class DailyQuotaPathsTest {

    private static final String SESSION = "/case-study/sessions/2fac791a-0000-0000-0000-000000000000";

    private final AntPathMatcher matcher = new AntPathMatcher();

    private boolean counted(String path) {
        for (String pattern : DailyQuotaInterceptor.LLM_PATHS) {
            if (matcher.match(pattern, path)) {
                return true;
            }
        }
        return false;
    }

    private boolean heavy(String path) {
        for (String pattern : RateLimitWebConfig.HEAVY_PATHS) {
            if (matcher.match(pattern, path)) {
                return true;
            }
        }
        return false;
    }

    @Test
    void 외부_LLM을_태우는_호출만_센다() {
        assertThat(counted("/explain/curves")).isTrue();
        assertThat(counted("/explain/fields")).isTrue();
        assertThat(counted("/chat/curves")).isTrue();
        assertThat(counted("/chat/fields")).isTrue();
        assertThat(counted(SESSION + "/evaluation")).isTrue();
        assertThat(counted(SESSION + "/followup")).isTrue();
    }

    // 우리 서버에서 도는 서로게이트 모델. 비싸긴 해도 외부 비용이 0이고,
    // 조건을 바꿔가며 비교하는 게 이 서비스의 핵심 사용 방식이라 하루
    // 한도에 넣으면 정작 배우려는 사람만 막힌다.
    @Test
    void 로컬_추론은_세지_않는다() {
        assertThat(counted("/curves/predict")).isFalse();
        assertThat(counted("/fields/display")).isFalse();
        assertThat(counted("/fields/compare")).isFalse();
        assertThat(counted(SESSION + "/experiment")).isFalse();
        assertThat(counted(SESSION + "/regenerate")).isFalse();
    }

    // 프롬프트 문자열만 만들어 돌려주는 경로다. /explain/curves 로 시작하지만
    // 정확히 일치하지 않으므로 걸리지 않아야 한다 — 여기가 무너지면 LLM을
    // 부르지도 않는 호출이 하루치를 깎는다.
    @Test
    void 프롬프트만_만드는_경로는_세지_않는다() {
        assertThat(counted("/explain/curves/prompt")).isFalse();
        assertThat(counted("/explain/fields/prompt")).isFalse();
    }

    @Test
    void 화면_진입_호출은_세지_않는다() {
        assertThat(counted("/auth/me")).isFalse();
        assertThat(counted("/parameters")).isFalse();
        assertThat(counted("/case-study/topics")).isFalse();
        assertThat(counted("/case-study/portfolio")).isFalse();
        assertThat(counted("/chat/threads")).isFalse();
        assertThat(counted("/chat/threads/12")).isFalse();
    }

    // 하루 한도에 세는 것은 전부 초당 제한의 무거운 몫에도 들어가야 한다.
    // 반대는 성립하지 않는다(로컬 추론은 무겁지만 공짜다).
    @Test
    void 세는_경로는_모두_무거운_몫에도_들어간다() {
        assertThat(heavy("/explain/curves")).isTrue();
        assertThat(heavy("/explain/fields")).isTrue();
        assertThat(heavy("/chat/curves")).isTrue();
        assertThat(heavy("/chat/fields")).isTrue();
        assertThat(heavy(SESSION + "/evaluation")).isTrue();
        assertThat(heavy(SESSION + "/followup")).isTrue();
    }
}
