package com.semiscopeai.service.casestudy;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import java.util.function.UnaryOperator;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

/**
 * 학습 세션의 한 걸음: 꺼내고 → Python에 맡기고 → 돌려받아 저장한다.
 *
 * <p>여기에 {@code @Transactional}이 없는 건 빠뜨린 게 아니다. 가운데 있는
 * Python 호출은 모델 추론이나 LLM 채점이라 수 초에서 수십 초가 걸린다.
 * 트랜잭션으로 감싸면 그동안 커넥션을 붙잡고 있게 되고, 동시 사용자가 풀
 * 크기를 넘는 순간 학습과 무관한 요청까지 함께 멈춘다.
 *
 * <p>읽기와 쓰기가 각각 단일 문장이라 원자성도 따로 필요없다. 대신 중간에
 * 실패하면 세션은 이전 상태로 남는데, 그게 오히려 맞는 동작이다 — 실패한
 * 걸음은 반영되지 않아야 하고, Python 라우터가 제출과 실행을 나눠둔 덕에
 * 학습자가 적은 답변은 이미 저장되어 있다.
 */
@Service
public class LearningService {

    private final LearningRepository learningRepository;

    public LearningService(LearningRepository learningRepository) {
        this.learningRepository = learningRepository;
    }

    public Map<String, Object> require(UUID sessionId, long userId) {
        return learningRepository
                .find(sessionId, userId)
                // 남의 세션은 존재 여부조차 알리지 않는다.
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "학습 기록을 찾을 수 없습니다."));
    }

    /** 세션을 Python에 보내 한 걸음 진행시키고, 돌아온 세션을 저장한다. */
    public Map<String, Object> advance(
            UUID sessionId, long userId, UnaryOperator<Map<String, Object>> callPython) {
        Map<String, Object> updated = callPython.apply(require(sessionId, userId));
        return persist(userId, updated);
    }

    public Map<String, Object> persist(long userId, Map<String, Object> session) {
        if (learningRepository.save(userId, session) == 0) {
            // ON CONFLICT의 소유자 조건에 걸린 경우 — 이미 남의 것인 id다.
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "학습 기록을 찾을 수 없습니다.");
        }
        return session;
    }

    /** Python 호출 본문. 세션을 그대로 실어 보낸다. */
    public static Map<String, Object> body(Map<String, Object> session) {
        Map<String, Object> value = new LinkedHashMap<>();
        value.put("session", session);
        return value;
    }

    public static Map<String, Object> body(Map<String, Object> session, String key, Object extra) {
        Map<String, Object> value = body(session);
        value.put(key, extra);
        return value;
    }
}
