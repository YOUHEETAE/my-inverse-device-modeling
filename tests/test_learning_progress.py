from __future__ import annotations

from backend.learning import (
    LearningSession,
    LearningStep,
    build_learning_portfolio,
    load_topics,
)


def _session(topic_id: str, step: LearningStep) -> LearningSession:
    topic = load_topics()[topic_id]
    session = LearningSession.create(topic)
    session.current_step = step
    return session


def test_portfolio_respects_curriculum_and_recommends_next_case() -> None:
    topics = load_topics()
    empty = build_learning_portfolio(topics, [])
    assert [item.topic_id for item in empty.cases] == [
        "sce_channel_length",
        "oxide_gate_control",
    ]
    assert [item.status for item in empty.cases] == [
        "not_started",
        "locked",
    ]
    assert empty.next_topic_id == "sce_channel_length"
    assert empty.recommendation_kind == "start"

    sce = _session("sce_channel_length", LearningStep.SESSION_COMPLETE)
    sce.completed_concepts = list(
        topics["sce_channel_length"].expected_concepts
    )
    after_sce = build_learning_portfolio(topics, [sce])
    assert [item.status for item in after_sce.cases] == [
        "completed",
        "not_started",
    ]
    assert after_sce.completed_case_count == 1
    assert after_sce.next_topic_id == "oxide_gate_control"


def test_portfolio_prefers_resume_and_tracks_concept_progress() -> None:
    topics = load_topics()
    sce = _session("sce_channel_length", LearningStep.SESSION_COMPLETE)
    oxide = _session("oxide_gate_control", LearningStep.RESULT_READY)
    oxide.completed_concepts = ["thinner_oxide_strengthens_gate_control"]
    portfolio = build_learning_portfolio(topics, [sce, oxide])
    item = next(
        case for case in portfolio.cases
        if case.topic_id == "oxide_gate_control"
    )
    assert item.status == "in_progress"
    assert item.completed_concepts == (
        "thinner_oxide_strengthens_gate_control",
    )
    assert portfolio.next_topic_id == "oxide_gate_control"
    assert portfolio.recommendation_kind == "resume"


def test_portfolio_excludes_sessions_from_old_case_conditions() -> None:
    topics = load_topics()
    legacy = _session("oxide_gate_control", LearningStep.SESSION_COMPLETE)
    legacy.comparison_conditions["T"] = 15.0
    portfolio = build_learning_portfolio(topics, [legacy])
    oxide = next(
        case for case in portfolio.cases
        if case.topic_id == "oxide_gate_control"
    )
    assert oxide.session_count == 0
    assert oxide.status == "locked"
    assert portfolio.archived_incompatible_session_count == 1


def test_portfolio_reports_all_cases_completed() -> None:
    sessions = [
        _session("sce_channel_length", LearningStep.SESSION_COMPLETE),
        _session("oxide_gate_control", LearningStep.SESSION_COMPLETE),
    ]
    portfolio = build_learning_portfolio(load_topics(), sessions)
    assert portfolio.completed_case_count == portfolio.total_case_count == 2
    assert portfolio.recommendation_kind == "review"
    assert portfolio.next_topic_id == "sce_channel_length"
