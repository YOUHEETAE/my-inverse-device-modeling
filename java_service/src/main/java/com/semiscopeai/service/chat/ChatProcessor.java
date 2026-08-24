package com.semiscopeai.service.chat;

import com.semiscopeai.service.chat.dto.ChatAnswer;
import com.semiscopeai.service.chat.dto.ChatTurn;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

/**
 * 자유질문의 DB 단계. 트랜잭션은 여기에만 있고, LLM 호출은 {@link ChatService}가
 * 이 메서드들 사이에서 트랜잭션 밖으로 한다.
 *
 * <p>클래스를 나눈 건 스타일 때문만이 아니다. 같은 클래스 안에서 부르면
 * 스프링 프록시를 거치지 않아 {@code @Transactional}이 조용히 무시된다.
 */
@Component
public class ChatProcessor {

    private final ChatRepository chatRepository;

    public ChatProcessor(ChatRepository chatRepository) {
        this.chatRepository = chatRepository;
    }

    /** 이어가는 대화에 필요한 것들. 첫 질문이면 {@link #firstTurn}을 쓴다. */
    public record Context(List<ChatTurn> history, Map<String, Object> checkpoint, Map<String, Object> deviceConfig) {

        public static Context firstTurn(Map<String, Object> deviceConfig) {
            return new Context(List.of(), Map.of(), deviceConfig);
        }
    }

    /**
     * 이어가는 대화의 맥락을 한 번에 읽는다. 소유자 확인과 턴 상한도 여기서
     * 본다 — 읽기 한 트랜잭션 안에서 검사와 조회가 같은 시점을 보게 된다.
     */
    @Transactional(readOnly = true)
    public Context loadContext(long threadId, long userId, int historyTurns, int maxTurns) {
        if (!chatRepository.threadBelongsTo(threadId, userId)) {
            // 남의 대화는 존재 여부조차 알리지 않는다.
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "대화를 찾을 수 없습니다.");
        }
        if (chatRepository.turnCount(threadId) >= maxTurns) {
            // 400이 아니라 409 — 요청은 멀쩡하고 대화의 상태가 문제다.
            throw new ResponseStatusException(
                    HttpStatus.CONFLICT, "이 대화는 질문 " + maxTurns + "개를 채웠습니다. 새 대화를 시작해 주세요.");
        }
        return new Context(
                chatRepository.recentTurns(threadId, historyTurns),
                chatRepository.lastIntentCheckpoint(threadId),
                chatRepository.deviceConfig(threadId));
    }

    public long openThread(long userId, String kind, Map<String, Object> deviceConfig) {
        return chatRepository.createThread(userId, kind, deviceConfig);
    }

    /**
     * 한 턴을 저장하고 소모한 턴 수를 돌려준다.
     *
     * <p>메시지 저장과 대화의 updated_at 갱신이 함께 일어나야 목록 정렬이
     * 어긋나지 않아서 트랜잭션으로 묶는다.
     */
    @Transactional
    public int recordTurn(long threadId, String question, ChatAnswer answer) {
        chatRepository.appendMessage(
                threadId, question, answer.answer(), answer.source(), answer.intent(), answer.intentCheckpoint());
        return chatRepository.turnCount(threadId);
    }
}
