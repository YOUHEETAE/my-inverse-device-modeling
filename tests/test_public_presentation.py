from backend.public_presentation import (
    public_ai_failure_message,
    public_failure_label,
    public_source_label,
    sanitize_persisted_diagnostic,
)


def test_public_rate_limit_message_keeps_action_and_hides_provider_details():
    diagnostic = {
        "http_status": 429,
        "message": (
            "Rate limit reached for organization org_secret and model "
            "openai/gpt-oss-120b."
        ),
        "model": "openai/gpt-oss-120b",
        "request_bytes": 16_384,
        "headers": {
            "retry-after": "20",
            "x-request-id": "req_secret",
        },
        "provider_code": "rate_limit_exceeded",
    }

    text = public_ai_failure_message(
        feature="Case Study",
        failure="external_http_429",
        diagnostic=diagnostic,
        retry_after_seconds=21,
        checkpoint_preserved=True,
        state_preserved=True,
    )

    assert "AI 요청 한도 초과" in text
    assert "21초 후" in text
    assert "질문 해석 결과는 보존" in text
    assert "세션 기록은 보존" in text
    for internal in (
        "org_secret",
        "openai/gpt-oss-120b",
        "req_secret",
        "rate_limit_exceeded",
        "16_384",
        "retry-after",
        "HTTP 429",
    ):
        assert internal not in text


def test_public_auth_message_tells_learner_to_contact_operator():
    text = public_ai_failure_message(
        feature="I-V",
        failure="external_http_401",
        diagnostic={
            "http_status": 401,
            "message": "Invalid API Key",
            "provider_code": "invalid_api_key",
        },
    )

    assert "AI 서비스 인증 실패" in text
    assert "서비스 관리자에게 문의" in text
    assert "Invalid API Key" not in text
    assert "invalid_api_key" not in text


def test_public_labels_do_not_disclose_provider_vendor():
    assert public_source_label("external_llm") == "AI 튜터"
    assert public_source_label("external_error") == "AI 연결 오류"
    assert (
        public_source_label("local", has_fallback=True)
        == "로컬 보조 해설"
    )
    assert (
        public_failure_label(
            "external_request_failed",
            {"http_status": 413},
        )
        == "AI 요청 정보 과다"
    )


def test_session_diagnostic_keeps_retry_state_but_drops_provider_payload():
    clean = sanitize_persisted_diagnostic({
        "category": "provider_http",
        "stage": "answer_generation",
        "http_status": "429",
        "recommended_retry_after_seconds": "21",
        "intent_checkpoint_available": 1,
        "message": "organization org_secret exceeded its token limit",
        "model": "openai/gpt-oss-120b",
        "request_bytes": 20_000,
        "headers": {"x-request-id": "req_secret"},
        "provider_code": "rate_limit_exceeded",
        "quality_failure": {"provider_response": "private learner text"},
    })

    assert clean == {
        "category": "provider_http",
        "stage": "answer_generation",
        "http_status": 429,
        "recommended_retry_after_seconds": 21,
        "intent_checkpoint_available": True,
    }
