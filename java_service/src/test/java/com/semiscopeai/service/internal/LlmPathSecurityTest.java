package com.semiscopeai.service.internal;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.semiscopeai.service.auth.CustomOAuth2UserService;
import com.semiscopeai.service.common.HealthController;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.security.oauth2.client.autoconfigure.OAuth2ClientAutoConfiguration;
import org.springframework.boot.security.oauth2.client.autoconfigure.servlet.OAuth2ClientWebSecurityAutoConfiguration;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.security.oauth2.client.registration.ClientRegistrationRepository;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

/**
 * 하루 한도는 계정 단위로만 셀 수 있으므로, 세는 경로가 전부 로그인을
 * 요구해야 뜻이 있다. 둘 중 하나만 바뀌면 조용히 구멍이 난다 —
 * DailyQuotaInterceptor는 principal이 없으면 세지 않고 통과시키기 때문에,
 * 인증이 빠진 경로는 한도 없이 열린다.
 *
 * <p>컨트롤러를 하나만 올려도 검증된다. 시큐리티 필터는 DispatcherServlet
 * 앞에서 돌기 때문에, 이 슬라이스에 매핑이 없는 경로도 인증이 필요하면
 * 404가 아니라 401이 나온다.
 */
@WebMvcTest(
        controllers = HealthController.class,
        excludeAutoConfiguration = {
            OAuth2ClientAutoConfiguration.class,
            OAuth2ClientWebSecurityAutoConfiguration.class
        })
@Import(SecurityConfig.class)
@ActiveProfiles("test")
class LlmPathSecurityTest {

    private static final String SESSION = "/case-study/sessions/2fac791a-0000-0000-0000-000000000000";

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private CustomOAuth2UserService customOAuth2UserService;

    @MockitoBean
    private ClientRegistrationRepository clientRegistrationRepository;

    @MockitoBean
    private RateLimiterService rateLimiterService;

    // @WebMvcTest는 @Repository를 빈에서 제외한다. DailyQuotaInterceptor가
    // 생성자로 요구하므로 채워준다 — 여기서 확인하는 건 인증 경계라 실제로
    // 호출되지는 않는다(401이 인터셉터보다 먼저 난다).
    @MockitoBean
    private DailyQuotaRepository dailyQuotaRepository;

    @BeforeEach
    void allowRateLimit() {
        when(rateLimiterService.isAllowed(anyString(), any())).thenReturn(true);
    }

    @Test
    void 하루_한도를_세는_경로는_전부_로그인을_요구한다() throws Exception {
        for (String path : new String[] {
            "/explain/curves",
            "/explain/fields",
            "/chat/curves",
            "/chat/fields",
            SESSION + "/evaluation",
            SESSION + "/followup",
        }) {
            mockMvc.perform(post(path)).andExpect(status().isUnauthorized());
        }
    }

    // 여기까지 막으면 로그인 없이는 아무것도 해볼 수 없는 서비스가 된다.
    // 조건을 바꿔 예측하고 비교하는 것은 외부 비용이 없으므로 열어둔다.
    // 404는 이 슬라이스에 매핑이 없다는 뜻이고, 인증은 통과했다는 뜻이다.
    @Test
    void 로컬_추론과_프롬프트_경로는_로그인_없이_열린다() throws Exception {
        for (String path : new String[] {
            "/explain/curves/prompt",
            "/explain/fields/prompt",
            "/curves/predict",
            "/fields/display",
            "/case-study/topics",
        }) {
            mockMvc.perform(post(path)).andExpect(status().isNotFound());
        }
    }
}
