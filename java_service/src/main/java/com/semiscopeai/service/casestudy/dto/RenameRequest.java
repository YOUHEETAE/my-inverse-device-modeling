package com.semiscopeai.service.casestudy.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

// 학습 기록에 사용자가 붙이는 이름. 목록에서 세션을 구분하는 값이라
// 길이를 제한한다 (데스크톱 앱의 _rename_selected_session).
public record RenameRequest(
        @JsonProperty("display_name") @NotBlank @Size(max = 80) String displayName) {
}
