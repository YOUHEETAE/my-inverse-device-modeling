from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from backend.answer_quality import (
    audit_answer_quality,
    build_validation_failure_record,
    validate_answer_quality,
)


FIXTURE = Path(__file__).parent / "fixtures" / "answer_quality_scenarios.json"


def _scenarios():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["scenarios"]


def _audit(item):
    return audit_answer_quality(
        domain=item["domain"],
        question=item["question"],
        answer=item["reference_answer"],
        route=item["route"],
        uses_current_result=item["uses_current_result"],
        needs_new_experiment=item["needs_new_experiment"],
        evidence_ids=(
            ("fixture_result",) if item["uses_current_result"] else ()
        ),
        requested_terms=item["requested_terms"],
        suggested_followup="다음에는 어떤 조건을 확인해 볼까요?",
    )


def test_quality_corpus_has_36_balanced_unique_scenarios() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    scenarios = data["scenarios"]
    assert data["scenario_count"] == len(scenarios) == 36
    assert len({item["id"] for item in scenarios}) == 36
    assert Counter(item["domain"] for item in scenarios) == {
        "case": 12,
        "iv": 12,
        "field": 12,
    }
    assert all(item["question"].strip() for item in scenarios)
    assert all(item["reference_answer"].strip() for item in scenarios)


def test_all_reference_answers_pass_hard_quality_gates() -> None:
    reports = {item["id"]: _audit(item) for item in _scenarios()}
    assert all(report.passed for report in reports.values())
    assert all(not report.hard_failures for report in reports.values())
    assert min(report.score for report in reports.values()) >= 80


def test_quality_contract_rejects_high_confidence_failures() -> None:
    common = {
        "domain": "case",
        "question": "현재 결과에서 Vth가 왜 감소했나요?",
        "route": "current_result",
        "uses_current_result": True,
        "needs_new_experiment": False,
        "evidence_ids": ("fixture_result",),
        "requested_terms": ("vth",),
        "suggested_followup": "다음 지표도 확인해 볼까요?",
    }
    broken = (
        ("같은 문장입니다. 같은 문장입니다.", "answer_repeats_sentence"),
        ("현재 결과에서 Vth가 왜 감소했나요?", "answer_echoes_question"),
        ("Vth가 감소했습니다. evidence_id: ev_bad", "internal_reference_exposed"),
    )
    for answer, expected in broken:
        try:
            validate_answer_quality(answer=answer, **common)
        except ValueError as error:
            assert str(error) == "answer_quality_" + expected
        else:
            raise AssertionError(f"{expected} was accepted")

    try:
        validate_answer_quality(
            **{**common, "answer": "Vth가 감소했습니다.", "evidence_ids": ()}
        )
    except ValueError as error:
        assert str(error) == "answer_quality_result_evidence_boundary"
    else:
        raise AssertionError("ungrounded current-result answer was accepted")


def test_quality_contract_keeps_style_checks_soft() -> None:
    report = audit_answer_quality(
        domain="iv",
        question="DIBL의 원인을 최대한 자세히 설명해줘.",
        answer="DIBL은 Drain bias에 따른 문턱전압 변화입니다.",
        route="explain_metric",
        uses_current_result=False,
        needs_new_experiment=False,
        requested_terms=("dibl",),
    )
    assert report.passed
    assert set(report.quality_warnings) == {
        "causal_depth",
        "requested_detail_depth",
    }


def test_quality_contract_accepts_korean_technical_aliases() -> None:
    report = audit_answer_quality(
        domain="field",
        question="전기장 집중은 무엇을 뜻해?",
        answer=(
            "전계 집중은 전위가 짧은 거리에서 크게 변하는 영역을 뜻합니다. "
            "이로 인해 특정 위치에서 전기장이 크게 나타날 수 있습니다."
        ),
        route="define_display",
        uses_current_result=False,
        needs_new_experiment=False,
        requested_terms=("field_concentration",),
    )
    assert report.checks["requested_term_coverage"]
    assert report.passed


def test_validation_failure_record_is_private_and_replay_can_be_opted_in() -> None:
    private = build_validation_failure_record(
        domain="field",
        stage="field_answer_generation_repair",
        validation_code="answer_quality_answer_repeats_sentence",
        repair_validation_code="answer_quality_answer_repeats_sentence",
        question="현재 채널 전계는 어떻게 보여?",
        model="test-model",
        request_bytes=4096,
        provider_response={
            "answer": "전계가 집중됩니다. 전계가 집중됩니다.",
            "used_evidence_ids": ["fixture"],
        },
    ).to_dict()
    assert private["question_fingerprint"]
    assert private["question_length"] > 0
    assert private["response_keys"] == (
        "answer",
        "used_evidence_ids",
    )
    assert private["replay_payload"] is None
    assert "현재 채널" not in json.dumps(private, ensure_ascii=False)

    replay = build_validation_failure_record(
        domain="field",
        stage="field_answer_generation_repair",
        validation_code="invalid",
        question="재현 질문",
        model="test-model",
        provider_response={"answer": "재현 응답"},
        include_replay_content=True,
    ).to_dict()
    assert replay["replay_payload"] == {
        "question": "재현 질문",
        "provider_response": {"answer": "재현 응답"},
    }
