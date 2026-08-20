package com.semiscopeai.service.explain;

import com.semiscopeai.service.explain.dto.ExplainCurveRequest;
import com.semiscopeai.service.explain.dto.ExplainFieldRequest;
import com.semiscopeai.service.explain.dto.ExplainResponse;
import com.semiscopeai.service.explain.dto.PromptResponse;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;

// Python의 slowapi 제한은 제거함 — 이 서비스가 Python을 대신 호출하면
// Python 입장에선 모든 요청이 한 IP로 보여서 방문자별 제한이 무의미해짐.
// 대신 RateLimitInterceptor가 실제 방문자 IP로 제한함.
@RestController
public class ExplainController {

    private final RestClient pythonServiceClient;

    public ExplainController(RestClient pythonServiceClient) {
        this.pythonServiceClient = pythonServiceClient;
    }

    @PostMapping("/explain/curves")
    public ExplainResponse explainCurves(@Valid @RequestBody ExplainCurveRequest request) {
        return pythonServiceClient
                .post()
                .uri("/explain/curves")
                .body(request)
                .retrieve()
                .body(ExplainResponse.class);
    }

    @PostMapping("/explain/curves/prompt")
    public PromptResponse explainCurvesPrompt(@Valid @RequestBody ExplainCurveRequest request) {
        return pythonServiceClient
                .post()
                .uri("/explain/curves/prompt")
                .body(request)
                .retrieve()
                .body(PromptResponse.class);
    }

    @PostMapping("/explain/fields")
    public ExplainResponse explainFields(@Valid @RequestBody ExplainFieldRequest request) {
        return pythonServiceClient
                .post()
                .uri("/explain/fields")
                .body(request)
                .retrieve()
                .body(ExplainResponse.class);
    }

    @PostMapping("/explain/fields/prompt")
    public PromptResponse explainFieldsPrompt(@Valid @RequestBody ExplainFieldRequest request) {
        return pythonServiceClient
                .post()
                .uri("/explain/fields/prompt")
                .body(request)
                .retrieve()
                .body(PromptResponse.class);
    }
}
