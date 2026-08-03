from __future__ import annotations

import inspect

from backend.learning import LearningSession, LearningStep, load_topic, load_topics
from frontend.app import IntegratedModelApp
from frontend.visualization.case_study import CaseStudyPanel
from frontend.visualization.case_study.panel import (
    FOLLOWUP_EXAMPLES,
    STEP_LABELS,
    STEP_ORDER,
    format_case_comparison,
    format_error_guidance,
    format_followup_metadata,
)
from backend.learning import FollowupResponse


def test_case_study_panel_covers_complete_learning_flow() -> None:
    expected = {
        LearningStep.INTRODUCTION,
        LearningStep.BASELINE_SETUP,
        LearningStep.PREDICTION_QUESTION,
        LearningStep.PREDICTION_SUBMITTED,
        LearningStep.SIMULATION_RUNNING,
        LearningStep.RESULT_READY,
        LearningStep.OBSERVATION_QUESTION,
        LearningStep.OBSERVATION_SUBMITTED,
        LearningStep.FEEDBACK_READY,
        LearningStep.NEXT_EXPERIMENT,
        LearningStep.SESSION_COMPLETE,
    }
    assert set(STEP_ORDER) == expected
    assert expected <= set(STEP_LABELS)


def test_case_study_uses_requested_channel_length_pair() -> None:
    topic = load_topic("sce_channel_length")
    assert topic.baseline_conditions["L"] == 700.0
    assert topic.comparison_conditions["L"] == 300.0
    assert [
        name
        for name in topic.baseline_conditions
        if topic.baseline_conditions[name] != topic.comparison_conditions[name]
    ] == ["L"]
    assert all(
        topic.baseline_conditions[name] == topic.comparison_conditions[name]
        for name in ("T", "B", "SD", "LDD")
    )
    caption, baseline, comparison = format_case_comparison(topic)
    assert "Channel length" in caption
    assert baseline == "700 nm"
    assert comparison == "300 nm"


def test_case_study_panel_is_catalog_driven_for_future_topics() -> None:
    source = inspect.getsource(CaseStudyPanel.__init__)
    switch_source = inspect.getsource(CaseStudyPanel._switch_topic)
    assert "load_topics()" in source
    assert "topic_choice_box" in source
    assert "self.topics[topic_id]" in switch_source
    assert "_restore_or_create_session()" in switch_source
    assert {
        "sce_channel_length",
        "oxide_gate_control",
    } <= set(load_topics())


def test_changed_case_conditions_do_not_resume_legacy_session() -> None:
    topic = load_topic("oxide_gate_control")
    panel = object.__new__(CaseStudyPanel)
    panel.topic = topic
    current = LearningSession.create(topic)
    legacy = LearningSession.create(topic)
    legacy.comparison_conditions["T"] = 15.0
    assert panel._session_matches_current_topic(current)
    assert not panel._session_matches_current_topic(legacy)


def test_app_exposes_test_safe_learning_options() -> None:
    parameters = inspect.signature(IntegratedModelApp.__init__).parameters
    assert parameters["enable_learning_persistence"].default is True
    assert parameters["auto_generate"].default is True
    assert hasattr(CaseStudyPanel, "set_provider")
    assert hasattr(CaseStudyPanel, "_build_chat")
    assert hasattr(CaseStudyPanel, "_build_feedback")
    assert hasattr(CaseStudyPanel, "_resume_selected_session")
    assert hasattr(CaseStudyPanel, "_reset_current_session")
    assert hasattr(CaseStudyPanel, "_delete_selected_session")
    assert hasattr(CaseStudyPanel, "_rename_selected_session")
    assert hasattr(CaseStudyPanel, "_clone_selected_session")
    assert hasattr(CaseStudyPanel, "_session_matches_current_topic")
    assert hasattr(CaseStudyPanel, "_show_learning_portfolio")
    assert hasattr(CaseStudyPanel, "_learning_portfolio")
    app_source = inspect.getsource(IntegratedModelApp.__init__)
    assert not hasattr(IntegratedModelApp, "_provider_changed")
    assert "provider_box" not in app_source
    assert "provider=interactive_provider" in app_source
    chat_source = inspect.getsource(CaseStudyPanel._build_chat)
    assert "history.see(tk.END)" in chat_source
    assert "widget.yview_moveto(1.0)" in chat_source
    assert "최근 실패 재시도" in chat_source
    assert "recommended_retry_after_seconds" in chat_source


