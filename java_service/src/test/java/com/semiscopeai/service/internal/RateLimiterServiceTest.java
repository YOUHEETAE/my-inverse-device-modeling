package com.semiscopeai.service.internal;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class RateLimiterServiceTest {

    private static final int BURST_CAPACITY = 10;

    @Test
    void 버스트_한도까지는_허용되고_넘으면_거부된다() {
        RateLimiterService service = new RateLimiterService();
        String ip = "1.2.3.4";

        for (int i = 0; i < BURST_CAPACITY; i++) {
            assertThat(service.isAllowed(ip, RateLimitGroup.HEAVY)).isTrue();
        }
        assertThat(service.isAllowed(ip, RateLimitGroup.HEAVY)).isFalse();
    }

    @Test
    void 서로_다른_IP는_독립적인_버킷을_가진다() {
        RateLimiterService service = new RateLimiterService();

        for (int i = 0; i < BURST_CAPACITY; i++) {
            assertThat(service.isAllowed("1.1.1.1", RateLimitGroup.HEAVY)).isTrue();
        }
        assertThat(service.isAllowed("1.1.1.1", RateLimitGroup.HEAVY)).isFalse();

        assertThat(service.isAllowed("2.2.2.2", RateLimitGroup.HEAVY)).isTrue();
    }

    @Test
    void 시간이_지나면_토큰이_다시_채워진다() throws InterruptedException {
        RateLimiterService service = new RateLimiterService();
        String ip = "3.3.3.3";

        for (int i = 0; i < BURST_CAPACITY; i++) {
            assertThat(service.isAllowed(ip, RateLimitGroup.HEAVY)).isTrue();
        }
        assertThat(service.isAllowed(ip, RateLimitGroup.HEAVY)).isFalse();

        // greedy 리필이라 1초를 조금 넘기면 채워짐
        Thread.sleep(1100);

        assertThat(service.isAllowed(ip, RateLimitGroup.HEAVY)).isTrue();
    }

    // 한 화면이 동시에 2~3건을 쏘는 실제 사용 패턴(예: CaseStudyFlow가 주제 조회
    // 직후 곡선 2건을 Promise.all로 동시 호출)이 막히지 않아야 함 — capacity가
    // 2였을 때 프로덕션에서 실제로 429가 났던 케이스.
    @Test
    void 한_화면에서_연달아_나가는_요청_3건은_막히지_않는다() {
        RateLimiterService service = new RateLimiterService();
        String ip = "4.4.4.4";

        assertThat(service.isAllowed(ip, RateLimitGroup.HEAVY)).isTrue();
        assertThat(service.isAllowed(ip, RateLimitGroup.HEAVY)).isTrue();
        assertThat(service.isAllowed(ip, RateLimitGroup.HEAVY)).isTrue();
    }

    @Test
    void 한동안_안_쓴_IP의_버킷은_정리된다() throws InterruptedException {
        RateLimiterService service = new RateLimiterService();
        service.isAllowed("5.5.5.5", RateLimitGroup.HEAVY);
        assertThat(service.trackedBucketCount()).isEqualTo(1);

        // 초당 2개씩 리필되므로 1개만 쓴 버킷은 1초 안에 다시 가득 참
        Thread.sleep(1100);
        service.cleanupExpiredBucket();

        assertThat(service.trackedBucketCount()).isZero();
    }

    @Test
    void 방금_사용한_IP의_버킷은_정리되지_않는다() {
        RateLimiterService service = new RateLimiterService();
        service.isAllowed("6.6.6.6", RateLimitGroup.HEAVY);

        service.cleanupExpiredBucket();

        assertThat(service.trackedBucketCount()).isEqualTo(1);
    }

    // 정리가 제한을 우회하는 수단이 되면 안 됨 — 한도를 다 쓴 버킷은 토큰이
    // 0이라 정리 대상이 아니고, 따라서 정리를 돌려도 여전히 막혀야 함.
    @Test
    void 정리를_돌려도_한도를_소진한_IP는_계속_막힌다() {
        RateLimiterService service = new RateLimiterService();
        String ip = "7.7.7.7";
        for (int i = 0; i < BURST_CAPACITY; i++) {
            service.isAllowed(ip, RateLimitGroup.HEAVY);
        }

        service.cleanupExpiredBucket();

        assertThat(service.trackedBucketCount()).isEqualTo(1);
        assertThat(service.isAllowed(ip, RateLimitGroup.HEAVY)).isFalse();
    }

    // 화면 하나 여는 데 요청이 네 개씩 나간다(로그인 확인, 케이스 목록, 학습
    // 현황, 학습 기록). 전부 한 몫으로 세던 시절에는 첫 진입부터 막혔다.
    @Test
    void 가벼운_호출은_화면_진입을_막지_않는다() {
        RateLimiterService service = new RateLimiterService();

        for (int i = 0; i < 20; i++) {
            assertThat(service.isAllowed("9.9.9.9", RateLimitGroup.STANDARD)).isTrue();
        }
    }

    // 무거운 몫을 다 썼다고 화면 이동까지 막히면 안 되고, 그 반대도 안 된다.
    @Test
    void 그룹끼리_몫을_나눠_쓴다() {
        RateLimiterService service = new RateLimiterService();
        String ip = "8.8.8.8";

        while (service.isAllowed(ip, RateLimitGroup.HEAVY)) {
            // 무거운 몫을 소진
        }

        assertThat(service.isAllowed(ip, RateLimitGroup.HEAVY)).isFalse();
        assertThat(service.isAllowed(ip, RateLimitGroup.STANDARD)).isTrue();
    }

    @Test
    void 같은_IP라도_그룹마다_버킷이_따로다() {
        RateLimiterService service = new RateLimiterService();

        service.isAllowed("7.7.7.7", RateLimitGroup.HEAVY);
        service.isAllowed("7.7.7.7", RateLimitGroup.STANDARD);

        assertThat(service.trackedBucketCount()).isEqualTo(2);
    }
}
