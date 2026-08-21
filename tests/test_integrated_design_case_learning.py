from __future__ import annotations

from backend.learning import (
    ElectricalChange,
    LearningAnalysisContext,
    LearningKnowledgeAssembler,
    LearningLLMService,
    load_theory_knowledge_base,
    load_topic,
)
from backend.learning.model_answer import build_grounded_model_answer
from frontend.visualization.case_study.panel import (
    CASE_CORE_SUMMARIES,
    CASE_UNDERSTANDING_GUIDES,
    PLANNED_CASES,
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


def _candidate(condition_id: str, label: str, conditions: dict, metrics: dict) -> dict:
    return {
        "condition_id": condition_id,
        "label": label,
        "conditions": conditions,
        "electrical_parameters": metrics,
    }


def _context() -> LearningAnalysisContext:
    control = {"L": 700, "T": 10, "B": 5e16, "SD": 1e20, "LDD": 5e17}
    balanced = {"L": 300, "T": 10, "B": 5e16, "SD": 1e20, "LDD": 5e17}
    return LearningAnalysisContext(
        experiment={
            "changed_parameter": "L",
            "changed_parameters": ["L"],
            "before": 700,
            "after": 300,
            "comparison_design": "candidate_set",
            "baseline_conditions": control,
            "comparison_conditions": balanced,
            "fixed_parameters": {"T": 10, "B": 5e16, "SD": 1e20, "LDD": 5e17},
            "condition_results": [
                _candidate("drive", "Drive", {"L": 300, "T": 10, "B": 1e16, "SD": 1e20, "LDD": 5e18}, {"ion_ma_per_um": 19.2258, "ioff_ma_per_um": 0.0800269, "ss_mv_per_dec": 76.7968, "dibl_gm_v_per_v": 0.0700262}),
                _candidate("leakage", "Leakage", {"L": 700, "T": 20, "B": 5e16, "SD": 1e19, "LDD": 5e17}, {"ion_ma_per_um": 1.85494, "ioff_ma_per_um": 1.564e-8, "ss_mv_per_dec": 92.6293, "dibl_gm_v_per_v": 0.0148626}),
                _candidate("baseline", "Control", control, {"ion_ma_per_um": 4.89716, "ioff_ma_per_um": 3.158e-5, "ss_mv_per_dec": 76.8789, "dibl_gm_v_per_v": 0.0061184}),
                _candidate("comparison", "Balanced", balanced, {"ion_ma_per_um": 12.9820, "ioff_ma_per_um": 0.00061353, "ss_mv_per_dec": 76.3035, "dibl_gm_v_per_v": 0.0226727}),
            ],
        },
        electrical_changes={
            "ion": _change(4.89716, 12.9820, "increase", "mA/um", "ion"),
            "ioff": _change(3.158e-5, 0.00061353, "increase", "mA/um", "ioff"),
            "dibl": _change(6.1184, 22.6727, "increase", "mV/V", "dibl"),
            "ss": _change(76.8789, 76.3035, "decrease", "mV/dec", "ss"),
            "ron": _change(0.30302, 0.13168, "decrease", "kohm um", "ron"),
        },
        in_training_range=True,
        analysis_status="complete",
    )


def test_integrated_case_is_the_eight_case_capstone() -> None:
    topic = load_topic("integrated_device_design")
    assert topic.catalog_order == 8
    assert topic.comparison_design == "candidate_set"
    assert topic.display_parameters == ("L", "T", "B", "SD", "LDD")
    assert PLANNED_CASES == ()
    assert [item.question_id for item in topic.prediction_questions] == [
        "design_pred_highest_ion", "design_pred_lowest_ioff", "design_pred_target_choice",
    ]
    assert [item.question_id for item in topic.observation_questions] == [
        "design_obs_constraint_filter", "design_obs_rejection_reasons", "design_obs_field_margin",
    ]
    assert len(CASE_UNDERSTANDING_GUIDES[topic.topic_id]["evidence"]) == 3
    assert len(CASE_CORE_SUMMARIES[topic.topic_id]) == 3
    assert all(
        item.question_id in QUESTION_REVIEW_GUIDES
        for item in (*topic.prediction_questions, *topic.observation_questions)
    )


def test_integrated_model_answer_filters_all_candidates_and_reaches_ai() -> None:
    topic = load_topic("integrated_device_design")
    context = _context()
    answer = build_grounded_model_answer(topic, context)
    for label in ("Drive", "Leakage", "Control", "Balanced"):
        assert label in answer
    assert "Balanced만 통과" in answer
    assert "feasible candidate" in answer
    assert "Field Map은 전기적 사양 검사를 대체하지" in answer

    layers = LearningKnowledgeAssembler.build(
        topic,
        context,
        load_theory_knowledge_base().retrieve(topic.theory_concepts),
    )
    assert layers.experiment_facts["comparison_design"] == "candidate_set"
    assert len(layers.experiment_facts["condition_results"]) == 4

    response = LearningLLMService().ask_followup(
        topic,
        "이번 결과에서 Balanced 후보의 Ion, Ioff, DIBL, SS가 목표를 어떻게 만족했나요?",
        context,
    )
    assert response.question_type == "current_result"
    assert response.uses_current_result
    assert {"metric:ion", "metric:ioff", "metric:dibl", "metric:ss"} <= set(
        response.evidence_ids
    )
