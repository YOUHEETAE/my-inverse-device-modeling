package com.semiscopeai.service.auth;

import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.oauth2Login;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.semiscopeai.service.internal.RateLimiterService;
import com.semiscopeai.service.internal.SecurityConfig;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.security.oauth2.client.autoconfigure.OAuth2ClientAutoConfiguration;
import org.springframework.boot.security.oauth2.client.autoconfigure.servlet.OAuth2ClientWebSecurityAutoConfiguration;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.security.oauth2.client.registration.ClientRegistrationRepository;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

// OAuth2 자동설정은 이 슬라이스가 제공하지 않는 HttpSecurity 빈을 요구해서
// 컨텍스트 로딩이 실패한다 (RateLimitInterceptorTest와 같은 이유).
@WebMvcTest(
        controllers = AuthController.class,
        excludeAutoConfiguration = {
            OAuth2ClientAutoConfiguration.class,
            OAuth2ClientWebSecurityAutoConfiguration.class
        })
@Import(SecurityConfig.class)
@ActiveProfiles("test")
class AuthControllerTest {

    @Autowired
    private MockMvc mockMvc;

    // 전역 인터셉터가 이 슬라이스에도 붙기 때문에 필요하다. 제한 로직 자체는
    // RateLimiterServiceTest에서 검증하므로 여기서는 항상 통과시킨다.
    // SecurityConfig가 이 빈을 생성자로 요구한다. 없으면 SecurityConfig가
    // 만들어지지 않아 스프링 기본 보안(전부 401)이 적용된다.
    @MockitoBean
    private CustomOAuth2UserService customOAuth2UserService;

    // SecurityConfig의 .oauth2Login()이 요구한다. 위에서 OAuth2 자동설정을
    // 제외했기 때문에 직접 채워줘야 한다 — 테스트에서 실제 구글 인증을
    // 하지는 않으므로 목으로 충분하다.
    @MockitoBean
    private ClientRegistrationRepository clientRegistrationRepository;

    @MockitoBean
    private RateLimiterService rateLimiterService;

    // 모든 경로가 permitAll이라 비로그인 요청도 컨트롤러까지 도달한다.
    // 이때 401이 아니라 200을 주는 것이 의도된 동작 — 프론트가 매 페이지
    // 진입마다 호출하는데 비로그인은 오류가 아니기 때문.
    @Test
    void 비로그인이면_200과_authenticated_false를_반환한다() throws Exception {
        Mockito.when(rateLimiterService.isAllowed(Mockito.anyString(), Mockito.any())).thenReturn(true);

        mockMvc.perform(get("/auth/me"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.authenticated").value(false))
                .andExpect(jsonPath("$.user_id").doesNotExist());
    }

    @Test
    void 로그인_상태면_세션에_담긴_사용자_정보를_반환한다() throws Exception {
        Mockito.when(rateLimiterService.isAllowed(Mockito.anyString(), Mockito.any())).thenReturn(true);

        mockMvc.perform(get("/auth/me")
                        .with(oauth2Login().attributes(attrs -> {
                            // CustomOAuth2UserService가 로그인 시점에 담아두는 값들
                            attrs.put("userId", 42L);
                            attrs.put("name", "홍길동");
                            attrs.put("email", "a@example.com");
                        })))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.authenticated").value(true))
                .andExpect(jsonPath("$.user_id").value(42))
                .andExpect(jsonPath("$.name").value("홍길동"))
                .andExpect(jsonPath("$.email").value("a@example.com"));
    }

    // 응답 키가 snake_case여야 한다 — 프론트가 그 형식을 기대하고,
    // 나머지 API도 전부 그렇게 나간다(application.properties의 SNAKE_CASE).
    @Test
    void 응답_필드는_snake_case로_나간다() throws Exception {
        Mockito.when(rateLimiterService.isAllowed(Mockito.anyString(), Mockito.any())).thenReturn(true);

        mockMvc.perform(get("/auth/me")
                        .with(oauth2Login().attributes(attrs -> {
                            attrs.put("userId", 7L);
                            attrs.put("name", "홍길동");
                            attrs.put("email", "a@example.com");
                        })))
                .andExpect(jsonPath("$.user_id").exists())
                .andExpect(jsonPath("$.userId").doesNotExist());
    }
}
