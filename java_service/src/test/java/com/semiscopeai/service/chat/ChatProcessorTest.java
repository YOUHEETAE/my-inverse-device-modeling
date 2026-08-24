package com.semiscopeai.service.chat;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.semiscopeai.service.chat.dto.ChatTurn;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

// 이어가는 대화에 들어가기 전의 관문 — 소유자 확인과 턴 상한.
@ExtendWith(MockitoExtension.class)
class ChatProcessorTest {

    private static final long USER_ID = 7L;
    private static final int MAX_TURNS = 20;

    @Mock
    private ChatRepository chatRepository;

    // 남의 대화에 질문을 이어붙이지 못해야 한다. 403이 아니라 404인 이유는
    // 그 threadId가 존재한다는 사실조차 알리지 않기 위해서다.
    @Test
    void 남의_대화에는_이어붙일_수_없다() {
        when(chatRepository.threadBelongsTo(42L, USER_ID)).thenReturn(false);
        ChatProcessor processor = new ChatProcessor(chatRepository);

        assertThatThrownBy(() -> processor.loadContext(42L, USER_ID, 6, MAX_TURNS))
                .isInstanceOf(ResponseStatusException.class)
                .extracting(e -> ((ResponseStatusException) e).getStatusCode())
                .isEqualTo(HttpStatus.NOT_FOUND);

        // 이력을 읽어보지도 않는다.
        verify(chatRepository, never()).recentTurns(anyLong(), anyInt());
    }

    // 상한에 닿으면 새 대화를 열게 한다. LLM은 어차피 최근 2턴만 보는데
    // 말풍선만 계속 쌓이면 사용자는 AI가 다 기억한다고 믿게 된다.
    @Test
    void 상한을_채운_대화는_409로_막는다() {
        when(chatRepository.threadBelongsTo(42L, USER_ID)).thenReturn(true);
        when(chatRepository.turnCount(42L)).thenReturn(MAX_TURNS);
        ChatProcessor processor = new ChatProcessor(chatRepository);

        assertThatThrownBy(() -> processor.loadContext(42L, USER_ID, 6, MAX_TURNS))
                .isInstanceOf(ResponseStatusException.class)
                // 400이 아니라 409 — 요청은 멀쩡하고 대화 상태가 문제다.
                // 프론트가 이 코드로 "새 대화 시작"을 띄운다.
                .extracting(e -> ((ResponseStatusException) e).getStatusCode())
                .isEqualTo(HttpStatus.CONFLICT);
    }

    @Test
    void 상한_직전까지는_맥락을_돌려준다() {
        when(chatRepository.threadBelongsTo(42L, USER_ID)).thenReturn(true);
        when(chatRepository.turnCount(42L)).thenReturn(MAX_TURNS - 1);
        when(chatRepository.recentTurns(42L, 6))
                .thenReturn(List.of(ChatTurn.of("이전 질문", "이전 답변", "external_llm")));
        when(chatRepository.lastIntentCheckpoint(42L)).thenReturn(Map.of("intent", "clarify"));
        when(chatRepository.deviceConfig(42L)).thenReturn(Map.of("curves", List.of("L=500")));

        ChatProcessor.Context context = new ChatProcessor(chatRepository).loadContext(42L, USER_ID, 6, MAX_TURNS);

        assertThat(context.history()).extracting(ChatTurn::question).containsExactly("이전 질문");
        assertThat(context.checkpoint()).containsEntry("intent", "clarify");
        assertThat(context.deviceConfig()).containsEntry("curves", List.of("L=500"));
    }

    @Test
    void 첫_턴_맥락은_비어_있고_요청_설정을_쓴다() {
        ChatProcessor.Context context = ChatProcessor.Context.firstTurn(Map.of("curves", List.of("L=500")));

        assertThat(context.history()).isEmpty();
        assertThat(context.checkpoint()).isEmpty();
        assertThat(context.deviceConfig()).containsEntry("curves", List.of("L=500"));
    }
}
