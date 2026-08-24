package com.semiscopeai.service.casestudy;

import com.semiscopeai.service.casestudy.dto.FollowupRequest;
import com.semiscopeai.service.casestudy.dto.FollowupReply;
import com.semiscopeai.service.casestudy.dto.NewSessionRequest;
import com.semiscopeai.service.casestudy.dto.RenameRequest;
import com.semiscopeai.service.casestudy.dto.SessionAnswers;
import com.semiscopeai.service.casestudy.dto.SessionSummary;
import jakarta.validation.Valid;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.core.user.OAuth2User;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;
import org.springframework.web.server.ResponseStatusException;

// 케이스 목록과 내용은 누구나 볼 수 있고, 학습 세션은 로그인해야 한다.
// 분석/자유질문과 같은 경계다 — 둘러보는 건 막지 않되, 기록이 남는 일은
// 누구 것인지 알아야 한다 (SecurityConfig 참고).
//
// 세션을 다루는 경로는 전부 같은 모양이다: 꺼내서 Python에 맡기고 돌아온 걸
// 저장한다. 세션의 내용은 Python 소유라 자바는 Map으로만 다룬다 — 필드를
// DTO로 옮겨 적으면 Python이 스키마를 고칠 때마다 같이 깨진다.
@RestController
public class CaseStudyController {

    private final RestClient pythonServiceClient;
    private final LearningRepository learningRepository;
    private final LearningService learningService;

    public CaseStudyController(
            RestClient pythonServiceClient,
            LearningRepository learningRepository,
            LearningService learningService) {
        this.pythonServiceClient = pythonServiceClient;
        this.learningRepository = learningRepository;
        this.learningService = learningService;
    }

    // ---- 케이스 목록 / 내용 (비로그인 가능) ----

    @GetMapping("/case-study/topics")
    public List<Map<String, Object>> topics() {
        return pythonServiceClient
                .get()
                .uri("/case-study/topics")
                .retrieve()
                .body(new ParameterizedTypeReference<List<Map<String, Object>>>() {});
    }

    @GetMapping("/case-study/topics/{topicId}")
    public Map<String, Object> topic(@PathVariable String topicId) {
        return pythonServiceClient
                .get()
                .uri("/case-study/topics/{topicId}", topicId)
                .retrieve()
                .body(map());
    }

    // ---- 내 학습 현황 ----

    // 진도·잠금 여부·다음 추천은 Python의 순수 함수가 계산한다. 자바는 그
    // 재료(내 세션 전부)를 모아 넘기는 일만 한다.
    @GetMapping("/case-study/portfolio")
    public Map<String, Object> portfolio(@AuthenticationPrincipal OAuth2User principal) {
        return post("/case-study/portfolio", Map.of("sessions", learningRepository.findAll(userId(principal))));
    }

    // ---- 학습 기록 (자바만으로 처리) ----

    @GetMapping("/case-study/sessions")
    public List<SessionSummary> sessions(
            @AuthenticationPrincipal OAuth2User principal,
            @RequestParam(name = "topic_id", required = false) String topicId) {
        return learningRepository.summaries(userId(principal), topicId);
    }

    @GetMapping("/case-study/sessions/{sessionId}")
    public Map<String, Object> session(
            @AuthenticationPrincipal OAuth2User principal, @PathVariable UUID sessionId) {
        return learningService.require(sessionId, userId(principal));
    }

