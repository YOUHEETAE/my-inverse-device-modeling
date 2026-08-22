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
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

// DB는 ChatRepositoryTest가 검증한다. 여기서는 "이력을 꺼내 Python에 넘기고
// 결과를 저장한다"는 흐름의 순서와 분기만 본다.
@ExtendWith(MockitoExtension.class)
class ChatServiceTest {

    private static final long USER_ID = 7L;

    @Mock
    private ChatRepository chatRepository;

    private ChatAnswer answer(String text, String source) {
        return new ChatAnswer(text, source, "explain_metric", List.of(), null, false, Map.of("intent", "explain_metric"));
    }

    @Test
    void thread_id가_없으면_새_대화를_만든다() {
        when(chatRepository.createThread(USER_ID, "curves", Map.of("L", "500"))).thenReturn(42L);
        when(chatRepository.recentTurns(42L, 6)).thenReturn(List.of());
        when(chatRepository.lastIntentCheckpoint(42L)).thenReturn(Map.of());

        ChatService service = new ChatService(chatRepository);
        ChatReply reply = service.ask(
                USER_ID, null, "curves", Map.of("L", "500"), "Ion은?", (h, c) -> answer("6.28", "external_llm"));

        // 프론트는 이 값을 받아 다음 질문에 실어 보낸다.
        assertThat(reply.threadId()).isEqualTo(42L);
    }

    // 요청 DTO에는 history 필드가 없다. 맥락은 전적으로 여기서 채워진다.
    @Test
    void 저장된_이력과_checkpoint를_Python에_넘긴다() {
        when(chatRepository.threadBelongsTo(42L, USER_ID)).thenReturn(true);
        when(chatRepository.recentTurns(42L, 6)).thenReturn(List.of(ChatTurn.of("이전 질문", "이전 답변", "external_llm")));
        when(chatRepository.lastIntentCheckpoint(42L)).thenReturn(Map.of("intent", "clarify"));

        AtomicReference<List<ChatTurn>> sentHistory = new AtomicReference<>();
        AtomicReference<Map<String, Object>> sentCheckpoint = new AtomicReference<>();

        new ChatService(chatRepository)
                .ask(USER_ID, 42L, "curves", Map.of(), "그건 좋은 값인가요?", (history, checkpoint) -> {
                    sentHistory.set(history);
                    sentCheckpoint.set(checkpoint);
                    return answer("네", "external_llm");
                });

        assertThat(sentHistory.get()).extracting(ChatTurn::question).containsExactly("이전 질문");
        assertThat(sentCheckpoint.get()).containsEntry("intent", "clarify");
    }

    @Test
    void 답변은_같은_대화에_저장된다() {
        when(chatRepository.createThread(anyLong(), any(), any())).thenReturn(42L);
        when(chatRepository.recentTurns(anyLong(), anyInt())).thenReturn(List.of());
        when(chatRepository.lastIntentCheckpoint(anyLong())).thenReturn(Map.of());

        new ChatService(chatRepository)
                .ask(USER_ID, null, "curves", Map.of(), "Ion은?", (h, c) -> answer("6.28", "external_llm"));

        verify(chatRepository)
                .appendMessage(
                        eq(42L),
                        eq("Ion은?"),
                        eq("6.28"),
                        eq("external_llm"),
                        eq("explain_metric"),
                        eq(Map.of("intent", "explain_metric")));
    }

    // 화면에 이미 보여준 내용이라 새로고침 시 사라지면 더 이상하다. 다음
    // 질문의 맥락에서 빼는 건 조회 단계(recentTurns)가 맡는다.
    @Test
    void 실패한_답변도_저장한다() {
        when(chatRepository.createThread(anyLong(), any(), any())).thenReturn(42L);
        when(chatRepository.recentTurns(anyLong(), anyInt())).thenReturn(List.of());
        when(chatRepository.lastIntentCheckpoint(anyLong())).thenReturn(Map.of());

        new ChatService(chatRepository)
                .ask(USER_ID, null, "curves", Map.of(), "Ion은?", (h, c) -> new ChatAnswer("생성 실패", "external_error", null, List.of(), null, false, null));

        verify(chatRepository).appendMessage(eq(42L), eq("Ion은?"), eq("생성 실패"), eq("external_error"), eq(null), eq(null));
    }

    // 남의 대화에 질문을 이어붙이지 못해야 한다. 403이 아니라 404인 이유는
    // 그 threadId가 존재한다는 사실조차 알리지 않기 위해서다.
    @Test
    void 남의_대화에는_이어붙일_수_없다() {
        when(chatRepository.threadBelongsTo(42L, USER_ID)).thenReturn(false);
        ChatService service = new ChatService(chatRepository);

        assertThatThrownBy(() -> service.ask(USER_ID, 42L, "curves", Map.of(), "질문", (h, c) -> answer("답", "external_llm")))
                .isInstanceOf(ResponseStatusException.class)
                .extracting(e -> ((ResponseStatusException) e).getStatusCode())
                .isEqualTo(HttpStatus.NOT_FOUND);

        verify(chatRepository, never()).appendMessage(anyLong(), any(), any(), any(), any(), any());
    }
}
