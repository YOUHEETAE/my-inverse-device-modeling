package com.semiscopeai.service.chat;

import static org.assertj.core.api.Assertions.assertThat;

import com.semiscopeai.service.chat.dto.ChatThreadSummary;
import com.semiscopeai.service.chat.dto.ChatTurn;
import com.semiscopeai.service.support.ChatPersistenceTestApp;
import com.semiscopeai.service.user.User;
import com.semiscopeai.service.user.UserRepository;
import java.util.List;
import java.util.Map;
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

// 이 리포지토리는 jsonb 캐스팅과 RETURNING 같은 PostgreSQL 전용 SQL을 쓰기
// 때문에 H2로 검증하면 의미가 없다(통과해도 실제로 깨질 수 있다). 진짜
// PostgreSQL을 띄우고, 스키마도 Flyway 마이그레이션이 그대로 만들게 한다 —
// 덕분에 마이그레이션 SQL 자체도 여기서 함께 검증된다.
// 컨테이너는 클래스 전체가 공유하므로 테스트마다 롤백해 서로 격리한다.
@SpringBootTest(classes = ChatPersistenceTestApp.class)
@Testcontainers
@Transactional
@ActiveProfiles("test-postgres")
class ChatRepositoryTest {

    @Container
    @ServiceConnection
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:17-alpine");

    @Autowired
    private ChatRepository chatRepository;

    @Autowired
    private UserRepository userRepository;

    private long userId;

    @BeforeEach
    void createUser() {
        userId = userRepository
                .save(User.builder().provider("google").providerId("u-1").email("a@example.com").name("홍길동").build())
                .getId();
    }

    @Test
    void 대화를_만들고_메시지를_쌓는다() {
        long threadId = chatRepository.createThread(userId, "curves", Map.of("L", "500"));

        chatRepository.appendMessage(threadId, "Ion은?", "6.28", "external_llm", "explain_metric", Map.of());

        assertThat(chatRepository.recentTurns(threadId, 10))
                .singleElement()
                .satisfies(turn -> {
                    assertThat(turn.question()).isEqualTo("Ion은?");
                    assertThat(turn.answer()).isEqualTo("6.28");
                });
    }

    // Python은 실패한 턴을 맥락으로 쓰지 않는다. 저장은 하되(화면에 이미
    // 보여준 내용이라) 이력으로는 넘기지 않아야 한다.
    @Test
    void 실패한_턴은_이력에서_제외된다() {
        long threadId = chatRepository.createThread(userId, "curves", Map.of());
        chatRepository.appendMessage(threadId, "질문1", "정상 답변", "external_llm", "explain_metric", Map.of());
        chatRepository.appendMessage(threadId, "질문2", "생성 실패", "external_error", null, null);

        List<ChatTurn> turns = chatRepository.recentTurns(threadId, 10);

        assertThat(turns).singleElement().extracting(ChatTurn::question).isEqualTo("질문1");
    }

    // Python은 history를 오래된 것부터 받는다. 뒤에서 잘라내기 때문에 순서가
    // 뒤집히면 가장 오래된 턴이 "최근 턴"으로 전달된다.
    @Test
    void 이력은_오래된_순서로_돌려준다() {
        long threadId = chatRepository.createThread(userId, "curves", Map.of());
        chatRepository.appendMessage(threadId, "첫번째", "a", "external_llm", null, null);
        chatRepository.appendMessage(threadId, "두번째", "b", "external_llm", null, null);
        chatRepository.appendMessage(threadId, "세번째", "c", "external_llm", null, null);

        assertThat(chatRepository.recentTurns(threadId, 10))
                .extracting(ChatTurn::question)
                .containsExactly("첫번째", "두번째", "세번째");
    }

