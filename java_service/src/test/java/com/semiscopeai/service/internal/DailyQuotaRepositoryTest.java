package com.semiscopeai.service.internal;

import static org.assertj.core.api.Assertions.assertThat;

import com.semiscopeai.service.support.PersistenceTestApp;
import com.semiscopeai.service.user.User;
import com.semiscopeai.service.user.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.annotation.Transactional;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

// 검사와 증가를 한 문장에 담은 ON CONFLICT ... WHERE 가 이 리포지토리의
// 전부라, H2로는 검증이 되지 않는다(문법도 동작도 다르다). 진짜 PostgreSQL을
// 띄우고 스키마도 Flyway가 만들게 해서 V5 마이그레이션까지 함께 확인한다.
@SpringBootTest(classes = PersistenceTestApp.class)
@Testcontainers
@Transactional
@ActiveProfiles("test-postgres")
class DailyQuotaRepositoryTest {

    @Container
    @ServiceConnection
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:17-alpine");

    @Autowired
    private DailyQuotaRepository dailyQuotaRepository;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private JdbcClient jdbcClient;

    private long userId;

    @BeforeEach
    void createUser() {
        userId = newUser("u-1");
    }

    @Test
    void 한도까지는_잡히고_넘으면_거절된다() {
        assertThat(dailyQuotaRepository.reserve(userId, 3)).isTrue();
        assertThat(dailyQuotaRepository.reserve(userId, 3)).isTrue();
        assertThat(dailyQuotaRepository.reserve(userId, 3)).isTrue();

        assertThat(dailyQuotaRepository.reserve(userId, 3)).isFalse();
        assertThat(dailyQuotaRepository.usedToday(userId)).isEqualTo(3);
    }

    // 거절된 요청까지 세면 한도를 넘긴 뒤로는 영원히 풀리지 않는다.
    @Test
    void 거절된_요청은_횟수를_늘리지_않는다() {
        dailyQuotaRepository.reserve(userId, 1);

        dailyQuotaRepository.reserve(userId, 1);
        dailyQuotaRepository.reserve(userId, 1);

        assertThat(dailyQuotaRepository.usedToday(userId)).isEqualTo(1);
    }

    @Test
    void 실패한_호출은_되돌려서_다시_쓸_수_있다() {
        assertThat(dailyQuotaRepository.reserve(userId, 1)).isTrue();
        assertThat(dailyQuotaRepository.reserve(userId, 1)).isFalse();

        dailyQuotaRepository.release(userId);

        assertThat(dailyQuotaRepository.usedToday(userId)).isZero();
        assertThat(dailyQuotaRepository.reserve(userId, 1)).isTrue();
    }

    // 되돌리기가 0 아래로 내려가면 그만큼 공짜 호출이 생긴다.
    @Test
    void 되돌리기는_0_아래로_내려가지_않는다() {
        dailyQuotaRepository.release(userId);
        dailyQuotaRepository.release(userId);

        assertThat(dailyQuotaRepository.usedToday(userId)).isZero();
    }

    @Test
    void 사용자마다_따로_센다() {
        long other = newUser("u-2");

        assertThat(dailyQuotaRepository.reserve(userId, 1)).isTrue();
        assertThat(dailyQuotaRepository.reserve(userId, 1)).isFalse();

        assertThat(dailyQuotaRepository.reserve(other, 1)).isTrue();
    }

    // 날짜가 키의 일부라 어제 행은 그대로 남고 오늘은 0에서 시작한다. 이게
    // 깨지면 한 번 한도를 채운 계정이 영영 막힌다.
    @Test
    void 어제_쓴_횟수는_오늘_한도에_영향을_주지_않는다() {
        jdbcClient
                .sql("""
                        INSERT INTO daily_llm_usage (user_id, usage_date, calls)
                        VALUES (:userId, (now() AT TIME ZONE 'Asia/Seoul')::date - 1, 99)
                        """)
                .param("userId", userId)
                .update();

        assertThat(dailyQuotaRepository.usedToday(userId)).isZero();
        assertThat(dailyQuotaRepository.reserve(userId, 1)).isTrue();
    }

    private long newUser(String providerId) {
        return userRepository
                .save(User.builder()
                        .provider("google")
                        .providerId(providerId)
                        .email(providerId + "@example.com")
                        .name("사용자 " + providerId)
                        .build())
                .getId();
    }
}