    // 이름 바꾸기와 삭제는 저장된 값만 건드리므로 Python을 거치지 않는다.
    @PatchMapping("/case-study/sessions/{sessionId}")
    public void rename(
            @AuthenticationPrincipal OAuth2User principal,
            @PathVariable UUID sessionId,
            @Valid @RequestBody RenameRequest request) {
        if (!learningRepository.rename(sessionId, userId(principal), request.displayName())) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "학습 기록을 찾을 수 없습니다.");
        }
    }

    @DeleteMapping("/case-study/sessions/{sessionId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@AuthenticationPrincipal OAuth2User principal, @PathVariable UUID sessionId) {
        if (!learningRepository.delete(sessionId, userId(principal))) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "학습 기록을 찾을 수 없습니다.");
        }
    }

    // ---- 학습 진행 ----

    @PostMapping("/case-study/sessions")
    public Map<String, Object> create(
            @AuthenticationPrincipal OAuth2User principal, @Valid @RequestBody NewSessionRequest request) {
        Map<String, Object> created = LearningService.sessionOf(post("/case-study/sessions", request));
        return learningService.persist(userId(principal), created);
    }

    @PostMapping("/case-study/sessions/{sessionId}/reset")
    public Map<String, Object> reset(
            @AuthenticationPrincipal OAuth2User principal, @PathVariable UUID sessionId) {
        return step(sessionId, principal, "/case-study/sessions/reset");
    }

    // 실험이나 채점이 실패해 ERROR로 남은 세션을 실패 직전 단계로 되돌린다.
    @PostMapping("/case-study/sessions/{sessionId}/recover")
    public Map<String, Object> recover(
            @AuthenticationPrincipal OAuth2User principal, @PathVariable UUID sessionId) {
        return step(sessionId, principal, "/case-study/sessions/recover");
    }

    @PostMapping("/case-study/sessions/{sessionId}/begin-prediction")
    public Map<String, Object> beginPrediction(
            @AuthenticationPrincipal OAuth2User principal, @PathVariable UUID sessionId) {
        return step(sessionId, principal, "/case-study/sessions/begin-prediction");
    }

    @PostMapping("/case-study/sessions/{sessionId}/predictions")
    public Map<String, Object> predictions(
            @AuthenticationPrincipal OAuth2User principal,
            @PathVariable UUID sessionId,
            @Valid @RequestBody SessionAnswers request) {
        return learningService.advance(sessionId, userId(principal), session -> post(
                "/case-study/sessions/predictions",
                LearningService.body(session, "answers", request.answers())));
    }

    // 모델 추론이 도는 단계라 느리다. 예측 제출과 나뉘어 있어서 여기서
    // 실패해도 학습자의 답변은 이미 저장되어 있고 다시 부르면 된다.
    //
    // 응답에 갱신된 세션과 그릴 곡선이 함께 온다. 곡선은 저장하지 않는다 —
    // 세션에 넣으면 걸음마다 오가는 짐이 되고, 조건만 있으면 언제든 다시
    // 만들 수 있다.
    @PostMapping("/case-study/sessions/{sessionId}/experiment")
    public Map<String, Object> experiment(
            @AuthenticationPrincipal OAuth2User principal, @PathVariable UUID sessionId) {
        return learningService.advanceWithPayload(sessionId, userId(principal), session -> post(
                "/case-study/sessions/experiment", LearningService.body(session)));
    }

    // 저장된 세션을 다시 열었을 때 그래프만 되살린다. 세션은 그대로 둔다 —
    // 데스크톱의 "그래프 다시 생성"과 같다.
    @PostMapping("/case-study/sessions/{sessionId}/regenerate")
    public Map<String, Object> regenerate(
            @AuthenticationPrincipal OAuth2User principal, @PathVariable UUID sessionId) {
        return post(
                "/case-study/sessions/regenerate",
                LearningService.body(learningService.require(sessionId, userId(principal))));
    }

    @PostMapping("/case-study/sessions/{sessionId}/observations")
    public Map<String, Object> observations(
            @AuthenticationPrincipal OAuth2User principal,
            @PathVariable UUID sessionId,
            @Valid @RequestBody SessionAnswers request) {
        return learningService.advance(sessionId, userId(principal), session -> post(
                "/case-study/sessions/observations",
                LearningService.body(session, "answers", request.answers())));
    }

    @PostMapping("/case-study/sessions/{sessionId}/evaluation")
    public Map<String, Object> evaluation(
            @AuthenticationPrincipal OAuth2User principal, @PathVariable UUID sessionId) {
        return step(sessionId, principal, "/case-study/sessions/evaluation");
    }

    // 케이스 안에서 묻는 AI 질문. I-V/Field 자유질문과 달리 이 대화는 학습
    // 세션에 붙어 followup_history로 함께 저장된다.
    @PostMapping("/case-study/sessions/{sessionId}/followup")
    public FollowupReply followup(
            @AuthenticationPrincipal OAuth2User principal,
            @PathVariable UUID sessionId,
            @Valid @RequestBody FollowupRequest request) {
        long userId = userId(principal);
        Map<String, Object> reply = learningService.advanceWithPayload(sessionId, userId, session -> post(
                "/case-study/sessions/followup",
                LearningService.body(session, "question", request.question())));
        return new FollowupReply(
                String.valueOf(reply.get("answer")), String.valueOf(reply.get("source")));
    }

    private Map<String, Object> step(UUID sessionId, OAuth2User principal, String path) {
        return learningService.advance(
                sessionId, userId(principal), session -> post(path, LearningService.body(session)));
    }

    private Map<String, Object> post(String path, Object body) {
        return pythonServiceClient.post().uri(path).body(body).retrieve().body(map());
    }

    private static ParameterizedTypeReference<Map<String, Object>> map() {
        return new ParameterizedTypeReference<>() {};
    }

    // /case-study/sessions/** 는 SecurityConfig에서 인증을 요구한다.
    private long userId(OAuth2User principal) {
        return ((Number) principal.getAttribute("userId")).longValue();
    }
}
