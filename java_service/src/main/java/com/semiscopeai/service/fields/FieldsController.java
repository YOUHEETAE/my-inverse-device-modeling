package com.semiscopeai.service.fields;

import com.semiscopeai.service.fields.dto.FieldCompareRequest;
import com.semiscopeai.service.fields.dto.FieldCompareResponse;
import com.semiscopeai.service.fields.dto.FieldDisplayRequest;
import com.semiscopeai.service.fields.dto.FieldDisplayResponse;
import com.semiscopeai.service.fields.dto.FieldRequest;
import com.semiscopeai.service.fields.dto.FieldResponse;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;

@RestController
public class FieldsController {

    private final RestClient pythonServiceClient;

    public FieldsController(RestClient pythonServiceClient) {
        this.pythonServiceClient = pythonServiceClient;
    }

    @PostMapping("/fields/predict")
    public FieldResponse predict(@Valid @RequestBody FieldRequest request) {
        return pythonServiceClient.post().uri("/fields/predict").body(request).retrieve().body(FieldResponse.class);
    }

    @PostMapping("/fields/display")
    public FieldDisplayResponse display(@Valid @RequestBody FieldDisplayRequest request) {
        return pythonServiceClient
                .post()
                .uri("/fields/display")
                .body(request)
                .retrieve()
                .body(FieldDisplayResponse.class);
    }

    @PostMapping("/fields/display/compare")
    public FieldCompareResponse displayCompare(@Valid @RequestBody FieldCompareRequest request) {
        return pythonServiceClient
                .post()
                .uri("/fields/display/compare")
                .body(request)
                .retrieve()
                .body(FieldCompareResponse.class);
    }
}
