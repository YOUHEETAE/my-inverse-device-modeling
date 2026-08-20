package com.semiscopeai.service.internal;

import java.net.http.HttpClient;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.http.converter.json.JacksonJsonHttpMessageConverter;
import org.springframework.web.client.RestClient;
import tools.jackson.databind.json.JsonMapper;

@Configuration
public class PythonServiceConfig {

    @Bean
    public RestClient pythonServiceClient(
            @Value("${python.service.base-url}") String baseUrl, JsonMapper jsonMapper) {
        // RestClient.builder()가 알아서 만드는 기본 컨버터는 application.properties의
        // SNAKE_CASE 설정을 모르는 새 매퍼를 써서 조용히 camelCase로 나가버림 —
        // 부트가 설정해둔 JsonMapper 빈을 명시적으로 넘겨야 함.
        JacksonJsonHttpMessageConverter jacksonConverter = new JacksonJsonHttpMessageConverter(jsonMapper);

        // JDK HttpClient 기본값인 HTTP/2 h2c 업그레이드 시도가 uvicorn(h2c
        // 미지원)과 만나면 커넥션이 깨져서 응답이 비거나 깨진 채로 옴.
        HttpClient httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .build();
        return RestClient.builder()
                .baseUrl(baseUrl)
                .requestFactory(new JdkClientHttpRequestFactory(httpClient))
                .configureMessageConverters(converters -> converters.withJsonConverter(jacksonConverter))
                .defaultStatusHandler(new PythonServiceErrorHandler(jsonMapper))
                .build();
    }
}
