package com.semiscopeai.service.casestudy;

import static org.assertj.core.api.Assertions.assertThat;

import com.semiscopeai.service.casestudy.dto.SessionSummary;
import com.semiscopeai.service.support.PersistenceTestApp;
import com.semiscopeai.service.user.User;
import com.semiscopeai.service.user.UserRepository;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.annotation.Transactional;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

// jsonb 캐스팅과 jsonb_set, ON CONFLICT ... WHERE 를 쓰기 때문에 H2로는
// 검증이 성립하지 않는다. 진짜 PostgreSQL을 띄우고 스키마는 Flyway가 만든다.
@SpringBootTest(classes = PersistenceTestApp.class)
@Testcontainers
@Transactional
@ActiveProfiles("test-postgres")
class LearningRepositoryTest {

    @Container
    @ServiceConnection
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:17-alpine");

    @Autowired
    private LearningRepository learningRepository;

    @Autowired
    private UserRepository userRepository;

    private long userId;
    private long otherUserId;

    @BeforeEach
    void createUsers() {
        userId = save("u-1", "a@example.com");
        otherUserId = save("u-2", "b@example.com");
    }

    private long save(String providerId, String email) {
        return userRepository
                .save(User.builder().provider("google").providerId(providerId).email(email).name("학습자").build())
                .getId();
    }

    private Map<String, Object> session(UUID id, String step) {
        return Map.of(
                "session_id", id.toString(),
                "topic_id", "sce_channel_length",
                "current_step", step,
                "display_name", "새 학습 세션");
    }

    @Test
    void 세션을_저장하고_꺼낸다() {
        UUID id = UUID.randomUUID();
        learningRepository.save(userId, session(id, "INTRODUCTION"));

        assertThat(learningRepository.find(id, userId))
                .get()
                .extracting(value -> value.get("current_step"))
                .isEqualTo("INTRODUCTION");
    }

    // 같은 session_id로 다시 저장하면 덮어쓴다 — Python이 걸음마다 갱신된
    // 세션을 돌려주기 때문에 INSERT와 UPDATE를 나누지 않는다.
    @Test
    void 같은_세션은_덮어쓴다() {
        UUID id = UUID.randomUUID();
        learningRepository.save(userId, session(id, "INTRODUCTION"));
        learningRepository.save(userId, session(id, "PREDICTION_QUESTION"));

        assertThat(learningRepository.findAll(userId)).hasSize(1);
        assertThat(learningRepository.find(id, userId))
                .get()
                .extracting(value -> value.get("current_step"))
                .isEqualTo("PREDICTION_QUESTION");
    }

    // ON CONFLICT에 소유자 조건이 없으면 남의 session_id를 실어 보내는
    // 것만으로 그 사람의 학습 기록을 덮어쓸 수 있다 — 충돌 시에는 INSERT의
    // 조건이 적용되지 않기 때문이다.
    @Test
    void 남의_세션은_덮어쓰지_못한다() {
        UUID id = UUID.randomUUID();
        learningRepository.save(userId, session(id, "INTRODUCTION"));

        int changed = learningRepository.save(otherUserId, session(id, "SESSION_COMPLETE"));

        assertThat(changed).isZero();
        assertThat(learningRepository.find(id, userId))
                .get()
                .extracting(value -> value.get("current_step"))
                .isEqualTo("INTRODUCTION");
    }

    @Test
    void 남의_세션은_읽지_못한다() {
        UUID id = UUID.randomUUID();
        learningRepository.save(userId, session(id, "INTRODUCTION"));

        assertThat(learningRepository.find(id, otherUserId)).isEmpty();
        assertThat(learningRepository.findAll(otherUserId)).isEmpty();
    }

    @Test
    void 남의_세션은_지우거나_이름을_바꾸지_못한다() {
        UUID id = UUID.randomUUID();
        learningRepository.save(userId, session(id, "INTRODUCTION"));

        assertThat(learningRepository.rename(id, otherUserId, "가로채기")).isFalse();
        assertThat(learningRepository.delete(id, otherUserId)).isFalse();
        assertThat(learningRepository.find(id, userId)).isPresent();
    }

    // 이름 바꾸기는 저장된 JSON 안의 값을 고치는 일이라 Python을 거치지 않는다.
    @Test
    void 이름을_바꿔도_나머지_세션은_그대로다() {
        UUID id = UUID.randomUUID();
        learningRepository.save(userId, session(id, "PREDICTION_QUESTION"));

        assertThat(learningRepository.rename(id, userId, "두 번째 시도")).isTrue();

        Map<String, Object> stored = learningRepository.find(id, userId).orElseThrow();
        assertThat(stored.get("display_name")).isEqualTo("두 번째 시도");
        assertThat(stored.get("current_step")).isEqualTo("PREDICTION_QUESTION");
    }

    // 목록은 세션 전체(30KB)를 싣지 않고 고르는 데 필요한 값만 추린다.
    @Test
    void 목록은_케이스별로_거를_수_있다() {
        learningRepository.save(userId, session(UUID.randomUUID(), "INTRODUCTION"));
        learningRepository.save(
                userId,
                Map.of(
                        "session_id", UUID.randomUUID().toString(),
                        "topic_id", "oxide_gate_control",
                        "current_step", "INTRODUCTION",
                        "display_name", "다른 케이스"));

        assertThat(learningRepository.summaries(userId, null)).hasSize(2);
        assertThat(learningRepository.summaries(userId, "sce_channel_length"))
                .singleElement()
                .extracting(SessionSummary::topicId)
                .isEqualTo("sce_channel_length");
    }

    // 완료 여부는 completed_at이 채워졌는지로 판단한다 — 목록에서 "완료"
    // 배지를 띄우는 값이다.
    @Test
    void 완료_여부를_요약에_담는다() {
        UUID open = UUID.randomUUID();
        UUID done = UUID.randomUUID();
        learningRepository.save(userId, session(open, "INTRODUCTION"));
        learningRepository.save(
                userId,
                Map.of(
                        "session_id", done.toString(),
                        "topic_id", "sce_channel_length",
                        "current_step", "SESSION_COMPLETE",
                        "display_name", "끝낸 세션",
                        "completed_at", "2026-08-25T00:00:00Z"));

        assertThat(learningRepository.summaries(userId, null))
                .filteredOn(SessionSummary::completed)
                .singleElement()
                .extracting(SessionSummary::sessionId)
                .isEqualTo(done);
    }
}
