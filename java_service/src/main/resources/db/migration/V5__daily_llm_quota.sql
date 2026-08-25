-- 계정별 하루 LLM 호출 한도.
--
-- 초당 레이트 리밋(RateLimitGroup)은 폭주를 막지만 총량은 막지 못한다.
-- 하루 종일 천천히 부르면 어느 순간에도 제한에 걸리지 않으면서 비용은 계속
-- 나간다. HEAVY의 초당 2회를 하루로 환산하면 17만 회다.
--
-- 인메모리 버킷 대신 테이블을 쓰는 이유가 둘 있다. 재배포와 재시작을 넘어
-- 남아야 "하루"라는 단위가 뜻을 갖고, 나중에 인스턴스를 늘려도 한도가
-- 서버마다 따로 세어지지 않는다.
CREATE TABLE daily_llm_usage (
    user_id    BIGINT  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- 서버는 UTC로 돌고 사용자는 KST다. UTC 날짜로 세면 한국 시간 오전 9시에
    -- 한도가 풀려서 사용자가 느끼는 하루와 어긋난다. 그래서 날짜는 항상
    -- Asia/Seoul 기준으로 계산해 넣는다 (DailyQuotaRepository의 SQL 참고).
    usage_date DATE    NOT NULL,
    calls      INTEGER NOT NULL,

    -- 검사와 증가를 한 문장으로 처리하려면 충돌 대상이 될 키가 필요하다.
    PRIMARY KEY (user_id, usage_date)
);
