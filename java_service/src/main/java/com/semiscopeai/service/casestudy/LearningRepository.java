package com.semiscopeai.service.casestudy;

import com.semiscopeai.service.casestudy.dto.SessionSummary;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;
import tools.jackson.databind.json.JsonMapper;

// 학습 세션 보관. 세션의 내용은 Python 소유라 자바는 통째로 넣고 뺀다 —
// 목록에 필요한 값(제목, 단계, 완료 여부)만 JSON에서 꺼내 읽는다.
@Repository
public class LearningRepository {

    private final JdbcClient jdbcClient;
    private final JsonMapper jsonMapper;

    public LearningRepository(JdbcClient jdbcClient, JsonMapper jsonMapper) {
        this.jdbcClient = jdbcClient;
        this.jsonMapper = jsonMapper;
    }

    // Python이 세션을 갱신해 돌려줄 때마다 덮어쓴다. session_id가 Python이
    // 발급한 값이라 INSERT와 UPDATE를 나눌 필요가 없다.
    //
    // ON CONFLICT에 user_id 조건이 붙어 있는 게 중요하다. 없으면 남의
    // session_id를 실어 보내는 것만으로 그 사람의 학습 기록을 덮어쓸 수
    // 있다 — 충돌 시에는 INSERT의 WHERE가 적용되지 않기 때문이다.
    // 조건이 어긋나면 아무 행도 바뀌지 않고, 호출부가 그걸 오류로 올린다.
    public int save(long userId, Map<String, Object> session) {
        return jdbcClient
                .sql("""
                        INSERT INTO learning_session (session_id, user_id, topic_id, session)
                        VALUES (CAST(:sessionId AS uuid), :userId, :topicId, CAST(:session AS jsonb))
                        ON CONFLICT (session_id) DO UPDATE
                           SET session = EXCLUDED.session, updated_at = now()
                         WHERE learning_session.user_id = :userId
                        """)
                .param("sessionId", sessionId(session))
                .param("userId", userId)
                .param("topicId", String.valueOf(session.get("topic_id")))
                .param("session", jsonMapper.writeValueAsString(session))
                .update();
    }

    // 소유자가 아니면 빈 값. 남의 session_id를 찍어봐도 존재 여부를 알 수 없다.
    public Optional<Map<String, Object>> find(UUID sessionId, long userId) {
        return jdbcClient
                .sql("""
                        SELECT session::text FROM learning_session
                        WHERE session_id = :sessionId AND user_id = :userId
                        """)
                .param("sessionId", sessionId)
                .param("userId", userId)
                .query(String.class)
                .optional()
                .map(this::readJson);
    }

    // 학습 현황(portfolio)은 사용자의 모든 세션을 재료로 계산된다.
    public List<Map<String, Object>> findAll(long userId) {
        return jdbcClient
                .sql("SELECT session::text FROM learning_session WHERE user_id = :userId ORDER BY updated_at DESC")
                .param("userId", userId)
                .query(String.class)
                .list()
                .stream()
                .map(this::readJson)
                .toList();
    }

    // 케이스 화면의 "학습 기록" 목록. 세션 전체를 내려보내면 한 건에 30KB라
    // 고르는 데 필요한 값만 추린다.
    public List<SessionSummary> summaries(long userId, String topicId) {
        return jdbcClient
                .sql("""
                        SELECT session_id,
                               topic_id,
                               updated_at,
                               session ->> 'display_name'  AS display_name,
                               session ->> 'current_step'  AS current_step,
                               session ->> 'completed_at'  AS completed_at
                        FROM learning_session
                        WHERE user_id = :userId
                          AND (CAST(:topicId AS text) IS NULL OR topic_id = CAST(:topicId AS text))
                        ORDER BY updated_at DESC
                        """)
                .param("userId", userId)
                .param("topicId", topicId)
                .query((rs, rowNum) -> new SessionSummary(
                        rs.getObject("session_id", UUID.class),
                        rs.getString("topic_id"),
                        rs.getString("display_name"),
                        rs.getString("current_step"),
                        rs.getString("completed_at") != null,
                        rs.getObject("updated_at", OffsetDateTime.class).toInstant()))
                .list();
    }

    // 이름 바꾸기는 저장된 JSON 안의 display_name을 고치는 일이라 Python을
    // 거칠 이유가 없다 (데스크톱 앱의 _rename_selected_session).
    public boolean rename(UUID sessionId, long userId, String displayName) {
        return jdbcClient
                .sql("""
                        UPDATE learning_session
                           SET session = jsonb_set(session, '{display_name}', to_jsonb(CAST(:name AS text))),
                               updated_at = now()
                        WHERE session_id = :sessionId AND user_id = :userId
                        """)
                .param("name", displayName)
                .param("sessionId", sessionId)
                .param("userId", userId)
                .update() > 0;
    }

    public boolean delete(UUID sessionId, long userId) {
        return jdbcClient
                .sql("DELETE FROM learning_session WHERE session_id = :sessionId AND user_id = :userId")
                .param("sessionId", sessionId)
                .param("userId", userId)
                .update() > 0;
    }

    private String sessionId(Map<String, Object> session) {
        Object value = session.get("session_id");
        if (value == null) {
            throw new IllegalArgumentException("session_id_missing");
        }
        return String.valueOf(value);
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> readJson(String value) {
        return jsonMapper.readValue(value, Map.class);
    }
}
