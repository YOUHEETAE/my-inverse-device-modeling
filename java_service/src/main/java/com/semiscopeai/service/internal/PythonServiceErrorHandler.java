package com.semiscopeai.service.internal;

import java.io.IOException;
import java.net.URI;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.client.ClientHttpResponse;
import org.springframework.web.client.ResponseErrorHandler;
import org.springframework.web.server.ResponseStatusException;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

// Python 에러를 그대로 다시 던져서, 이 API를 쓰는 쪽이 Python을 직접
// 호출했을 때와 같은 에러를 보게 함. Pydantic 자동 검증 422는 detail이
// 문자열이 아니라 리스트라서 아래에서 폴백 처리함.
public class PythonServiceErrorHandler implements ResponseErrorHandler {

    private final ObjectMapper objectMapper;

    public PythonServiceErrorHandler(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    @Override
    public boolean hasError(ClientHttpResponse response) throws IOException {
        return response.getStatusCode().isError();
    }

    @Override
    public void handleError(URI url, HttpMethod method, ClientHttpResponse response) throws IOException {
        HttpStatusCode status = response.getStatusCode();
        String message = extractDetail(response);
        throw new ResponseStatusException(status, message);
    }

    private String extractDetail(ClientHttpResponse response) {
        try {
            JsonNode body = objectMapper.readTree(response.getBody());
            JsonNode detail = body.get("detail");
            if (detail != null && detail.isString()) {
                return detail.asString();
            }
            return detail != null ? detail.toString() : body.toString();
        } catch (IOException e) {
            return "Python service returned an error with an unreadable body";
        }
    }
}