def test_chat_metadata_distinguishes_external_local_and_fallback() -> None:
    external = FollowupResponse(
        "current_result",
        "answer",
        ("ev_dibl",),
        True,
        source="external_llm",
        relevance_to_case="direct",
        uses_current_result=True,
        theory_concepts=("dibl",),
    )
    headline, details = format_followup_metadata(external)
    assert "AI 튜터" in headline
    assert "현재 결과 사용" in headline
    assert "ev_dibl" not in details
    assert "DIBL" in details and "dibl" in details

    fallback = FollowupResponse(
        "hypothetical",
        "answer",
        needs_new_experiment=True,
        relevance_to_case="domain_adjacent",
        fallback_reason="external_timeout",
    )
    headline, details = format_followup_metadata(fallback)
    assert "로컬 보조 해설" in headline
    assert "추가 실험 필요" in headline
    assert "AI 응답 시간 초과" in details


def test_chat_metadata_hides_internal_provider_diagnostics() -> None:
    fallback = FollowupResponse(
        "case_theory",
        "answer",
        source="external_error",
        fallback_reason="external_http_429",
        pipeline_diagnostics=(
            {
                "stage": "answer_generation",
                "http_status": 429,
                "error_type": "rate_limit_error",
                "message": "Rate limit reached for openai/gpt-oss-120b.",
                "request_bytes": 32_768,
                "model": "openai/gpt-oss-120b",
                "recommended_retry_after_seconds": 3,
                "headers": {
                    "retry-after": "20",
                    "x-ratelimit-remaining-tokens": "0",
                },
                "attempts": [
                    {
                        "attempt": 1,
                        "http_status": 429,
                        "message": "Token rate limit reached.",
                    },
                    {
                        "attempt": 2,
                        "http_status": 413,
                        "message": "Request body is too large.",
                    },
                ],
            },
        ),
    )

    headline, details = format_followup_metadata(fallback)
    assert "AI 연결 오류" in headline
    assert "로컬 보조 해설" not in headline
    assert "오류: AI 요청 한도 초과" in details
    assert "다시 시도: 3초 후" in details
    for internal in (
        "HTTP 429",
        "Rate limit reached",
        "32.0 KB",
        "retry-after",
        "API 시도",
        "openai/gpt-oss-120b",
    ):
        assert internal not in details


def test_chat_metadata_keeps_successful_usage_internal() -> None:
    response = FollowupResponse(
        "case_theory",
        "answer",
        source="external_llm",
        pipeline_diagnostics=(
            {
                "category": "provider_success",
                "stage": "intent_interpretation",
                "request_bytes": 1_024,
                "duration_ms": 100.0,
                "usage": {
                    "prompt_tokens": 200,
                    "completion_tokens": 40,
                    "total_tokens": 240,
                },
            },
            {
                "category": "provider_success",
                "stage": "answer_generation",
                "request_bytes": 4_096,
                "duration_ms": 500.0,
                "usage": {
                    "prompt_tokens": 900,
                    "completion_tokens": 300,
                    "total_tokens": 1200,
                },
            },
        ),
    )
    _headline, details = format_followup_metadata(response)
    assert "입력 1,100" not in details
    assert "출력 340" not in details
    assert "tokens" not in details
    assert "API 2회" not in details
    assert "실제 오류" not in details


def test_completion_keeps_open_ended_questions_and_error_recovery_clear() -> None:
    assert len(FOLLOWUP_EXAMPLES) >= 4
    assert any("PN 접합" in question for _label, question in FOLLOWUP_EXAMPLES)
    assert any("Body doping" in question for _label, question in FOLLOWUP_EXAMPLES)
    assert hasattr(CaseStudyPanel, "_build_complete")
    guidance = format_error_guidance(
        "learning_experiment_failed:field_inference",
        LearningStep.SIMULATION_RUNNING,
    )
    assert "실험을 다시 실행" in guidance
    assert "모델 실행" in guidance
    assert "기존 세션 기록은 삭제되지 않습니다" in guidance


