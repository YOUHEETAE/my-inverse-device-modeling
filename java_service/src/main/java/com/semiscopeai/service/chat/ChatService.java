package com.semiscopeai.service.chat;

import com.semiscopeai.service.chat.dto.ChatAnswer;
import com.semiscopeai.service.chat.dto.ChatReply;
import com.semiscopeai.service.chat.dto.ChatTurn;
import java.util.List;
import java.util.Map;
import java.util.function.BiFunction;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

// 컨트롤러가 얇게 유지되도록 "이력을 꺼내 Python에 넘기고 결과를 저장하는"
// 흐름을 여기 모은다. curves/fields 두 경로가 이 흐름을 공유한다.
//
// 로그인은 SecurityConfig에서 이미 강제되므로 여기서 익명 사용자를 다루지
// 않는다.
@Service
public class ChatService {

    // Python은 최근 2턴만 LLM에 넘기지만, 그건 Python 쪽 구현 사항이다.
    // 여기서 조금 더 보내두면 Python이 상한을 바꿔도 자바를 고칠 필요가 없다.
    private static final int HISTORY_TURNS = 6;

    private final ChatRepository chatRepository;

    public ChatService(ChatRepository chatRepository) {
        this.chatRepository = chatRepository;
    }

    @Transactional
    public ChatReply ask(
            long userId,
            Long requestedThreadId,
            String kind,
            Object deviceConfig,
            String question,
            BiFunction<List<ChatTurn>, Map<String, Object>, ChatAnswer> callPython) {

        long threadId = resolveThread(userId, requestedThreadId, kind, deviceConfig);
        List<ChatTurn> history = chatRepository.recentTurns(threadId, HISTORY_TURNS);
        Map<String, Object> checkpoint = chatRepository.lastIntentCheckpoint(threadId);

        ChatAnswer answer = callPython.apply(history, checkpoint);

        // 실패한 턴도 남긴다. 화면에 이미 보여준 내용이라 새로고침하면 사라지는
        // 게 더 이상하고, 다음 질문의 맥락으로는 조회 단계에서 걸러진다.
        chatRepository.appendMessage(
                threadId, question, answer.answer(), answer.source(), answer.intent(), answer.intentCheckpoint());

        return ChatReply.of(threadId, answer);
    }

    private long resolveThread(long userId, Long requestedThreadId, String kind, Object deviceConfig) {
        if (requestedThreadId == null) {
            return chatRepository.createThread(userId, kind, deviceConfig);
        }
        // 남의 threadId를 넘겨 대화를 훔쳐보거나 이어붙이지 못하게 막는다.
        if (!chatRepository.threadBelongsTo(requestedThreadId, userId)) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "대화를 찾을 수 없습니다.");
        }
        return requestedThreadId;
    }
}