    @Test
    void 최근_N턴만_가져오되_순서는_유지한다() {
        long threadId = chatRepository.createThread(userId, "curves", Map.of());
        chatRepository.appendMessage(threadId, "첫번째", "a", "external_llm", null, null);
        chatRepository.appendMessage(threadId, "두번째", "b", "external_llm", null, null);
        chatRepository.appendMessage(threadId, "세번째", "c", "external_llm", null, null);

        assertThat(chatRepository.recentTurns(threadId, 2))
                .extracting(ChatTurn::question)
                .containsExactly("두번째", "세번째");
    }

    // 남의 threadId를 넘겨 대화를 이어붙이거나 훔쳐보지 못해야 한다.
    @Test
    void 다른_사용자의_대화는_소유자로_인정되지_않는다() {
        long threadId = chatRepository.createThread(userId, "curves", Map.of());
        long otherUserId = userRepository
                .save(User.builder().provider("google").providerId("u-2").email("b@example.com").name("김철수").build())
                .getId();

        assertThat(chatRepository.threadBelongsTo(threadId, userId)).isTrue();
        assertThat(chatRepository.threadBelongsTo(threadId, otherUserId)).isFalse();
    }

    @Test
    void 다른_사용자는_대화를_조회할_수_없다() {
        long threadId = chatRepository.createThread(userId, "curves", Map.of("L", "500"));
        long otherUserId = userRepository
                .save(User.builder().provider("google").providerId("u-3").email("c@example.com").name("이영희").build())
                .getId();

        assertThat(chatRepository.findThread(threadId, userId, 100)).isPresent();
        assertThat(chatRepository.findThread(threadId, otherUserId, 100)).isEmpty();
    }

    // 소자 조건을 남겨야 "그때 무슨 설정으로 물어봤더라"를 복원할 수 있다.
    @Test
    void 조회하면_소자_조건과_실패한_턴까지_함께_복원된다() {
        long threadId = chatRepository.createThread(userId, "fields", Map.of("display", "Potential"));
        chatRepository.appendMessage(threadId, "질문1", "답변", "external_llm", "explain_region", Map.of());
        chatRepository.appendMessage(threadId, "질문2", "실패", "external_error", null, null);

        var thread = chatRepository.findThread(threadId, userId, 100).orElseThrow();

        assertThat(thread.kind()).isEqualTo("fields");
        assertThat(thread.deviceConfig()).containsEntry("display", "Potential");
        // 이력(recentTurns)과 달리 조회는 실패한 턴도 보여준다.
        assertThat(thread.messages()).hasSize(2);
    }

    // 서버 오류로 답을 못 받은 턴이 사용자의 질문 할당량을 깎으면 안 된다.
    @Test
    void 턴_수를_셀_때_실패한_턴은_빼고_센다() {
        long threadId = chatRepository.createThread(userId, "curves", Map.of());
        chatRepository.appendMessage(threadId, "질문1", "답변", "external_llm", null, null);
        chatRepository.appendMessage(threadId, "질문2", "생성 실패", "external_error", null, null);
        chatRepository.appendMessage(threadId, "질문3", "답변", "external_llm", null, null);

        assertThat(chatRepository.turnCount(threadId)).isEqualTo(2);
    }

    @Test
    void 조회한_대화는_사용한_턴_수를_함께_준다() {
        long threadId = chatRepository.createThread(userId, "curves", Map.of());
        chatRepository.appendMessage(threadId, "질문1", "답변", "external_llm", null, null);
        chatRepository.appendMessage(threadId, "질문2", "생성 실패", "external_error", null, null);

        var thread = chatRepository.findThread(threadId, userId, 100).orElseThrow();

        // 말풍선은 2개지만 소모한 턴은 1개다.
        assertThat(thread.messages()).hasSize(2);
        assertThat(thread.turnsUsed()).isEqualTo(1);
    }

