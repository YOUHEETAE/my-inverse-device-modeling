package com.semiscopeai.service.chat;

import com.semiscopeai.service.chat.dto.ChatMessageView;
import com.semiscopeai.service.chat.dto.ChatThreadSummary;
import com.semiscopeai.service.chat.dto.ChatThreadView;
import com.semiscopeai.service.chat.dto.ChatTurn;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;
import tools.jackson.databind.json.JsonMapper;

// 대화 기록은 users와 달리 JPA를 쓰지 않는다. 메시지는 append-only 로그에
// 가깝고 읽기도 "최근 N턴" 하나뿐이라, 엔티티 그래프나 더티 체킹에서 얻을
// 게 없다. 대신 SQL이 그대로 보여서 무슨 쿼리가 나가는지 명확하다.
@Repository
public class ChatRepository {

    private final JdbcClient jdbcClient;
    private final JsonMapper jsonMapper;

    public ChatRepository(JdbcClient jdbcClient, JsonMapper jsonMapper) {
        this.jdbcClient = jdbcClient;
        this.jsonMapper = jsonMapper;
    }

    public long createThread(long userId, String kind, Object deviceConfig) {
        return jdbcClient
                .sql("""
                        INSERT INTO chat_thread (user_id, kind, device_config)
                        VALUES (:userId, :kind, CAST(:deviceConfig AS jsonb))
                        RETURNING id
                        """)
                .param("userId", userId)
                .param("kind", kind)
                .param("deviceConfig", jsonMapper.writeValueAsString(deviceConfig))
                .query(Long.class)
                .single();
    }

    // 스레드가 이 사용자의 것인지도 함께 확인한다. 남의 threadId를 넣어
    // 대화를 들여다보거나 이어붙이지 못하게 하려면 조회 조건에 user_id가
    // 반드시 들어가야 한다.
    public boolean threadBelongsTo(long threadId, long userId) {
        return jdbcClient
                .sql("SELECT count(*) FROM chat_thread WHERE id = :id AND user_id = :userId")
                .param("id", threadId)
                .param("userId", userId)
                .query(Long.class)
                .single() > 0;
    }

    // 첫 질문에서 얼려둔 소자 설정. 후속 턴은 화면의 현재 값이 아니라 이걸
    // 다시 써야 대화가 처음 주제를 유지한다 (ChatService.ask 참고).
    public Map<String, Object> deviceConfig(long threadId) {
        return jdbcClient
                .sql("SELECT device_config::text FROM chat_thread WHERE id = :id")
                .param("id", threadId)
                .query(String.class)
                .optional()
                .map(this::readJson)
                .orElseGet(Map::of);
    }

    // 대화 길이 상한을 재는 기준. 실패한 턴은 사용자 잘못이 아니므로 세지
    // 않는다 — 서버 오류로 할당량이 깎이면 안 된다.
    public int turnCount(long threadId) {
        return jdbcClient
                .sql("""
                        SELECT count(*) FROM chat_message
                        WHERE thread_id = :threadId AND source <> 'external_error'
                        """)
                .param("threadId", threadId)
                .query(Integer.class)
                .single();
    }

    // Python은 최근 2턴만 LLM에 넣지만(iv_chat.py), 그 상한은 Python 쪽 구현
    // 사항이라 여기서 몇 턴을 넘길지는 별개로 정한다. 실패한 턴은 맥락으로
    // 되돌려보내지 않으므로 아예 제외한다.
    public List<ChatTurn> recentTurns(long threadId, int limit) {
        List<ChatTurn> newestFirst = jdbcClient
                .sql("""
                        SELECT question, answer, source
                        FROM chat_message
                        WHERE thread_id = :threadId AND source <> 'external_error'
                        ORDER BY created_at DESC, id DESC
                        LIMIT :limit
                        """)
                .param("threadId", threadId)
                .param("limit", limit)
                .query((rs, rowNum) -> ChatTurn.of(
                        rs.getString("question"), rs.getString("answer"), rs.getString("source")))
                .list();

        // Python은 history를 오래된 것부터 받는다(뒤에서 잘라내므로 순서가
        // 뒤집히면 가장 오래된 턴이 최근 턴으로 전달된다).
        return newestFirst.reversed();
    }

    public void appendMessage(
            long threadId,
            String question,
            String answer,
            String source,
            String intent,
            Map<String, Object> intentCheckpoint) {
        jdbcClient
                .sql("""
                        INSERT INTO chat_message
                            (thread_id, question, answer, source, intent, intent_checkpoint)
                        VALUES
                            (:threadId, :question, :answer, :source, :intent,
                             CAST(:checkpoint AS jsonb))
                        """)
                .param("threadId", threadId)
                .param("question", question)
                .param("answer", answer)
                .param("source", source)
                .param("intent", intent)
                .param("checkpoint", intentCheckpoint == null ? null : jsonMapper.writeValueAsString(intentCheckpoint))
                .update();

        // 최근 대화 목록을 정렬하는 기준이라 갱신해준다.
        jdbcClient
                .sql("UPDATE chat_thread SET updated_at = now() WHERE id = :id")
                .param("id", threadId)
                .update();
    }

