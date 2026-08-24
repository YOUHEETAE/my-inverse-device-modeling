package com.semiscopeai.service.internal;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.util.AntPathMatcher;

// 어떤 경로가 어느 몫을 쓰는지. 새 엔드포인트가 늘 때 여기서 먼저 걸린다.
class RateLimitGroupTest {

    private final AntPathMatcher matcher = new AntPathMatcher();

    private boolean heavy(String path) {
        for (String pattern : RateLimitWebConfig.HEAVY_PATHS) {
            if (matcher.match(pattern, path)) {
                return true;
            }
        }
        return false;
    }

    @Test
    void LLM과_모델_추론은_무거운_몫을_쓴다() {
        assertThat(heavy("/explain/curves")).isTrue();
        assertThat(heavy("/chat/curves")).isTrue();
        assertThat(heavy("/curves/predict")).isTrue();
        assertThat(heavy("/fields/display")).isTrue();
    }

    // 케이스 스터디는 세션 경로 안에서 갈린다 — 같은 접두사를 쓰지만
    // 실험과 채점만 추론과 LLM을 태운다.
    @Test
    void 케이스_스터디는_세션_경로_안에서_갈린다() {
        String session = "/case-study/sessions/2fac791a-0000-0000-0000-000000000000";

        assertThat(heavy(session + "/experiment")).isTrue();
        assertThat(heavy(session + "/evaluation")).isTrue();
        assertThat(heavy(session + "/followup")).isTrue();
        assertThat(heavy(session + "/regenerate")).isTrue();

        assertThat(heavy(session)).isFalse();
        assertThat(heavy(session + "/predictions")).isFalse();
        assertThat(heavy(session + "/begin-prediction")).isFalse();
    }

    // 화면 진입 때 나가는 것들. 여기가 무거운 몫에 걸리면 첫 진입부터 막힌다.
    @Test
    void 화면_진입_호출은_가벼운_몫을_쓴다() {
        assertThat(heavy("/auth/me")).isFalse();
        assertThat(heavy("/parameters")).isFalse();
        assertThat(heavy("/case-study/topics")).isFalse();
        assertThat(heavy("/case-study/portfolio")).isFalse();
        assertThat(heavy("/case-study/sessions")).isFalse();
    }

    @Test
    void 무거운_쪽이_더_빡빡하다() {
        assertThat(RateLimitGroup.HEAVY.burstCapacity())
                .isLessThan(RateLimitGroup.STANDARD.burstCapacity());
    }
}
