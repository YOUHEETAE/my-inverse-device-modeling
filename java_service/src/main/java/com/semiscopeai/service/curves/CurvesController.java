package com.semiscopeai.service.curves;

import com.semiscopeai.service.curves.dto.CurveRequest;
import com.semiscopeai.service.curves.dto.CurveResponse;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;

@RestController
public class CurvesController {

    private final RestClient pythonServiceClient;

    public CurvesController(RestClient pythonServiceClient) {
        this.pythonServiceClient = pythonServiceClient;
    }

    @PostMapping("/curves/predict")
    public CurveResponse predict(@Valid @RequestBody CurveRequest request) {
        return pythonServiceClient.post().uri("/curves/predict").body(request).retrieve().body(CurveResponse.class);
    }
}
