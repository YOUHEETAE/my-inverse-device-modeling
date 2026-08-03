from __future__ import annotations

import json
from pathlib import Path

from backend.learning import (
    LearningAnalysisContext,
    LearningLLMService,
    load_theory_knowledge_base,
    load_topic,
)


FIXTURE = Path(__file__).parent / "fixtures" / "learning" / "sce_channel_length_analysis.json"


def _context() -> LearningAnalysisContext:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return LearningAnalysisContext.from_dict(data["learning_context"])


def test_knowledge_base_is_valid_and_retrieves_related_concepts() -> None:
    knowledge = load_theory_knowledge_base()
    assert knowledge.knowledge_id == "semiconductor_theory_core"
    assert len(knowledge.concepts) >= 19
    retrieved = knowledge.retrieve(["threshold_voltage"])
    assert [item.concept_id for item in retrieved] == [
        "threshold_voltage",
        "short_channel_effect",
        "dibl",
        "source_barrier",
    ]
    assert all(item.summary and item.principles for item in retrieved)


def test_current_vth_and_ss_answers_combine_metrics_with_theory() -> None:
    topic, context = load_topic("sce_channel_length"), _context()
    service = LearningLLMService()

    vth = service.ask_followup(
        topic,
        "결과에서 Vth가 감소하는 이유가 뭐야?",
        context,
    )
    assert vth.question_type == "current_result"
    assert vth.evidence_ids == ("metric:vth_high",)
    assert "0.5976" in vth.answer and "0.4416 V" in vth.answer
    assert "Drain" in vth.answer and "장벽" in vth.answer
    assert "threshold_voltage" in vth.theory_concepts
    assert vth.case_connection

    ss = service.ask_followup(
        topic,
        "그럼 결과에서 SS는 왜 증가해?",
        context,
    )
    assert ss.evidence_ids == ("metric:ss",)
    assert "69.27" in ss.answer and "75.48 mV/dec" in ss.answer
    assert "off-state 전류" in ss.answer


def test_adjacent_and_hypothetical_answers_do_not_claim_current_results() -> None:
    topic, context = load_topic("sce_channel_length"), _context()
    service = LearningLLMService()

    junction = service.ask_followup(
        topic,
        "PN 접합에서 접합 길이가 짧아지면 어떻게 돼?",
        context,
    )
    assert junction.relevance_to_case == "domain_adjacent"
    assert junction.needs_clarification
    assert not junction.uses_current_result and not junction.evidence_ids
    assert "공핍영역" in junction.answer
    assert "punch-through" in junction.answer
    assert "현재 700 nm와 300 nm 비교에서 직접 확인한 결과가 아닙니다" in junction.answer
    assert {"pn_junction", "depletion_region", "punch_through"} <= set(
        junction.theory_concepts
    )

    body = service.ask_followup(
        topic,
        "Body doping을 높이면 DIBL이 줄어?",
        context,
    )
    assert body.question_type == "hypothetical"
    assert body.needs_new_experiment and not body.uses_current_result
    assert not body.evidence_ids
    assert "DIBL과 punch-through 억제에 유리" in body.answer
    assert "trade-off" in body.answer
    assert {"body_doping", "dibl"} <= set(body.theory_concepts)


def test_potential_guidance_comes_from_shared_theory_not_metric_invention() -> None:
    response = LearningLLMService().ask_followup(
        load_topic("sce_channel_length"),
        "Potential Map에서는 어디를 봐야 해?",
        _context(),
    )
    assert response.question_type == "case_theory"
    assert not response.evidence_ids
    assert "Drain" in response.answer
    assert "Source" in response.answer
    assert "색만으로 직접 비교하지 않는다" in response.answer
    assert response.theory_concepts[0] == "potential"
