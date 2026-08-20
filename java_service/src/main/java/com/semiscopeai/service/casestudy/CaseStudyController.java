package com.semiscopeai.service.casestudy;

import com.semiscopeai.service.casestudy.dto.GradeRequest;
import com.semiscopeai.service.casestudy.dto.GradeResponse;
import com.semiscopeai.service.casestudy.dto.TopicDetail;
import com.semiscopeai.service.casestudy.dto.TopicSummary;
import jakarta.validation.Valid;
import java.util.List;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;

@RestController
public class CaseStudyController {

    private final RestClient pythonServiceClient;

    public CaseStudyController(RestClient pythonServiceClient) {
        this.pythonServiceClient = pythonServiceClient;
    }

    @GetMapping("/case-study/topics")
    public List<TopicSummary> listTopics() {
        return pythonServiceClient
                .get()
                .uri("/case-study/topics")
                .retrieve()
                .body(new ParameterizedTypeReference<List<TopicSummary>>() {});
    }

    @GetMapping("/case-study/topics/{topicId}")
    public TopicDetail getTopic(@PathVariable String topicId) {
        return pythonServiceClient
                .get()
                .uri("/case-study/topics/{topicId}", topicId)
                .retrieve()
                .body(TopicDetail.class);
    }

    @PostMapping("/case-study/topics/{topicId}/grade")
    public GradeResponse grade(@PathVariable String topicId, @Valid @RequestBody GradeRequest request) {
        return pythonServiceClient
                .post()
                .uri("/case-study/topics/{topicId}/grade", topicId)
                .body(request)
                .retrieve()
                .body(GradeResponse.class);
    }
}
