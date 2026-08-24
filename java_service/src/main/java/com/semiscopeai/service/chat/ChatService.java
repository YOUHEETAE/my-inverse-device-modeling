package com.semiscopeai.service.chat;

import com.semiscopeai.service.chat.dto.ChatAnswer;
import com.semiscopeai.service.chat.dto.ChatReply;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.function.Function;
import org.springframework.stereotype.Service;

// 컨트롤러가 얇게 유지되도록 "이력을 꺼내 Python에 넘기고 결과를 저장하는"
// 흐름을 여기 모은다. curves/fields 두 경로가 이 흐름을 공유한다.
//
// 로그인은 SecurityConfig에서 이미 강제되므로 여기서 익명 사용자를 다루지
// 않는다.
//
// 이 클래스에는 @Transactional이 없다. 가운데 LLM 호출이 수십 초까지 걸리는데
// 트랜잭션으로 감싸면 그동안 DB 커넥션을 붙잡고 있게 되고, 동시 질문이 풀
// 크기(HikariCP 기본 10)를 넘는 순간 로그인 확인 같은 무관한 요청까지 함께
// 멈춘다. DB 단계는 ChatProcessor가 짧은 트랜잭션으로 처리한다.
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

    private final ChatProcessor chatProcessor;

    public ChatService(ChatProcessor chatProcessor) {
        this.chatProcessor = chatProcessor;
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
    public ChatReply ask(
            long userId,
            Long requestedThreadId,
            String kind,
            Map<String, Object> deviceConfig,
            String question,
            Function<Map<String, Object>, ChatAnswer> callPython) {

        // 첫 질문이면 요청에 실려온 설정이 곧 얼린 설정이 된다. 이어가는
        // 질문이면 처음에 얼린 값을 읽어 쓴다 — 요청의 설정은 쓰지 않는다.
        ChatProcessor.Context context = requestedThreadId == null
                ? ChatProcessor.Context.firstTurn(deviceConfig)
                : chatProcessor.loadContext(requestedThreadId, userId, HISTORY_TURNS, MAX_TURNS_PER_THREAD);

        Map<String, Object> body = new LinkedHashMap<>(context.deviceConfig());
        body.put("question", question);
        body.put("history", context.history());
        body.put("intent_checkpoint", context.checkpoint());

        ChatAnswer answer = callPython.apply(body);

        // 대화는 답이 온 뒤에 만든다. 미리 만들면 Python 호출이 통째로
        // 실패했을 때 질문 한 줄 없는 빈 대화가 남는다.
        long threadId = requestedThreadId != null
                ? requestedThreadId
                : chatProcessor.openThread(userId, kind, deviceConfig);

        // 실패한 턴도 남긴다. 화면에 이미 보여준 내용이라 새로고침하면 사라지는
        // 게 더 이상하고, 다음 질문의 맥락으로는 조회 단계에서 걸러진다.
        int turnsUsed = chatProcessor.recordTurn(threadId, question, answer);

        return ChatReply.of(threadId, answer, turnsUsed, MAX_TURNS_PER_THREAD);
    }
}
