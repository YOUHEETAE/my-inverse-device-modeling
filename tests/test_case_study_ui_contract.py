from __future__ import annotations

import inspect

from backend.learning import LearningStep, load_topic
from frontend.app import IntegratedModelApp
from frontend.visualization.case_study import CaseStudyPanel
from frontend.visualization.case_study.panel import (
    FOLLOWUP_EXAMPLES,
    STEP_LABELS,
    STEP_ORDER,
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
    provider_change_source = inspect.getsource(IntegratedModelApp._provider_changed)
    assert "case_study_panel.set_provider" not in provider_change_source


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
    assert "Groq LLM" in headline
    assert "현재 결과 사용" in headline
    assert "ev_dibl" in details and "dibl" in details

    fallback = FollowupResponse(
        "hypothetical",
        "answer",
        needs_new_experiment=True,
        relevance_to_case="domain_adjacent",
        fallback_reason="external_timeout",
    )
    headline, details = format_followup_metadata(fallback)
    assert "로컬 fallback" in headline
    assert "추가 실험 필요" in headline
    assert "Groq 시간 초과" in details


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