def test_case_result_and_observation_columns_use_fixed_non_draggable_layout() -> None:
    result_source = inspect.getsource(CaseStudyPanel._build_results)
    observation_source = inspect.getsource(CaseStudyPanel._build_observation)
    assert "Panedwindow" not in result_source
    assert "Panedwindow" not in observation_source
    assert "parameters.pack_propagate(False)" in result_source
    assert "questions.pack_propagate(False)" in observation_source


def test_compact_parameter_table_reserves_the_change_column_width() -> None:
    source = inspect.getsource(CaseStudyPanel._build_parameter_table)
    assert '("direction", "변화", 62)' in source
    assert "stretch=False" in source


def test_observation_and_feedback_use_fixed_wider_explanation_columns() -> None:
    result_source = inspect.getsource(CaseStudyPanel._build_results)
    observation_source = inspect.getsource(CaseStudyPanel._build_observation)
    feedback_source = inspect.getsource(CaseStudyPanel._build_feedback)
    assert "width=350" in result_source
    assert "width=500" in observation_source
    assert "width=620" in feedback_source
    assert "wraplength=540" in inspect.getsource(
        CaseStudyPanel._feedback_cards
    )
    assert "추천 행동 진행" not in feedback_source
    assert "내 답변에서 다시 확인할 Curve 위치" in inspect.getsource(
        CaseStudyPanel._feedback_cards
    )
    assert "내 답변에서 다시 확인할 Field 위치" in inspect.getsource(
        CaseStudyPanel._feedback_cards
    )
    assert "scrollregion" in feedback_source
    assert "fit_feedback_width" in feedback_source
    assert "content_width - 48" in feedback_source
    assert "yscrollincrement=12" in feedback_source
    assert "_bind_feedback_mousewheel(canvas)" in feedback_source
    wheel_source = inspect.getsource(CaseStudyPanel._bind_feedback_mousewheel)
    assert '"<MouseWheel>"' in wheel_source
    assert '"<Button-4>"' in wheel_source
    assert '"<Button-5>"' in wheel_source
    assert 'canvas.yview_scroll(units, "units")' in wheel_source


def test_case_study_opens_on_a_cover_with_resume_and_new_start_actions() -> None:
    init_source = inspect.getsource(CaseStudyPanel.__init__)
    render_source = inspect.getsource(CaseStudyPanel.render)
    cover_source = inspect.getsource(CaseStudyPanel._build_cover)
    assert "self.show_cover = True" in init_source
    assert "if self.show_cover" in render_source
    assert "Case Study Learning Lab" in cover_source
    assert "이어서 학습" in cover_source
    assert "완료 결과 보기" in cover_source
    assert "새로 시작" in cover_source
    assert "추천 학습 이어서" in cover_source


def test_cover_hides_case_selector_until_a_case_is_opened() -> None:
    chrome_source = inspect.getsource(CaseStudyPanel._set_cover_chrome)
    assert "self.case_selector_label.pack_forget()" in chrome_source
    assert "self.topic_choice_box.pack_forget()" in chrome_source
    assert "self.topic_title_label.pack_forget()" in chrome_source
    assert "self.topic_choice_box.pack(side=tk.LEFT" in chrome_source


def test_cover_navigation_preserves_sessions_and_enters_selected_case() -> None:
    open_source = inspect.getsource(CaseStudyPanel._open_case_session)
    start_source = inspect.getsource(CaseStudyPanel._start_new_case)
    show_source = inspect.getsource(CaseStudyPanel._show_cover)
    assert "self.repository.load(session_id)" in open_source
    assert "self.show_cover = False" in open_source
    assert "LearningSession.create(self.topic)" in start_source
    assert "self._save()" in start_source
    assert "self.show_cover = True" in show_source
