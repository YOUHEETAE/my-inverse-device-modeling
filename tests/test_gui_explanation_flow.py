"""Regression checks for the simplified explanation provider controls."""

import inspect

from backend.explanation.errors import ExplanationPipelineError
from backend.explanation.providers.external import ProviderHTTPError
from frontend.app import (
    IntegratedModelApp,
    _load_runtime_models_async,
    _start_interactive_app,
)
from frontend.visualization.explanation_panel import ExplanationPanelMixin


def test_gui_fixes_automatic_explanation_to_groq_without_selector() -> None:
    source = inspect.getsource(IntegratedModelApp.__init__)
    assert "self.explanation_llm_available" in source
    assert "ExplanationService(service_provider)" in source
    assert "provider_box" not in source
    assert "explanation_provider_var" not in source


def test_interactive_startup_shows_window_before_async_model_loading() -> None:
    startup_source = inspect.getsource(_start_interactive_app)
    loader_source = inspect.getsource(_load_runtime_models_async)
    assert startup_source.index("_create_tk_window()") < startup_source.index(
        "_load_runtime_models_async("
    )
    assert "window.mainloop()" in startup_source
    assert "ttk.Progressbar" in startup_source
    assert "threading.Thread(" in loader_source
    assert 'daemon=True' in loader_source


def test_automatic_explanation_formats_public_failure_only() -> None:
    error = ProviderHTTPError(
        429,
        message="Rate limit reached. Please try again in 2s",
        error_type="tokens",
        provider_code="rate_limit_exceeded",
        request_bytes=8_192,
        model="test-model",
        headers={"retry-after": "2"},
    )
    text = ExplanationPanelMixin._format_explanation_provider_error(error)
    assert "AI 요청 한도 초과" in text
    assert "3초 후" in text
    assert "HTTP 429" not in text
    assert "Rate limit reached" not in text
    assert "요청 크기" not in text
    validation_text = (
        ExplanationPanelMixin._format_explanation_provider_error(
            ValueError("language_polish_changed_numbers")
        )
    )
    assert "생성된 답변을 안전하게 표시할 수 없어" in validation_text
    assert "language_polish_changed_numbers" not in validation_text


def test_automatic_explanation_distinguishes_local_and_llm_validation() -> None:
    local = ExplanationPipelineError(
        "deterministic_draft_validation",
        "mock_draft_missing_tradeoff",
        retryable=False,
    )
    local_text = ExplanationPanelMixin._format_explanation_provider_error(local)
    assert "분석 결과를 해설로 구성하는 과정" in local_text
    assert "mock_draft_missing_tradeoff" not in local_text
    assert "API 호출" not in local_text

    llm = ExplanationPipelineError(
        "llm_response_validation",
        "language_polish_changed_numbers",
        retryable=True,
        diagnostics=(
            {
                "category": "provider_success",
                "model": "test-model",
                "request_bytes": 1_024,
                "duration_ms": 100,
                "usage": {
                    "prompt_tokens": 200,
                    "completion_tokens": 50,
                    "total_tokens": 250,
                },
            },
            {
                "category": "provider_success",
                "model": "test-model",
                "request_bytes": 1_024,
                "duration_ms": 100,
                "usage": {
                    "prompt_tokens": 200,
                    "completion_tokens": 50,
                    "total_tokens": 250,
                },
                "retry_reason": "language_polish_changed_section_structure",
            },
        ),
        first_validation_code="language_polish_changed_section_structure",
    )
    llm_text = ExplanationPanelMixin._format_explanation_provider_error(llm)
    assert "AI 응답 확인 실패" in llm_text
    assert "API 2회" not in llm_text
    assert "language_polish_changed" not in llm_text


def test_automatic_explanation_does_not_recommend_waiting_for_auth_error() -> None:
    error = ProviderHTTPError(
        401,
        message="Invalid API Key",
        error_type="invalid_request_error",
        provider_code="invalid_api_key",
        request_bytes=512,
        model="test-model",
    )
    text = ExplanationPanelMixin._format_explanation_provider_error(error)
    assert "서비스 관리자에게 문의" in text
    assert "API key" not in text
    assert "Invalid API Key" not in text


def test_iv_chat_freezes_snapshot_without_switching_the_plot_view() -> None:
    send_source = inspect.getsource(ExplanationPanelMixin._send_iv_chat)
    status_source = inspect.getsource(
        ExplanationPanelMixin._update_iv_chat_view_status
    )
    assert "self.iv_chat_snapshot is None" in send_source
    assert "selection_signature=signature" in send_source
    assert "self.notebook.select" not in send_source
    assert "화면 변경됨" in status_source
    assert hasattr(ExplanationPanelMixin, "_reset_iv_chat")
    assert hasattr(ExplanationPanelMixin, "_retry_iv_chat")
    assert "최근 실패 재시도" in inspect.getsource(
        ExplanationPanelMixin._build_iv_chat_panel
    )


def test_field_chat_freezes_snapshot_and_tracks_field_view_changes() -> None:
    send_source = inspect.getsource(ExplanationPanelMixin._send_field_chat)
    status_source = inspect.getsource(
        ExplanationPanelMixin._update_field_chat_view_status
    )
    build_source = inspect.getsource(
        ExplanationPanelMixin._build_explanation_panel
    )
    assert "self.field_chat_snapshot is None" in send_source
    assert "selection_signature=signature" in send_source
    assert "iv_results=iv_results" in send_source
    assert "iv_configs=iv_configs" in send_source
    assert "self.notebook.select" not in send_source
    assert "화면 변경됨" in status_source
    assert "I-V 근거 연동" in status_source
    assert 'kind in {"curve", "field"}' in build_source
    assert hasattr(ExplanationPanelMixin, "_reset_field_chat")
    assert hasattr(ExplanationPanelMixin, "_retry_field_chat")
    assert "최근 실패 재시도" in inspect.getsource(
        ExplanationPanelMixin._build_field_chat_panel
    )


def test_chat_history_persists_comparison_focus_metadata() -> None:
    iv_source = inspect.getsource(
        ExplanationPanelMixin._show_iv_chat_response
    )
    field_source = inspect.getsource(
        ExplanationPanelMixin._show_field_chat_response
    )
    for source in (iv_source, field_source):
        assert '"comparison_focus"' in source
        assert "public_source_label" in source
