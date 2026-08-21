from __future__ import annotations

import inspect

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
    CaseStudyPanel,
    format_case_comparison,
)


def _change(
    before: float,
    after: float,
    direction: str,
    unit: str,
    evidence_id: str,
) -> ElectricalChange:
    return ElectricalChange(
        before=before,
        after=after,
        difference=after - before,
        change_percent=((after - before) / before * 100.0),
        change_ratio=after / before,
        direction=direction,
        unit=unit,
        available=True,
        evidence_id=evidence_id,
    )


def _condition_result(
    condition_id: str,
    label: str,
    length: float,
    oxide: float,
    *,
    ss: float,
    dibl: float,
    ioff: float,
) -> dict:
    return {
        "condition_id": condition_id,
        "label": label,
        "conditions": {
            "L": length,
            "T": oxide,
            "B": 1e16,
            "SD": 1e20,
            "LDD": 1e18,
        },
        "electrical_parameters": {
            "ss_mv_per_dec": ss,
            "dibl_gm_v_per_v": dibl / 1000.0,
            "ioff_ma_per_um": ioff,
        },
    }


def _context() -> LearningAnalysisContext:
    return LearningAnalysisContext(
        experiment={
            "changed_parameter": "T",
            "changed_parameters": ["T"],
            "before": 20.0,
            "after": 10.0,
            "baseline_conditions": {
                "L": 300.0,
                "T": 20.0,
                "B": 1e16,
                "SD": 1e20,
                "LDD": 1e18,
            },
            "comparison_conditions": {
                "L": 300.0,
                "T": 10.0,
                "B": 1e16,
                "SD": 1e20,
                "LDD": 1e18,
            },
            "fixed_parameters": {
                "L": 300.0,
                "B": 1e16,
                "SD": 1e20,
                "LDD": 1e18,
            },
            "condition_results": [
                _condition_result(
                    "long_thick", "Long·Thick", 700, 20,
                    ss=77.3249, dibl=24.8276, ioff=0.0002713,
                ),
                _condition_result(
                    "long_thin", "Long·Thin", 700, 10,
                    ss=69.2707, dibl=13.6209, ioff=0.0066523,
                ),
                _condition_result(
                    "baseline", "Short·Thick", 300, 20,
                    ss=93.1274, dibl=114.2123, ioff=0.0271068,
                ),
                _condition_result(
                    "comparison", "Short·Thin", 300, 10,
                    ss=75.4819, dibl=59.2768, ioff=0.0669082,
                ),
            ],
        },
        electrical_changes={
            "ss": _change(93.1274, 75.4819, "decrease", "mV/dec", "metric:ss"),
            "dibl": _change(114.2123, 59.2768, "decrease", "mV/V", "metric:dibl"),
            "ioff": _change(0.0271068, 0.0669082, "increase", "mA/um", "metric:ioff"),
            "ion": _change(8.61236, 16.3437, "increase", "mA/um", "metric:ion"),
        },
        in_training_range=True,
        analysis_status="complete",
    )


def test_channel_oxide_case_has_three_predictions_and_observations() -> None:
    topic = load_topic("channel_oxide_electrostatic_compensation")

    assert [question.question_id for question in topic.prediction_questions] == [
        "comp_pred_ss",
        "comp_pred_dibl",
        "comp_pred_recovery",
    ]
    assert [question.question_id for question in topic.observation_questions] == [
        "comp_obs_iv_interaction",
        "comp_obs_iv_boundary",
        "comp_obs_field_pairing",
    ]
    assert all(question.reason_required for question in topic.prediction_questions)
    assert all(question.reason_required for question in topic.observation_questions)
    assert topic.prediction_questions[0].correct_options == ("감소",)
    assert topic.prediction_questions[1].correct_options == ("감소",)
    assert "Gate 제어 보상" in topic.observation_questions[1].correct_options[0]
    assert "잔류 SCE" in topic.observation_questions[1].correct_options[0]


def test_channel_oxide_case_ui_exposes_four_condition_contract() -> None:
    topic_id = "channel_oxide_electrostatic_compensation"
    topic = load_topic(topic_id)

    assert len(CASE_UNDERSTANDING_GUIDES[topic_id]["evidence"]) == 3
    assert len(CASE_CORE_SUMMARIES[topic_id]) == 3
    for question in (*topic.prediction_questions, *topic.observation_questions):
        assert question.question_id in QUESTION_REVIEW_GUIDES
        assert len(QUESTION_REVIEW_GUIDES[question.question_id]["model_sections"]) == 3
    caption, baseline, comparison = format_case_comparison(topic)
    assert "Short Channel" in caption
    assert (baseline, comparison) == ("Short·Thick", "Short·Thin")
    assert PLANNED_CASES == ()
    assert "reference_conditions" in inspect.getsource(
        CaseStudyPanel._build_introduction
    )
    assert "self._labeled_display_runs()" in inspect.getsource(
        CaseStudyPanel._build_curve_view
    )
    assert "self._labeled_display_runs()" in inspect.getsource(
        CaseStudyPanel._build_field_view
    )
    assert "self.result.display_runs" in inspect.getsource(
        CaseStudyPanel._labeled_display_runs
    )


def test_channel_oxide_model_answer_separates_compensation_from_recovery() -> None:
    answer = build_grounded_model_answer(
        load_topic("channel_oxide_electrostatic_compensation"),
        _context(),
    )

    assert "L=700/300 nm와 T=20/10 nm의 네 조건" in answer
    assert "부분적 보상" in answer
    assert "완전한 회복" in answer
    assert "54.94 mV/V" in answer
    assert "대각선 두 조건" in answer


def test_channel_oxide_condition_results_reach_ai_knowledge_layers() -> None:
    topic = load_topic("channel_oxide_electrostatic_compensation")
    context = _context()
    theory = load_theory_knowledge_base().retrieve(topic.theory_concepts)
    layers = LearningKnowledgeAssembler.build(topic, context, theory)

    assert layers.experiment_facts["comparison_design"] == "two_by_two"
    assert not layers.experiment_facts["controlled_single_parameter_comparison"]
    assert len(layers.experiment_facts["condition_results"]) == 4

    result = LearningLLMService().ask_followup(
        topic,
        "이번 결과에서 얇은 Oxide가 짧은 Channel의 DIBL을 얼마나 보상했나요?",
        context,
    )
    assert result.question_type == "current_result"
    assert result.uses_current_result
    assert "metric:dibl" in result.evidence_ids
    assert {"oxide_thickness", "dibl", "short_channel_effect"} <= set(
        result.theory_concepts
    )
