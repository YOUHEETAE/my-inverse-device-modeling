package com.semiscopeai.service.internal;

import java.time.Duration;
import io.github.bucket4j.Bandwidth;

/**
 * 호출 비용에 따른 제한 그룹.
 *
 * <p>전에는 모든 경로에 초당 2개를 걸었는데, 화면 하나 여는 데 요청이 네 개씩
 * 나가서(로그인 확인, 케이스 목록, 학습 현황, 학습 기록) 정상 사용이 첫
 * 진입부터 막혔다.
 *
 * <p>가르는 기준은 "화면 이동이냐"가 아니라 "비싸냐"다. 화면 진입 때 불리는
 * 학습 현황도 DB 전체 조회가 따르고, 화면 이동과 무관한 곡선 예측은 파라미터를
 * 만질 때마다 불린다. 막고 싶은 건 토큰과 추론 시간을 태우는 호출이다.
 */
public enum RateLimitGroup {

    /** LLM 토큰이나 모델 추론을 태우는 호출. */
    HEAVY(2, 10),

    /** DB 읽기나 설정 파일 조회. 정상 사용은 닿지 않고 폭주만 걸린다. */
    STANDARD(20, 40);

    private final Bandwidth bandwidth;

    RateLimitGroup(long perSecond, long burstCapacity) {
        // refillIntervally는 1초 경계마다 몰아서 리필해 그 순간의 버스트를
        // 못 막는다 — greedy여야 실제로 초당 n개로 눌린다.
        this.bandwidth = Bandwidth.builder()
                .capacity(burstCapacity)
                .refillGreedy(perSecond, Duration.ofSeconds(1))
                .build();
    }

    Bandwidth bandwidth() {
        return bandwidth;
    }

    long burstCapacity() {
        return bandwidth.getCapacity();
    }
}