    // 대화 하나를 통째로 복원한다. 소유자가 아니면 빈 값을 돌려줘, 남의
    // threadId를 찍어봐도 존재 여부조차 알 수 없게 한다.
    public Optional<ChatThreadView> findThread(long threadId, long userId, int messageLimit) {
        List<ChatThreadView> threads = jdbcClient
                .sql("""
                        SELECT id, kind, device_config::text AS device_config, created_at, updated_at
                        FROM chat_thread
                        WHERE id = :id AND user_id = :userId
                        """)
                .param("id", threadId)
                .param("userId", userId)
                .query((rs, rowNum) -> new ChatThreadView(
                        rs.getLong("id"),
                        rs.getString("kind"),
                        readJson(rs.getString("device_config")),
                        rs.getObject("created_at", OffsetDateTime.class).toInstant(),
                        rs.getObject("updated_at", OffsetDateTime.class).toInstant(),
                        List.of(),
                        0,
                        0))
                .list();

        if (threads.isEmpty()) {
            return Optional.empty();
        }
        ChatThreadView thread = threads.get(0);
        return Optional.of(new ChatThreadView(
                thread.threadId(),
                thread.kind(),
                thread.deviceConfig(),
                thread.createdAt(),
                thread.updatedAt(),
                messages(threadId, messageLimit),
                turnCount(threadId),
                0));
    }

    private List<ChatMessageView> messages(long threadId, int limit) {
        return jdbcClient
                .sql("""
                        SELECT id, question, answer, source, intent, created_at
                        FROM chat_message
                        WHERE thread_id = :threadId
                        ORDER BY created_at, id
                        LIMIT :limit
                        """)
                .param("threadId", threadId)
                .param("limit", limit)
                .query((rs, rowNum) -> new ChatMessageView(
                        rs.getLong("id"),
                        rs.getString("question"),
                        rs.getString("answer"),
                        rs.getString("source"),
                        rs.getString("intent"),
                        rs.getObject("created_at", OffsetDateTime.class).toInstant()))
                .list();
    }

    // kind가 null이면 전부, 아니면 그 종류만. I-V 화면에서 Field 대화가
    // 섞이면 고를 수 없고, 한쪽 종류가 상한(limit)을 다 먹어버리기도 한다.
    public List<ChatThreadSummary> listThreads(long userId, String kind, int limit) {
        return jdbcClient
                .sql("""
                        SELECT t.id,
                               t.kind,
                               t.updated_at,
                               t.device_config::text AS device_config,
                               (SELECT m.question FROM chat_message m
                                 WHERE m.thread_id = t.id
                                 ORDER BY m.created_at, m.id LIMIT 1) AS first_question,
                               (SELECT count(*) FROM chat_message m
                                 WHERE m.thread_id = t.id
                                   AND m.source <> 'external_error') AS turns_used
                        FROM chat_thread t
                        WHERE t.user_id = :userId
                          AND (CAST(:kind AS text) IS NULL OR t.kind = CAST(:kind AS text))
                          -- 질문 한 번 못 붙인 대화는 고를 이유가 없다.
                          AND EXISTS (SELECT 1 FROM chat_message m WHERE m.thread_id = t.id)
                        ORDER BY t.updated_at DESC, t.id DESC
                        LIMIT :limit
                        """)
                .param("userId", userId)
                .param("kind", kind)
                .param("limit", limit)
                .query((rs, rowNum) -> new ChatThreadSummary(
                        rs.getLong("id"),
                        rs.getString("kind"),
                        rs.getObject("updated_at", OffsetDateTime.class).toInstant(),
                        rs.getString("first_question"),
                        readJson(rs.getString("device_config")),
                        rs.getInt("turns_used")))
                .list();
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> readJson(String value) {
        return value == null ? Map.of() : jsonMapper.readValue(value, Map.class);
    }

    // 명확화 흐름을 이어가려면 직전 턴이 남긴 checkpoint가 필요하다.
    public Map<String, Object> lastIntentCheckpoint(long threadId) {
        List<String> rows = jdbcClient
                .sql("""
                        SELECT intent_checkpoint FROM chat_message
                        WHERE thread_id = :threadId AND intent_checkpoint IS NOT NULL
                        ORDER BY created_at DESC, id DESC
                        LIMIT 1
                        """)
                .param("threadId", threadId)
                .query(String.class)
                .list();
        if (rows.isEmpty() || rows.get(0) == null) {
            return Map.of();
        }
        return jsonMapper.readValue(rows.get(0), Map.class);
    }
}
