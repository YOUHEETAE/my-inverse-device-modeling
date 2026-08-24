package com.semiscopeai.service.chat;

import com.semiscopeai.service.chat.dto.ChatAnswer;
import com.semiscopeai.service.chat.dto.ChatReply;
import com.semiscopeai.service.chat.dto.ChatThreadSummary;
import com.semiscopeai.service.chat.dto.ChatThreadView;
import com.semiscopeai.service.chat.dto.CurveChatRequest;
import com.semiscopeai.service.chat.dto.FieldChatRequest;
import jakarta.validation.Valid;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.core.user.OAuth2User;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;
import org.springframework.web.server.ResponseStatusException;

// 다른 컨트롤러들과 달리 순수 프록시가 아니다. 대화 이력도, 소자 설정도
// 요청이 아니라 DB에서 나온다 — ChatService가 본문을 통째로 만들어 주고
// 여기서는 어느 Python 경로로 보낼지만 정한다. 요청의 소자 설정을 그대로
// 넘길 방법이 아예 없어야 스냅샷 고정이 실수로 깨지지 않는다.
@RestController
public class ChatController {

    // 한 대화에서 불러올 메시지 상한. 대화가 아무리 길어져도 응답 크기가
    // 무한정 커지지 않게 한다.
    private static final int MESSAGE_LIMIT = 200;
    private static final int THREAD_LIMIT = 50;

    private final RestClient pythonServiceClient;
    private final ChatService chatService;
    private final ChatRepository chatRepository;

    public ChatController(
            RestClient pythonServiceClient, ChatService chatService, ChatRepository chatRepository) {
        this.pythonServiceClient = pythonServiceClient;
        this.chatService = chatService;
        this.chatRepository = chatRepository;
    }

    @PostMapping("/chat/curves")
    public ChatReply curves(
            @AuthenticationPrincipal OAuth2User principal, @Valid @RequestBody CurveChatRequest request) {

        return chatService.ask(
                userId(principal),
                request.threadId(),
                "curves",
                Map.of("curves", request.curves()),
                request.question(),
                body -> post("/explain/curves/chat", body));
    }

    @PostMapping("/chat/fields")
    public ChatReply fields(
            @AuthenticationPrincipal OAuth2User principal, @Valid @RequestBody FieldChatRequest request) {

        return chatService.ask(
                userId(principal),
                request.threadId(),
                "fields",
                Map.of(
                        "fields", request.fields(),
                        "display", request.display(),
                        "scale_mode", request.scaleMode(),
                        "range_mode", request.rangeMode()),
                request.question(),
                body -> post("/explain/fields/chat", body));
    }

    // 새로고침하거나 다른 기기에서 열었을 때 대화를 복원한다. 저장만 하고
    // 읽을 방법이 없으면 말풍선이 페이지를 벗어나는 순간 사라진다.
    @GetMapping("/chat/threads/{threadId}")
    public ChatThreadView thread(@AuthenticationPrincipal OAuth2User principal, @PathVariable long threadId) {
        return chatRepository
                .findThread(threadId, userId(principal), MESSAGE_LIMIT)
                .map(thread -> thread.withTurnLimit(ChatService.MAX_TURNS_PER_THREAD))
                // 남의 대화는 존재 여부조차 알리지 않는다 — 403이면 "있긴
                // 하다"는 정보가 새어나간다.
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "대화를 찾을 수 없습니다."));
    }

    @GetMapping("/chat/threads")
    public List<ChatThreadSummary> threads(
            @AuthenticationPrincipal OAuth2User principal,
            @RequestParam(required = false) String kind) {
        return chatRepository.listThreads(userId(principal), kind, THREAD_LIMIT);
    }

    private ChatAnswer post(String path, Map<String, Object> body) {
        return pythonServiceClient.post().uri(path).body(body).retrieve().body(ChatAnswer.class);
    }

    // /chat/** 는 SecurityConfig에서 인증을 요구하므로 principal은 항상 있다.
    // userId는 로그인 시점에 세션에 담아둔 우리 DB의 PK다
    // (CustomOAuth2UserService 참고).
    private long userId(OAuth2User principal) {
        return ((Number) principal.getAttribute("userId")).longValue();
    }
}
