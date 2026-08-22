package com.semiscopeai.service.internal;

import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.semiscopeai.service.auth.CustomOAuth2UserService;
import com.semiscopeai.service.common.HealthController;
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

// 버킷 로직은 RateLimiterServiceTest에서 검증했고, 여기서는 인터셉터가 실제
// MVC 요청 흐름에 제대로 배선됐는지만 확인함.
//
// @WebMvcTest는 @Service를 빈에서 제외해서, RateLimiterService는
// @MockitoBean으로 직접 등록해야 함.
// OAuth2 자동설정은 이 슬라이스가 제공하지 않는 HttpSecurity 빈을 요구해서
// 컨텍스트 로딩이 실패한다. 여기서 확인하려는 건 인터셉터 배선이지 로그인이
// 아니므로 제외한다 (실제 앱에서는 정상 동작하며, 통합 검증은 따로 한다).
@WebMvcTest(
        controllers = HealthController.class,
        excludeAutoConfiguration = {
            OAuth2ClientAutoConfiguration.class,
            OAuth2ClientWebSecurityAutoConfiguration.class
        })
@Import(SecurityConfig.class)
@ActiveProfiles("test")
class RateLimitInterceptorTest {

    @Autowired
    private MockMvc mockMvc;

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

    @Test
    void 허용되면_컨트롤러까지_정상적으로_도달한다() throws Exception {
        when(rateLimiterService.isAllowed(anyString())).thenReturn(true);

        mockMvc.perform(get("/health")).andExpect(status().isOk());
    }

    @Test
    void 제한에_걸리면_컨트롤러_대신_429와_detail_메시지가_반환된다() throws Exception {
        when(rateLimiterService.isAllowed(anyString())).thenReturn(false);

        mockMvc.perform(get("/health"))
                .andExpect(status().isTooManyRequests())
                .andExpect(jsonPath("$.detail").value("Rate limit exceeded"));
    }

    // CORS 프리플라이트는 브라우저가 자동으로 보내는 사전 확인이라 사용자 행동이
    // 아님 — 이걸 카운트하면 요청 1건이 토큰 2개를 먹어서 정상 사용도 429가 남.
    @Test
    void CORS_프리플라이트는_토큰을_소비하지_않는다() throws Exception {
        mockMvc.perform(options("/health")
                        .header("Origin", "http://localhost:5174")
                        .header("Access-Control-Request-Method", "GET"))
                .andExpect(status().isOk());

        verify(rateLimiterService, never()).isAllowed(anyString());
    }
}
