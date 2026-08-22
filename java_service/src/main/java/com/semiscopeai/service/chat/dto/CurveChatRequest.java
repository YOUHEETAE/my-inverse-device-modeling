package com.semiscopeai.service.chat.dto;

import com.semiscopeai.service.explain.dto.CurveConfig;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Size;
import java.util.List;

// 프론트가 보내는 요청. Python으로 그대로 넘기는 게 아니라, 로그인 상태면
// 이력을 서버가 채워 넣는다(ChatService 참고).
//
// threadId가 없으면 새 대화를 시작한다. 응답에 담긴 값을 다음 질문에 실어
// 보내면 같은 대화로 이어진다.
public record CurveChatRequest(
        @NotEmpty @Valid List<CurveConfig> curves,
        @NotBlank @Size(max = 800) String question,
        Long threadId) {
}
