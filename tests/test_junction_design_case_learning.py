from __future__ import annotations

from backend.learning import (
    ElectricalChange,
    LearningAnalysisContext,
    LearningKnowledgeAssembler,
    load_theory_knowledge_base,
    load_topic,
)
from backend.learning.model_answer import build_grounded_model_answer
from frontend.visualization.case_study.panel import (
    CASE_CORE_SUMMARIES,
    CASE_UNDERSTANDING_GUIDES,
    QUESTION_REVIEW_GUIDES,
)


def _change(before: float, after: float, direction: str, unit: str, name: str) -> ElectricalChange:
    return ElectricalChange(
        before=before,
        after=after,
        difference=after - before,
        change_percent=(after - before) / before * 100,
        change_ratio=after / before,
        direction=direction,
        unit=unit,
        available=True,
        evidence_id=f"metric:{name}",
    )


def _result(condition_id: str, label: str, sd: float, ldd: float, ion: float, ron: float) -> dict:
    return {
        "condition_id": condition_id,
        "label": label,
        "conditions": {"L": 700, "T": 20, "B": 1e16, "SD": sd, "LDD": ldd},
        "electrical_parameters": {"ion_ma_per_um": ion, "ron_kohm_um": ron},
    }


def _context() -> LearningAnalysisContext:
    return LearningAnalysisContext(
        experiment={
            "changed_parameter": "LDD",
            "changed_parameters": ["LDD"],
            "before": 5e17,
            "after": 5e18,
            "comparison_design": "two_by_two",
            "baseline_conditions": {"L": 700, "T": 20, "B": 1e16, "SD": 1e20, "LDD": 5e17},
            "comparison_conditions": {"L": 700, "T": 20, "B": 1e16, "SD": 1e20, "LDD": 5e18},
            "fixed_parameters": {"L": 700, "T": 20, "B": 1e16, "SD": 1e20},
            "condition_results": [
                _result("low_sd_low_ldd", "LowSD·LowLDD", 1e19, 5e17, 2.9087, 0.55004),
                _result("low_sd_high_ldd", "LowSD·HighLDD", 1e19, 5e18, 3.0583, 0.50924),
                _result("baseline", "HighSD·LowLDD", 1e20, 5e17, 2.9795, 0.53536),
                _result("comparison", "HighSD·HighLDD", 1e20, 5e18, 3.1786, 0.49495),
            ],
        },
        electrical_changes={
            "ion": _change(2.9795, 3.1786, "increase", "mA/um", "ion"),
            "ron": _change(0.53536, 0.49495, "decrease", "kohm um", "ron"),
            "ioff": _change(0.0002703, 0.0002975, "increase", "mA/um", "ioff"),
            "dibl": _change(24.3805, 24.6716, "increase", "mV/V", "dibl"),
        },
        in_training_range=True,
        analysis_status="complete",
    )


def test_junction_case_contract_and_ui_content() -> None:
    topic = load_topic("source_drain_ldd_junction_engineering")
    assert [item.question_id for item in topic.prediction_questions] == [
        "junction_pred_ion", "junction_pred_ron", "junction_pred_best_drive",
    ]
    assert [item.question_id for item in topic.observation_questions] == [
        "junction_obs_iv_interaction", "junction_obs_iv_tradeoff", "junction_obs_field_pairs",
    ]
    assert topic.comparison_design == "two_by_two"
    assert topic.display_parameters == ("SD", "LDD")
    assert len(CASE_UNDERSTANDING_GUIDES[topic.topic_id]["evidence"]) == 3
    assert len(CASE_CORE_SUMMARIES[topic.topic_id]) == 3
    assert all(
        question.question_id in QUESTION_REVIEW_GUIDES
        for question in (*topic.prediction_questions, *topic.observation_questions)
    )


def test_junction_model_answer_and_ai_context_use_four_conditions() -> None:
    topic = load_topic("source_drain_ldd_junction_engineering")
    context = _context()
    answer = build_grounded_model_answer(topic, context)
    assert "2×2 접합 조건" in answer
    assert "5.14%" in answer and "6.68%" in answer
    assert "HighSD·HighLDD" in answer
    assert "보편적 최적" in answer

    layers = LearningKnowledgeAssembler.build(
        topic,
        context,
        load_theory_knowledge_base().retrieve(topic.theory_concepts),
    )
    assert layers.experiment_facts["comparison_design"] == "two_by_two"
    assert len(layers.experiment_facts["condition_results"]) == 4
