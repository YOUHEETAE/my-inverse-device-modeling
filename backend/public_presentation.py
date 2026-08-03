from __future__ import annotations

from typing import Any


_SOURCE_LABELS = {
    "external_llm": "AI 튜터",
    "external_error": "AI 연결 오류",
    "local_router": "비교 기준 확인",
    "local": "로컬 튜터",
}

_FAILURE_LABELS = {
    "provider_unavailable": "AI 기능 미연결",
    "external_response_unavailable": "AI 응답 사용 불가",
    "external_timeout": "AI 응답 시간 초과",
    "external_network_error": "AI 서비스 연결 실패",
    "external_provider_error": "AI 서비스 오류",
    "external_request_failed": "AI 요청 실패",
    "external_validation_failed": "AI 응답 확인 실패",
    "external_http_400": "AI 요청 처리 실패",
    "external_http_401": "AI 서비스 인증 실패",
    "external_http_403": "AI 서비스 접근 권한 없음",
    "external_http_404": "AI 서비스 설정 오류",
    "external_http_413": "AI 요청 정보 과다",
    "external_http_429": "AI 요청 한도 초과",
    "external_http_500": "AI 서비스 일시 오류",
    "external_http_502": "AI 서비스 일시 오류",
    "external_http_503": "AI 서비스 일시 오류",
    "external_http_504": "AI 서비스 응답 시간 초과",
}

_PERSISTED_DIAGNOSTIC_FIELDS = {
    "category",
    "stage",
    "http_status",
    "recommended_retry_after_seconds",
    "intent_checkpoint_available",
}


def public_source_label(
    source: str | None,
    *,
    has_fallback: bool = False,
) -> str:
    """Return a learner-facing label without vendor implementation details."""

    if has_fallback and source != "external_error":
        return "로컬 보조 해설"
    return _SOURCE_LABELS.get(str(source or ""), "로컬 튜터")


def public_failure_label(
    failure: str | None,
    diagnostic: dict[str, Any] | None = None,
) -> str:
    """Map provider/internal identifiers to a stable learner-facing label."""

    value = diagnostic or {}
    status = value.get("http_status")
    if status is not None:
        mapped = _FAILURE_LABELS.get(f"external_http_{status}")
        if mapped:
            return mapped
    return _FAILURE_LABELS.get(str(failure or ""), "AI 답변 생성 실패")


def public_ai_failure_message(
    *,
    feature: str,
    failure: str | None,
    diagnostic: dict[str, Any] | None = None,
    retry_after_seconds: int | None = None,
    checkpoint_preserved: bool = False,
    state_preserved: bool = False,
    automatic: bool = False,
) -> str:
    """Build a public error while raw provider diagnostics remain internal."""

    value = diagnostic or {}
    status = value.get("http_status")
    title = (
        f"{feature} 자동 해설을 생성하지 못했습니다."
        if automatic
        else f"{feature} AI 답변을 생성하지 못했습니다."
    )

    if status == 429 or failure == "external_http_429":
        reason = "요청이 일시적으로 많아 AI 사용 한도에 도달했습니다."
        action = (
            f"{retry_after_seconds}초 후 같은 요청을 다시 시도해 주세요."
            if retry_after_seconds is not None
            else "잠시 후 같은 요청을 다시 시도해 주세요."
        )
    elif status == 413 or failure == "external_http_413":
        reason = "현재 질문과 분석 정보가 한 번에 처리할 수 있는 크기를 넘었습니다."
        action = "질문의 범위를 줄여 다시 시도하거나 관리자에게 문의해 주세요."
    elif status in {401, 403} or failure in {
        "provider_unavailable",
        "external_http_401",
        "external_http_403",
    }:
        reason = "AI 서비스 연결 설정을 확인할 수 없습니다."
        action = "서비스 관리자에게 문의해 주세요."
    elif failure == "external_validation_failed":
        reason = "생성된 답변을 안전하게 표시할 수 없어 중단했습니다."
        action = "같은 요청을 다시 시도해 주세요."
    elif failure == "external_timeout" or status == 504:
        reason = "AI 서비스가 제한 시간 안에 응답하지 않았습니다."
        action = (
            f"{retry_after_seconds}초 후 다시 시도해 주세요."
            if retry_after_seconds is not None
            else "잠시 후 다시 시도해 주세요."
        )
    elif failure == "external_network_error":
        reason = "AI 서비스에 연결하지 못했습니다."
        action = "네트워크 상태를 확인한 뒤 다시 시도해 주세요."
    elif status in {500, 502, 503}:
        reason = "AI 서비스에 일시적인 오류가 발생했습니다."
        action = "잠시 후 다시 시도해 주세요."
    elif failure == "local_processing_error":
        reason = "분석 결과를 해설로 구성하는 과정에서 오류가 발생했습니다."
        action = "같은 조건에서 다시 분석해 주세요. 반복되면 관리자에게 문의해 주세요."
    else:
        reason = "AI 답변 생성 과정에서 오류가 발생했습니다."
        action = "잠시 후 다시 시도해 주세요. 반복되면 관리자에게 문의해 주세요."

    lines = [
        title,
        f"상태: {public_failure_label(failure, value)}",
        f"원인: {reason}",
        f"다시 시도: {action}",
    ]
    if checkpoint_preserved:
        lines.append("완료된 질문 해석 결과는 보존됩니다.")
    if state_preserved:
        lines.append("현재 질문과 세션 기록은 보존됩니다.")
    return "\n".join(lines)


def sanitize_persisted_diagnostic(value: Any) -> dict[str, Any]:
    """Keep only fields required to restore retry and public error behavior."""

    if not isinstance(value, dict):
        return {}
    clean = {
        key: value[key]
        for key in _PERSISTED_DIAGNOSTIC_FIELDS
        if value.get(key) is not None
    }
    if "http_status" in clean:
        try:
            clean["http_status"] = int(clean["http_status"])
        except (TypeError, ValueError):
            clean.pop("http_status", None)
    if "recommended_retry_after_seconds" in clean:
        try:
            clean["recommended_retry_after_seconds"] = max(
                0,
                int(clean["recommended_retry_after_seconds"]),
            )
        except (TypeError, ValueError):
            clean.pop("recommended_retry_after_seconds", None)
    if "intent_checkpoint_available" in clean:
        clean["intent_checkpoint_available"] = bool(
            clean["intent_checkpoint_available"]
        )
    return clean


def sanitize_persisted_diagnostics(values: Any) -> list[dict[str, Any]]:
    """Remove provider payloads, identifiers, usage, and raw failures from sessions."""

    if not isinstance(values, (list, tuple)):
        return []
    return [
        clean
        for item in values
        if (clean := sanitize_persisted_diagnostic(item))
    ]