    @Test
    void 마지막_checkpoint를_가져온다() {
        long threadId = chatRepository.createThread(userId, "curves", Map.of());
        chatRepository.appendMessage(threadId, "q1", "a1", "external_llm", null, Map.of("intent", "clarify"));
        chatRepository.appendMessage(threadId, "q2", "a2", "external_llm", null, Map.of("intent", "explain_metric"));

        assertThat(chatRepository.lastIntentCheckpoint(threadId)).containsEntry("intent", "explain_metric");
    }

    @Test
    void 목록은_최근_대화부터_준다() {
        long first = chatRepository.createThread(userId, "curves", Map.of());
        chatRepository.appendMessage(first, "오래된 질문", "a", "external_llm", null, null);
        long second = chatRepository.createThread(userId, "fields", Map.of());
        chatRepository.appendMessage(second, "최근 질문", "b", "external_llm", null, null);

        assertThat(chatRepository.listThreads(userId, null, 10))
                .extracting(ChatThreadSummary::firstQuestion)
                .containsExactly("최근 질문", "오래된 질문");
    }

    // 마지막 질문은 곁가지일 수 있다("감기에 걸렸어" 같은 범위 밖 질문).
    // 주제를 정한 건 첫 질문이라 그쪽이 대화를 대표한다.
    @Test
    void 미리보기는_마지막이_아니라_첫_질문이다() {
        long threadId = chatRepository.createThread(userId, "curves", Map.of());
        chatRepository.appendMessage(threadId, "SS가 왜 나빠졌어?", "답변", "external_llm", null, null);
        chatRepository.appendMessage(threadId, "감기에 걸렸어", "범위 밖", "external_llm", null, null);

        assertThat(chatRepository.listThreads(userId, null, 10))
                .singleElement()
                .extracting(ChatThreadSummary::firstQuestion)
                .isEqualTo("SS가 왜 나빠졌어?");
    }

    // 질문 문장만으로는 대화를 구분할 수 없다 — 같은 화면에서 비슷하게
    // 물으면 미리보기가 전부 같아지고, 정작 다른 건 소자 조건이다.
    @Test
    void 목록은_소자_조건도_함께_준다() {
        long threadId = chatRepository.createThread(userId, "curves", Map.of("L", "500"));
        chatRepository.appendMessage(threadId, "질문", "답변", "external_llm", null, null);

        assertThat(chatRepository.listThreads(userId, null, 10))
                .singleElement()
                .extracting(ChatThreadSummary::deviceConfig)
                .isEqualTo(Map.of("L", "500"));
    }

    @Test
    void 종류로_거를_수_있다() {
        long curves = chatRepository.createThread(userId, "curves", Map.of());
        chatRepository.appendMessage(curves, "커브 질문", "a", "external_llm", null, null);
        long fields = chatRepository.createThread(userId, "fields", Map.of());
        chatRepository.appendMessage(fields, "필드 질문", "b", "external_llm", null, null);

        assertThat(chatRepository.listThreads(userId, "curves", 10))
                .singleElement()
                .extracting(ChatThreadSummary::firstQuestion)
                .isEqualTo("커브 질문");
    }

    // 실패한 턴만 남은 대화도 목록에는 나와야 한다 — 사용자가 다시 시도할
    // 수 있어야 하니까. 대신 소모 턴은 0이다.
    @Test
    void 실패만_있는_대화도_목록에_나오되_턴은_0이다() {
        long threadId = chatRepository.createThread(userId, "curves", Map.of());
        chatRepository.appendMessage(threadId, "질문", "생성 실패", "external_error", null, null);

        assertThat(chatRepository.listThreads(userId, null, 10))
                .singleElement()
                .extracting(ChatThreadSummary::turnsUsed)
                .isEqualTo(0);
    }

    // 질문이 하나도 안 붙은 대화는 고를 이유가 없다.
    @Test
    void 빈_대화는_목록에서_빠진다() {
        chatRepository.createThread(userId, "curves", Map.of());

        assertThat(chatRepository.listThreads(userId, null, 10)).isEmpty();
    }
}
