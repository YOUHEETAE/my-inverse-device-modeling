from __future__ import annotations

import json
from pathlib import Path

from backend.learning import (
    FollowupTurn,
    LearningAnalysisContext,
    LearningLLMService,
    TutorAuditScenario,
    audit_followup_history,
    load_topic,
    run_tutor_scenarios,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "learning"


def _context() -> LearningAnalysisContext:
    data = json.loads(
        (FIXTURE_DIR / "sce_channel_length_analysis.json").read_text(
            encoding="utf-8",
        )
    )
    return LearningAnalysisContext.from_dict(data["learning_context"])


def test_configured_tutor_scenarios_pass_all_quality_gates() -> None:
    data = json.loads(
        (FIXTURE_DIR / "tutor_quality_scenarios.json").read_text(
            encoding="utf-8",
        )
    )
    scenarios = tuple(
        TutorAuditScenario.from_dict(item)
        for item in data["scenarios"]
    )
    report = run_tutor_scenarios(
        topic=load_topic(data["topic_id"]),
        context=_context(),
        scenarios=scenarios,
        service=LearningLLMService(),
        learner_profile=data["learner_profile"],
    )
    assert report.passed
    assert all(item.passed for item in report.scenario_results)
    assert report.quality.coverage_text == "8/8"
    assert report.quality.grounded_result_turns == 3
    assert report.quality.claim_feedback_turns == 1
    assert report.quality.adaptive_turns == 8
    assert report.quality.fallback_turns == 0


def test_quality_audit_reports_exact_contract_failures() -> None:
    broken = FollowupTurn(
        question="현재 결과가 맞지?",
        answer="같은 문장입니다. 같은 문장입니다.",
        question_type="current_result",
        evidence_ids=(),
        created_at="2026-07-30T00:00:00+00:00",
        uses_current_result=True,
        learning_move="confirm_experiment",
        claim_assessment="supported",
        explanation_level="foundational",
        adaptation_reasons=(),
        fallback_reason="external_validation_failed",
    )
    report = audit_followup_history((broken,), _context())
    assert not report.passed
    assert set(report.turns[0].failures) >= {
        "answer_cohesion",
        "result_grounding",
        "claim_feedback",
        "claim_evidence",
        "adaptive_metadata",
        "fallback_diagnostic",
    }
    assert "turn_1:result_grounding" in report.gate_failures
