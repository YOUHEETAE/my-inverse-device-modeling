package com.semiscopeai.service.internal;

import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.semiscopeai.service.common.HealthController;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

// 버킷 로직은 RateLimiterServiceTest에서 검증했고, 여기서는 인터셉터가 실제
// MVC 요청 흐름에 제대로 배선됐는지만 확인함.
//
// @WebMvcTest는 @Service를 빈에서 제외해서, RateLimiterService는
// @MockitoBean으로 직접 등록해야 함.
@WebMvcTest(HealthController.class)
class RateLimitInterceptorTest {

    @Autowired
    private MockMvc mockMvc;

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
