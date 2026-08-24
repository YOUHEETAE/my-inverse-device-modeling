package com.semiscopeai.service.chat;

import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.oauth2Login;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.semiscopeai.service.auth.CustomOAuth2UserService;
import com.semiscopeai.service.chat.dto.ChatAnswer;
import com.semiscopeai.service.chat.dto.ChatReply;
import com.semiscopeai.service.chat.dto.ChatThreadSummary;
import com.semiscopeai.service.internal.RateLimiterService;
import com.semiscopeai.service.internal.SecurityConfig;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.security.oauth2.client.autoconfigure.OAuth2ClientAutoConfiguration;
import org.springframework.boot.security.oauth2.client.autoconfigure.servlet.OAuth2ClientWebSecurityAutoConfiguration;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.security.oauth2.client.registration.ClientRegistrationRepository;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.RequestPostProcessor;
import org.springframework.web.client.RestClient;
import org.springframework.web.server.ResponseStatusException;

// 저장 로직은 ChatServiceTest/ChatRepositoryTest가 본다. 여기서는 HTTP 경계 —
// 인증, 요청 검증, 응답 형식만 확인한다.
@WebMvcTest(
        controllers = ChatController.class,
        excludeAutoConfiguration = {
            OAuth2ClientAutoConfiguration.class,
            OAuth2ClientWebSecurityAutoConfiguration.class
        })
@Import(SecurityConfig.class)
@ActiveProfiles("test")
class ChatControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private ChatService chatService;

    @MockitoBean
    private ChatRepository chatRepository;

    @MockitoBean
    private RestClient pythonServiceClient;

    @MockitoBean
    private CustomOAuth2UserService customOAuth2UserService;

    @MockitoBean
    private ClientRegistrationRepository clientRegistrationRepository;

    @MockitoBean
    private RateLimiterService rateLimiterService;

    // 로그인 시점에 CustomOAuth2UserService가 세션에 담아두는 값
    private RequestPostProcessor loggedIn() {
        return oauth2Login().attributes(attrs -> attrs.put("userId", 42L));
    }

    private static final String CURVE_BODY =
            """
            {"curves":[{"label":"Curve 1","L":"500","T":"15","B":"1e16","SD":"1e20","LDD":"1e18"}],
             "question":"Ion이 얼마인가요?"}
            """;

    @BeforeEach
    void allowRateLimit() {
        Mockito.when(rateLimiterService.isAllowed(Mockito.anyString())).thenReturn(true);
    }

    // 비로그인은 구글 로그인 페이지로 리다이렉트되면 안 된다. 프론트가 fetch로
    // 부르기 때문에 302를 받으면 CORS 오류로만 보이고 이유를 알 수 없다.
    @Test
    void 비로그인_질문은_401이다() throws Exception {
        mockMvc.perform(post("/chat/curves").contentType(MediaType.APPLICATION_JSON).content(CURVE_BODY))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void 비로그인_조회도_401이다() throws Exception {
        mockMvc.perform(get("/chat/threads")).andExpect(status().isUnauthorized());
    }

    // 응답의 thread_id를 프론트가 그대로 다음 요청에 실어야 대화가 이어진다.
    @Test
    void 응답의_thread_id는_snake_case로_나간다() throws Exception {
        Mockito.when(chatService.ask(
                        Mockito.anyLong(),
                        Mockito.any(),
                        Mockito.anyString(),
                        Mockito.any(),
                        Mockito.anyString(),
                        Mockito.any()))
                .thenReturn(ChatReply.of(
                        42L,
                        new ChatAnswer("6.28 mA/um", "external_llm", "explain_metric", List.of(), null, false, Map.of()),
                        3,
                        20));

        mockMvc.perform(post("/chat/curves")
                        .with(loggedIn())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(CURVE_BODY))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.thread_id").value(42))
                .andExpect(jsonPath("$.threadId").doesNotExist())
                // 프론트는 이 둘로 상한이 가까워졌음을 미리 안내한다.
                .andExpect(jsonPath("$.turns_used").value(3))
                .andExpect(jsonPath("$.turn_limit").value(20));
    }

    // 프론트가 이 응답을 일반 오류와 구분해서 "새 대화 시작"을 띄워야 한다.
    @Test
    void 상한을_채운_대화는_409와_안내문을_준다() throws Exception {
        Mockito.when(chatService.ask(
                        Mockito.anyLong(),
                        Mockito.any(),
                        Mockito.anyString(),
                        Mockito.any(),
                        Mockito.anyString(),
                        Mockito.any()))
                .thenThrow(new ResponseStatusException(HttpStatus.CONFLICT, "이 대화는 질문 20개를 채웠습니다. 새 대화를 시작해 주세요."));

        mockMvc.perform(post("/chat/curves")
                        .with(loggedIn())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(CURVE_BODY))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.detail").value("이 대화는 질문 20개를 채웠습니다. 새 대화를 시작해 주세요."));
    }

    // 근거가 비교에서 만들어지는 설계라 소자 1개짜리 Field 질문은 Python이
    // 거부한다. LLM 호출 비용을 쓰기 전에 여기서 막는다.
    @Test
    void 소자가_하나뿐인_Field_질문은_400이다() throws Exception {
        String body =
                """
                {"fields":[{"label":"Device 1","L":"500","T":"15","B":"1e16","SD":"1e20","LDD":"1e18",
                            "vg":"1.0","vd":"1.0"}],
                 "display":"Potential","scale_mode":"linear","range_mode":"shared",
                 "question":"차이가 뭔가요?"}
                """;

        mockMvc.perform(post("/chat/fields")
                        .with(loggedIn())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest());

        Mockito.verifyNoInteractions(chatService);
    }

    @Test
    void 빈_질문은_400이다() throws Exception {
        String body =
                """
                {"curves":[{"label":"Curve 1","L":"500","T":"15","B":"1e16","SD":"1e20","LDD":"1e18"}],
                 "question":"  "}
                """;

        mockMvc.perform(post("/chat/curves")
                        .with(loggedIn())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest());
    }

    // 남의 threadId를 찍어보면 403이 아니라 404여야 한다 — 403은 "있긴 하다"는
    // 사실을 흘린다.
    @Test
    void 없는_대화_조회는_404다() throws Exception {
        Mockito.when(chatRepository.findThread(Mockito.anyLong(), Mockito.anyLong(), Mockito.anyInt()))
                .thenReturn(Optional.empty());

        mockMvc.perform(get("/chat/threads/999999").with(loggedIn())).andExpect(status().isNotFound());
    }

    @Test
    void 목록_응답도_snake_case로_나간다() throws Exception {
        Mockito.when(chatRepository.listThreads(Mockito.anyLong(), Mockito.anyInt()))
                .thenReturn(List.of(new ChatThreadSummary(42L, "curves", Instant.parse("2026-08-17T00:00:00Z"), "Ion은?", 3)));

        mockMvc.perform(get("/chat/threads").with(loggedIn()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].last_question").value("Ion은?"))
                .andExpect(jsonPath("$[0].message_count").value(3));
    }
}
