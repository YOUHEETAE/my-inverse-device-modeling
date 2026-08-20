package com.semiscopeai.service.theory;

import com.semiscopeai.service.theory.dto.LongChannelOptionsResponse;
import com.semiscopeai.service.theory.dto.LongChannelResultRequest;
import com.semiscopeai.service.theory.dto.LongChannelResultResponse;
import com.semiscopeai.service.theory.dto.MOSCapOptionsResponse;
import com.semiscopeai.service.theory.dto.MOSCapResultRequest;
import com.semiscopeai.service.theory.dto.MOSCapResultResponse;
import com.semiscopeai.service.theory.dto.PNOptionsResponse;
import com.semiscopeai.service.theory.dto.PNResultRequest;
import com.semiscopeai.service.theory.dto.PNResultResponse;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;

// long-channel-mosfet은 프론트엔드가 더 이상 안 부르지만(MOSCapacitorTool로
// 교체됨) Python과의 동일성 유지를 위해 그대로 이관함.
@RestController
public class TheoryController {

    private final RestClient pythonServiceClient;

    public TheoryController(RestClient pythonServiceClient) {
        this.pythonServiceClient = pythonServiceClient;
    }

    @GetMapping("/theory/pn-junction/options")
    public PNOptionsResponse pnJunctionOptions() {
        return pythonServiceClient.get().uri("/theory/pn-junction/options").retrieve().body(PNOptionsResponse.class);
    }

    @PostMapping("/theory/pn-junction/result")
    public PNResultResponse pnJunctionResult(@Valid @RequestBody PNResultRequest request) {
        return pythonServiceClient
                .post()
                .uri("/theory/pn-junction/result")
                .body(request)
                .retrieve()
                .body(PNResultResponse.class);
    }

    @GetMapping("/theory/long-channel-mosfet/options")
    public LongChannelOptionsResponse longChannelMosfetOptions() {
        return pythonServiceClient
                .get()
                .uri("/theory/long-channel-mosfet/options")
                .retrieve()
                .body(LongChannelOptionsResponse.class);
    }

    @PostMapping("/theory/long-channel-mosfet/result")
    public LongChannelResultResponse longChannelMosfetResult(@Valid @RequestBody LongChannelResultRequest request) {
        return pythonServiceClient
                .post()
                .uri("/theory/long-channel-mosfet/result")
                .body(request)
                .retrieve()
                .body(LongChannelResultResponse.class);
    }

    @GetMapping("/theory/mos-capacitor/options")
    public MOSCapOptionsResponse mosCapacitorOptions() {
        return pythonServiceClient
                .get()
                .uri("/theory/mos-capacitor/options")
                .retrieve()
                .body(MOSCapOptionsResponse.class);
    }

    @PostMapping("/theory/mos-capacitor/result")
    public MOSCapResultResponse mosCapacitorResult(@Valid @RequestBody MOSCapResultRequest request) {
        return pythonServiceClient
                .post()
                .uri("/theory/mos-capacitor/result")
                .body(request)
                .retrieve()
                .body(MOSCapResultResponse.class);
    }
}
