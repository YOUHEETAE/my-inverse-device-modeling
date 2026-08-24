package com.semiscopeai.service.chat;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.semiscopeai.service.chat.dto.ChatAnswer;
import com.semiscopeai.service.chat.dto.ChatReply;
import com.semiscopeai.service.chat.dto.ChatTurn;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.web.client.ResourceAccessException;

// DB는 ChatRepositoryTest가, 소유자·상한 검사는 ChatProcessorTest가 본다.
// 여기서는 "맥락을 꺼내 Python에 넘기고 결과를 저장한다"는 순서만 본다.
@ExtendWith(MockitoExtension.class)
class ChatServiceTest {

    private static final long USER_ID = 7L;

    @Mock
    private ChatProcessor chatProcessor;

    private ChatAnswer answer(String text, String source) {
        return new ChatAnswer(
                text, source, "explain_metric", List.of(), null, false, Map.of("intent", "explain_metric"));
    }

    @Test
    void thread_id가_없으면_답변을_받은_뒤_새_대화를_만든다() {
        when(chatProcessor.openThread(USER_ID, "curves", Map.of("curves", List.of("L=500")))).thenReturn(42L);
        when(chatProcessor.recordTurn(anyLong(), any(), any())).thenReturn(1);

        ChatReply reply = new ChatService(chatProcessor)
                .ask(
                        USER_ID, null, "curves", Map.of("curves", List.of("L=500")), "Ion은?",
                        body -> answer("6.28", "external_llm"));

        // 프론트는 이 값을 받아 다음 질문에 실어 보낸다.
        assertThat(reply.threadId()).isEqualTo(42L);
        assertThat(reply.turnsUsed()).isEqualTo(1);
    }

    // Python 호출이 통째로 실패했을 때 질문 한 줄 없는 빈 대화가 남으면
    // 안 된다. 그래서 대화 생성이 답변 뒤에 온다.
    @Test
    void Python_호출이_실패하면_빈_대화를_만들지_않는다() {
        ChatService service = new ChatService(chatProcessor);

        assertThatThrownBy(() -> service.ask(
                        USER_ID, null, "curves", Map.of(), "Ion은?",
                        body -> {
                            throw new ResourceAccessException("connect timed out");
                        }))
                .isInstanceOf(ResourceAccessException.class);

        verify(chatProcessor, never()).openThread(anyLong(), any(), any());
        verify(chatProcessor, never()).recordTurn(anyLong(), any(), any());
    }

    // 요청 DTO에는 history 필드가 없다. 맥락은 전적으로 여기서 채워진다.
    @Test
    @SuppressWarnings("unchecked")
    void 저장된_이력과_checkpoint를_Python에_넘긴다() {
        when(chatProcessor.loadContext(eq(42L), eq(USER_ID), anyInt(), anyInt()))
                .thenReturn(new ChatProcessor.Context(
                        List.of(ChatTurn.of("이전 질문", "이전 답변", "external_llm")),
                        Map.of("intent", "clarify"),
                        Map.of("curves", List.of("L=500"))));

        AtomicReference<Map<String, Object>> sentBody = new AtomicReference<>();
        new ChatService(chatProcessor)
                .ask(USER_ID, 42L, "curves", Map.of(), "그건 좋은 값인가요?", body -> {
                    sentBody.set(body);
                    return answer("네", "external_llm");
                });

        assertThat(sentBody.get()).containsEntry("question", "그건 좋은 값인가요?");
        assertThat((List<ChatTurn>) sentBody.get().get("history"))
                .extracting(ChatTurn::question)
                .containsExactly("이전 질문");
        assertThat((Map<String, Object>) sentBody.get().get("intent_checkpoint"))
                .containsEntry("intent", "clarify");
    }

    // 첫 질문이 소자 설정을 얼린다 — 데스크톱 앱과 같은 규칙
    // (frontend/visualization/explanation_panel.py의 iv_chat_snapshot).
    //
    // 요청에 실려온 설정을 쓰면, 사용자가 파라미터를 바꾼 순간 말풍선 위쪽은
    // 옛 소자 얘기인데 새 답변은 다른 소자 얘기가 된다. 오류도 안 나서
    // 알아챌 수가 없다.
    @Test
    void 후속_턴은_요청이_아니라_얼린_설정을_Python에_보낸다() {
        when(chatProcessor.loadContext(eq(42L), eq(USER_ID), anyInt(), anyInt()))
                .thenReturn(new ChatProcessor.Context(List.of(), Map.of(), Map.of("curves", List.of("L=500"))));

        AtomicReference<Map<String, Object>> sentBody = new AtomicReference<>();
        // 화면에서는 이미 L=250으로 바꾼 뒤 이어서 묻는 상황
        new ChatService(chatProcessor)
                .ask(USER_ID, 42L, "curves", Map.of("curves", List.of("L=250")), "그럼 이건?", body -> {
                    sentBody.set(body);
                    return answer("답", "external_llm");
                });

        assertThat(sentBody.get()).containsEntry("curves", List.of("L=500"));
    }

    @Test
    void 첫_턴은_요청의_설정을_그대로_얼린다() {
        AtomicReference<Map<String, Object>> sentBody = new AtomicReference<>();

        new ChatService(chatProcessor)
                .ask(USER_ID, null, "curves", Map.of("curves", List.of("L=500")), "Ion은?", body -> {
                    sentBody.set(body);
                    return answer("답", "external_llm");
                });

        assertThat(sentBody.get()).containsEntry("curves", List.of("L=500"));
        // 새 대화라 읽어올 맥락이 없다.
        verify(chatProcessor, never()).loadContext(anyLong(), anyLong(), anyInt(), anyInt());
    }

    @Test
    void 답변은_같은_대화에_저장된다() {
        when(chatProcessor.openThread(anyLong(), any(), any())).thenReturn(42L);

        new ChatService(chatProcessor)
                .ask(USER_ID, null, "curves", Map.of(), "Ion은?", body -> answer("6.28", "external_llm"));

        verify(chatProcessor).recordTurn(eq(42L), eq("Ion은?"), any(ChatAnswer.class));
    }

    // 화면에 이미 보여준 내용이라 새로고침 시 사라지면 더 이상하다. 다음
    // 질문의 맥락에서 빼는 건 조회 단계(recentTurns)가 맡는다.
    @Test
    void 실패한_답변도_저장한다() {
        when(chatProcessor.openThread(anyLong(), any(), any())).thenReturn(42L);
        ChatAnswer failed = new ChatAnswer("생성 실패", "external_error", null, List.of(), null, false, null);

        new ChatService(chatProcessor).ask(USER_ID, null, "curves", Map.of(), "Ion은?", body -> failed);

        verify(chatProcessor).recordTurn(42L, "Ion은?", failed);
    }
}
