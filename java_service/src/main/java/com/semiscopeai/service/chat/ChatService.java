package com.semiscopeai.service.chat;

import com.semiscopeai.service.chat.dto.ChatAnswer;
import com.semiscopeai.service.chat.dto.ChatReply;
import com.semiscopeai.service.chat.dto.ChatTurn;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
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

    // 한 대화에 담을 수 있는 턴 수. 비용 문제가 아니다 — LLM에 가는 토큰은
    // 대화 길이와 무관하게 최근 2턴으로 고정이다.
    //
    // 말풍선이 수십 개 쌓이면 사용자는 AI가 그걸 다 기억한다고 믿게 되는데,
    // 실제로 기억하는 건 2턴뿐이다. 상한에서 새 대화를 열게 해서 그 간극을
    // 숨기지 않는다. 오래된 intent_checkpoint가 계속 따라다니며 맥락을
    // 어지럽히는 것도 여기서 끊긴다.
    public static final int MAX_TURNS_PER_THREAD = 20;

    private final ChatRepository chatRepository;

    public ChatService(ChatRepository chatRepository) {
        this.chatRepository = chatRepository;
    }

    /**
     * 첫 질문이 소자 설정을 얼리고, 이후 턴은 그 설정을 다시 쓴다.
     *
     * <p>데스크톱 앱과 같은 규칙이다(frontend/visualization/explanation_panel.py의
     * {@code iv_chat_snapshot}). 매 턴 화면의 현재 설정을 보내면, 사용자가
     * 파라미터를 바꾼 순간 말풍선 위쪽은 옛 소자 얘기인데 새 답변은 다른
     * 소자 얘기가 된다. "그 값은 좋은 편이야?" 같은 질문이 조용히 엉뚱한
     * 대상에 답하게 되는데, 오류도 나지 않아 알아챌 방법이 없다.
     *
     * <p>얼려두면 대화 중에 파라미터를 얼마든지 바꿔도 이 대화는 원래 주제를
     * 유지한다. 바뀐 설정으로 묻고 싶으면 새 대화를 시작하면 된다.
     */
    @Transactional
    public ChatReply ask(
            long userId,
            Long requestedThreadId,
            String kind,
            Map<String, Object> deviceConfig,
            String question,
            Function<Map<String, Object>, ChatAnswer> callPython) {

        long threadId = resolveThread(userId, requestedThreadId, kind, deviceConfig);
        List<ChatTurn> history = chatRepository.recentTurns(threadId, HISTORY_TURNS);
        Map<String, Object> checkpoint = chatRepository.lastIntentCheckpoint(threadId);

        // 첫 턴이면 방금 저장한 값을, 이어가는 턴이면 처음에 얼린 값을 읽는다.
        // 요청에 실려온 설정을 쓰지 않는 게 핵심이다.
        Map<String, Object> frozen = chatRepository.deviceConfig(threadId);

        Map<String, Object> body = new LinkedHashMap<>(frozen);
        body.put("question", question);
        body.put("history", history);
        body.put("intent_checkpoint", checkpoint);

        ChatAnswer answer = callPython.apply(body);

        // 실패한 턴도 남긴다. 화면에 이미 보여준 내용이라 새로고침하면 사라지는
        // 게 더 이상하고, 다음 질문의 맥락으로는 조회 단계에서 걸러진다.
        chatRepository.appendMessage(
                threadId, question, answer.answer(), answer.source(), answer.intent(), answer.intentCheckpoint());

        return ChatReply.of(threadId, answer, chatRepository.turnCount(threadId), MAX_TURNS_PER_THREAD);
    }

    private long resolveThread(
            long userId, Long requestedThreadId, String kind, Map<String, Object> deviceConfig) {
        if (requestedThreadId == null) {
            return chatRepository.createThread(userId, kind, deviceConfig);
        }
        // 남의 threadId를 넘겨 대화를 훔쳐보거나 이어붙이지 못하게 막는다.
        if (!chatRepository.threadBelongsTo(requestedThreadId, userId)) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "대화를 찾을 수 없습니다.");
        }
        // 400이 아니라 409인 이유: 요청 자체는 멀쩡하고 대화의 상태가 문제다.
        // 프론트는 이 코드를 보고 오류 대신 "새 대화 시작"을 띄운다.
        if (chatRepository.turnCount(requestedThreadId) >= MAX_TURNS_PER_THREAD) {
            throw new ResponseStatusException(
                    HttpStatus.CONFLICT,
                    "이 대화는 질문 " + MAX_TURNS_PER_THREAD + "개를 채웠습니다. 새 대화를 시작해 주세요.");
        }
        return requestedThreadId;
    }
}
