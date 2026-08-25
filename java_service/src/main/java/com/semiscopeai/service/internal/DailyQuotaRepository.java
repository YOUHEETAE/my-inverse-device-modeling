package com.semiscopeai.service.internal;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

// 하루 한도를 세는 짧은 DB 단계들만 여기 있다. LLM 호출은 이 클래스 밖에서
// 일어난다 — 수십 초짜리 외부 호출을 트랜잭션 안에서 기다리면 커넥션 풀이
// 마른다(HikariCP 기본 최대 10). ChatService/ChatProcessor와 같은 규칙이다.
@Repository
public class DailyQuotaRepository {

    private final JdbcClient jdbcClient;

    public DailyQuotaRepository(JdbcClient jdbcClient) {
        this.jdbcClient = jdbcClient;
    }

    /**
     * 오늘 몫에서 한 번을 미리 잡아둔다. 한도를 넘었으면 false.
     *
     * <p>조회한 뒤 증가시키는 두 문장으로 나누면 동시에 들어온 요청이 같은
     * 값을 읽고 둘 다 통과한다. INSERT ... ON CONFLICT는 한 문장이라 그 틈이
     * 없다 — WHERE는 갱신 경로에만 걸리고, 조건이 어긋나면 아무 행도 바뀌지
     * 않는다. 그날 첫 요청은 충돌이 없으므로 WHERE와 무관하게 1로 시작한다.
     */
    @Transactional
    public boolean reserve(long userId, int limit) {
        return jdbcClient
                .sql("""
                        INSERT INTO daily_llm_usage (user_id, usage_date, calls)
                        VALUES (:userId, (now() AT TIME ZONE 'Asia/Seoul')::date, 1)
                        ON CONFLICT (user_id, usage_date) DO UPDATE
                           SET calls = daily_llm_usage.calls + 1
                         WHERE daily_llm_usage.calls < :limit
                        """)
                .param("userId", userId)
                .param("limit", limit)
                .update() > 0;
    }

    /**
     * 잡아둔 몫을 되돌린다.
     *
     * <p>답을 받지 못한 요청에까지 하루치를 깎으면 사용자가 손해를 본다.
     * 검증 오류든 LLM 장애든, 성공하지 못한 요청은 세지 않는다.
     */
    @Transactional
    public void release(long userId) {
        jdbcClient
                .sql("""
                        UPDATE daily_llm_usage
                           SET calls = calls - 1
                         WHERE user_id = :userId
                           AND usage_date = (now() AT TIME ZONE 'Asia/Seoul')::date
                           AND calls > 0
                        """)
                .param("userId", userId)
                .update();
    }

    /** 오늘 쓴 횟수. 기록이 없으면 0. */
    @Transactional(readOnly = true)
    public int usedToday(long userId) {
        return jdbcClient
                .sql("""
                        SELECT calls FROM daily_llm_usage
                        WHERE user_id = :userId
                          AND usage_date = (now() AT TIME ZONE 'Asia/Seoul')::date
                        """)
                .param("userId", userId)
                .query(Integer.class)
                .optional()
                .orElse(0);
    }
}
