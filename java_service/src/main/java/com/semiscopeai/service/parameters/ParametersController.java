package com.semiscopeai.service.parameters;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;

@RestController
public class ParametersController {

    private final RestClient pythonServiceClient;

    public ParametersController(RestClient pythonServiceClient) {
        this.pythonServiceClient = pythonServiceClient;
    }

    @GetMapping("/parameters")
    public ParametersResponse getParameters() {
        return pythonServiceClient.get().uri("/parameters").retrieve().body(ParametersResponse.class);
    }
}
