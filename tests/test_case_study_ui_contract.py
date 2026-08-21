from __future__ import annotations

import inspect
from types import SimpleNamespace

import numpy as np
from matplotlib.figure import Figure

from ai.curve_model.inference import CurvePrediction
from backend.learning import (
    LearningAnalysisContext,
    LearningSession,
    LearningStep,
    load_topic,
    load_topics,
)
from frontend.app import IntegratedModelApp
from frontend.visualization.case_study import CaseStudyPanel
from frontend.visualization.case_study.panel import (
    CASE_CORE_SUMMARIES,
    CASE_UNDERSTANDING_GUIDES,
    COMPACT_PARAMETER_PANEL_WIDTH,
    FOLLOWUP_EXAMPLES,
    LEARNING_PAGE_LABELS,
    LEARNING_PAGE_ORDER,
    METRIC_LABELS,
    METRIC_TABLE_SPECS,
    OBSERVATION_PANEL_WIDTH,
    PLANNED_CASES,
    QUESTION_REVIEW_GUIDES,
    STEP_LABELS,
    STEP_ORDER,
    format_case_comparison,
    format_condition_details,
    format_curve_condition_label,
    format_error_guidance,
    format_followup_metadata,
    split_model_answer_sections,
    topic_condition_rows,
)
from frontend.visualization.curve_rendering import render_curve_figure
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


def test_case_study_exposes_four_persistent_learning_pages() -> None:
    assert LEARNING_PAGE_ORDER == (
        "understanding",
        "prediction",
        "observation",
        "explanation",
    )
    assert tuple(LEARNING_PAGE_LABELS.values()) == (
        "1. Case 이해",
        "2. 초기 예측",
        "3. 결과 관찰",
        "4. 최종 설명",
    )
    render_source = inspect.getsource(CaseStudyPanel.render)
    assert "_refresh_learning_navigation()" in render_source
    assert "_build_prediction_review()" in render_source
    assert "_build_observation_review()" in render_source
    init_source = inspect.getsource(CaseStudyPanel.__init__)
    navigation_source = inspect.getsource(
        CaseStudyPanel._refresh_learning_navigation
    )
    assert "self.learning_progress_segments" in init_source
    assert 'height=4' in init_source
    assert 'background="#d1d5db"' in init_source
    assert 'background="#16a34a" if unlocked else "#d1d5db"' in navigation_source
    assert "ttk.Progressbar" not in init_source
    assert "· 현재" not in navigation_source
    assert "LearningActive.TButton" in navigation_source


def test_learning_page_locks_follow_saved_session_progress() -> None:
    topic = load_topic("sce_channel_length")
    panel = object.__new__(CaseStudyPanel)
    panel.session = LearningSession.create(topic)

    assert panel._is_learning_page_unlocked("understanding")
    assert not panel._is_learning_page_unlocked("prediction")
    assert not panel._is_learning_page_unlocked("observation")
    assert not panel._is_learning_page_unlocked("explanation")

    panel.session.current_step = LearningStep.PREDICTION_QUESTION
    assert panel._is_learning_page_unlocked("prediction")
    assert not panel._is_learning_page_unlocked("observation")

    panel.session.analysis_snapshot = {"saved": True}
    assert panel._is_learning_page_unlocked("observation")
    assert not panel._is_learning_page_unlocked("explanation")

    panel.session.feedback_snapshot = {"headline": "완료"}
    assert panel._is_learning_page_unlocked("explanation")


def test_submitted_answers_have_read_only_review_surfaces() -> None:
    prediction_source = inspect.getsource(CaseStudyPanel._build_prediction_review)
    observation_source = inspect.getsource(CaseStudyPanel._build_observation_review)
    review_source = inspect.getsource(CaseStudyPanel._build_answer_review)
    assert "제출 후에는 수정되지 않습니다" in prediction_source
    assert "_latest_prediction_answers()" in prediction_source
    assert "_latest_observation_answers()" in observation_source
    assert "Radiobutton" in review_source
    assert "Checkbutton" in review_source
    assert "state=tk.DISABLED" in review_source
    assert "reason_box.configure(state=tk.DISABLED)" in review_source
    assert "self._review_variables.append" in review_source
    assert "wraplength=400" in observation_source


def test_completed_page_has_one_flat_synchronized_tab_row() -> None:
    source = inspect.getsource(CaseStudyPanel._build_complete)
    assert 'notebook.add(summary_tab, text="학습 요약")' in source
    assert 'notebook.add(curve_tab, text="I–V Curve")' in source
    assert 'notebook.add(field_tab, text="Field Map")' in source
    assert 'notebook.add(chat_tab, text="AI 자유 질문")' in source
    assert 'text="결과 다시 보기"' not in source
    assert "self._build_results(" not in source
    assert "self._build_curve_view(curve_view)" in source
    assert "self._build_field_view(field_tab)" in source
    assert "self._build_chat(chat_tab)" in source
    assert 'remembered["result_view_tab"] = selected_label' in source
    assert "self._feedback_cards(" in source
    assert "self._build_learning_journey_summary(" in source
    assert "show_headline=False" in source
    assert "scrollregion" in source
    assert "확인한 개념:" not in source
    assert "복습할 개념:" not in source
    assert 'text="학습 완료"' not in source
    assert 'text="학습 완료됨"' not in source


def test_completed_summary_connects_saved_answers_to_actual_results() -> None:
    journey_source = inspect.getsource(
        CaseStudyPanel._build_learning_journey_summary
    )
    question_source = inspect.getsource(
        CaseStudyPanel._build_question_review_card
    )
    actual_source = inspect.getsource(CaseStudyPanel._build_question_actual_results)
    core_source = inspect.getsource(CaseStudyPanel._build_core_summary)
    feedback_source = inspect.getsource(CaseStudyPanel._feedback_cards)
    assert 'text="초기 예측 → 실제 결과"' in journey_source
    assert "self._latest_prediction_answers()" in journey_source
    assert 'phase="prediction"' in journey_source
    assert 'text="결과를 보고 제출한 관찰"' in journey_source
    assert "self._latest_observation_answers()" in journey_source
    assert 'phase="observation"' in journey_source
    assert '("내 답변", selected_text' in question_source
    assert '"현재 Case 결과"' in question_source
    assert '"확인된 결과"' in question_source
    assert "confirmed_text" in question_source
    assert '("비교", verdict' in question_source
    assert 'text="내가 작성한 근거"' in question_source
    assert 'text="이 질문의 모범 답안"' in question_source
    assert 'text="질문과 연결된 실제 결과"' in actual_source
    assert '("지표", baseline_label, comparison_label, "변화")' in actual_source
    assert 'text="핵심 정리"' in core_source
    assert "CASE_CORE_SUMMARIES" in core_source
    assert "self._build_model_answer_sections(" in feedback_source
    assert "self._build_personalized_feedback(" in feedback_source


def test_case_one_question_review_guides_use_one_common_card_contract() -> None:
    expected = {
        "sce_pred_ion": ("ion",),
        "sce_pred_ioff": ("ioff",),
        "sce_pred_dibl": ("dibl",),
        "sce_obs_subthreshold": (),
        "sce_obs_tradeoff": ("ioff", "dibl", "ss"),
        "sce_obs_field_coupling": ("ioff", "dibl"),
    }
    assert {
        question_id: tuple(QUESTION_REVIEW_GUIDES[question_id]["metric_keys"])
        for question_id in expected
    } == expected
    for question_id in expected:
        guide = QUESTION_REVIEW_GUIDES[question_id]
        assert guide["title"]
        assert guide["model_sections"]
    card_source = inspect.getsource(CaseStudyPanel._build_question_review_card)
    assert "QUESTION_REVIEW_GUIDES.get(question.question_id" in card_source
    assert 'model_text = "\\n".join(' in card_source
    assert 'f"{heading} · {text}" for heading, text in model_sections' in card_source


def test_completed_summary_orders_core_review_model_answer_and_feedback() -> None:
    source = inspect.getsource(CaseStudyPanel._build_complete)
    assert source.index("self._build_core_summary(") < source.index(
        "self._build_learning_journey_summary("
    )
    assert source.index("self._build_learning_journey_summary(") < source.index(
        "self._feedback_cards("
    )
    assert len(CASE_CORE_SUMMARIES["sce_channel_length"]) == 3


def test_model_answer_is_rendered_as_named_full_width_sections() -> None:
    raw = (
        "[현재 Case의 핵심 메커니즘]\n설명 1\n\n"
        "[현재 Case의 I–V 근거]\n설명 2"
    )
    assert split_model_answer_sections(raw) == (
        ("현재 Case의 핵심 메커니즘", "설명 1"),
        ("I–V Curve에서 확인된 근거", "설명 2"),
    )
    source = inspect.getsource(CaseStudyPanel._build_model_answer_sections)
    assert 'text="전체 모범 답안"' in source
    assert '("지표", "실제 변화", "방향", "물리적 설명")' in source
    assert "split_model_answer_sections(model_answer)" in source


def test_personalized_feedback_hides_empty_evidence_review() -> None:
    assert not CaseStudyPanel._focus_is_actionable(
        "추가로 다시 확인할 Curve 위치 없음"
    )
    assert CaseStudyPanel._focus_is_actionable(
        "log(Id)–Vg의 subthreshold 구간을 다시 확인하세요."
    )
    source = inspect.getsource(CaseStudyPanel._build_personalized_feedback)
    assert 'text="내 학습 피드백"' in source
    assert '("잘 이해한 부분", data.get("positive_feedback", []))' in source
    assert '("보완할 부분", data.get("corrections", []))' in source
    assert 'text="다시 확인할 근거"' in source
    assert 'focus_items.append(("I–V Curve에서 확인"' in source
    assert 'focus_items.append(("Field Map에서 확인"' in source
    humanized = CaseStudyPanel._humanize_feedback_line(
        "ion_can_increase 개념을 확인했습니다."
    )
    assert humanized == "채널 길이 감소에 따른 Ion 증가 개념을 확인했습니다."
    assert "ion_can_increase" not in humanized


def test_question_verdict_judges_selection_without_scoring_the_reason() -> None:
    topic = load_topic("sce_channel_length")
    ion_question = topic.prediction_questions[0]
    tradeoff_question = topic.observation_questions[1]
    assert CaseStudyPanel._question_verdict(
        ion_question,
        ("증가",),
        phase="prediction",
    )[0] == "현재 결과와 일치"
    assert CaseStudyPanel._question_verdict(
        ion_question,
        ("감소",),
        phase="prediction",
    )[0] == "현재 결과와 다름"
    assert CaseStudyPanel._question_verdict(
        tradeoff_question,
        (
            "Ioff 증가 — 고정된 off-bias에서 누설 전류가 커졌다",
            "DIBL 증가 — Drain bias에 대한 Channel 장벽과 Vth의 민감도가 커졌다",
        ),
        phase="observation",
    )[0] == "일부 일치"
    assert CaseStudyPanel._question_verdict(
        tradeoff_question,
        (
            "Ron 감소 — on-state 전압 강하가 줄었으므로 고정 off-bias의 Ioff 증가는 누설 비용으로 보지 않는다",
        ),
        phase="observation",
    )[0] == "관찰 보완 필요"


def test_feedback_ready_opens_the_stable_completed_layout_immediately() -> None:
    source = inspect.getsource(CaseStudyPanel.render)
    assert "LearningStep.FEEDBACK_READY" in source
    assert "LearningStep.NEXT_EXPERIMENT" in source
    assert "LearningStep.SESSION_COMPLETE" in source
    assert "self._build_complete()" in source
    assert "elif step == LearningStep.FEEDBACK_READY" not in source
    evaluation_source = inspect.getsource(CaseStudyPanel._start_evaluation)
    assert "LearningStep.SESSION_COMPLETE" in evaluation_source
    panel_source = inspect.getsource(CaseStudyPanel)
    assert 'text="현재 Case 완료"' not in panel_source
    assert 'text="Case 학습 완료"' not in panel_source


def test_curve_and_field_saved_results_offer_regeneration() -> None:
    curve_source = inspect.getsource(CaseStudyPanel._build_curve_view)
    field_source = inspect.getsource(CaseStudyPanel._build_field_view)
    simulation_source = inspect.getsource(CaseStudyPanel._start_simulation)
    assert 'text="그래프 다시 생성"' in curve_source
    assert 'text="Field Map 다시 생성"' in field_source
    assert "use_session_transition=False" in curve_source
    assert "use_session_transition=False" in field_source
    assert "self._labeled_display_runs()" in curve_source
    assert "self._labeled_display_runs()" in field_source
    labels_source = inspect.getsource(CaseStudyPanel._labeled_display_runs)
    assert "format_curve_condition_label" in labels_source
    assert "format_case_comparison" in labels_source
    assert "values=FIELD_DISPLAYS" in field_source
    assert '"observation" if use_session_transition else self.learning_view' in simulation_source
    assert "return_completion_tab = self.completion_view_tab" in simulation_source
    assert "self.learning_view = return_learning_view" in simulation_source
    assert "self.completion_view_tab = return_completion_tab" in simulation_source
    assert 'self.learning_view = "observation"' not in simulation_source


def test_completed_curve_regeneration_returns_to_the_requesting_tab() -> None:
    topic = load_topic("sce_channel_length")
    session = LearningSession.create(topic)
    session.current_step = LearningStep.SESSION_COMPLETE
    context = LearningAnalysisContext(experiment={}, electrical_changes={})
    result = SimpleNamespace(learning_context=context)
    statuses: list[str] = []
    rendered: list[str] = []

    panel = object.__new__(CaseStudyPanel)
    panel.topic = topic
    panel.session = session
    panel.runner = SimpleNamespace(execute=lambda _topic: result)
    panel.state_machine = SimpleNamespace(transition=lambda *_args: None)
    panel.learning_view = "explanation"
    panel.completion_view_tab = "I–V Curve"
    panel.status_var = SimpleNamespace(set=statuses.append)
    panel.render = lambda: rendered.append(panel.learning_view)
    panel._save = lambda: None
    panel._run_async = lambda task, complete, _title: complete(task())

    panel._start_simulation(use_session_transition=False)

    assert panel.learning_view == "explanation"
    assert panel.completion_view_tab == "I–V Curve"
    assert panel.session.current_step is LearningStep.SESSION_COMPLETE
    assert len(rendered) == 2
    assert statuses[-1] == "예측과 분석이 완료되었습니다."


def test_question_review_cards_compact_repeated_explanation_chrome() -> None:
    source = inspect.getsource(CaseStudyPanel._build_question_review_card)
    assert 'card = ttk.LabelFrame(parent, text=title, padding=8)' in source
    assert 'text="이 질문의 모범 답안", padding=6' in source
    assert "model_text =" in source
    assert 'font=("TkDefaultFont", 9, "bold")' not in source.split(
        "model_text =", 1
    )[1]


def test_case_understanding_connects_context_question_and_evidence() -> None:
    assert set(CASE_UNDERSTANDING_GUIDES) == {
        "sce_channel_length",
        "oxide_gate_control",
        "body_doping_design_window",
        "source_drain_on_state_conduction",
        "ldd_field_resistance_tradeoff",
        "channel_oxide_electrostatic_compensation",
        "source_drain_ldd_junction_engineering",
        "integrated_device_design",
    }
    for guide in CASE_UNDERSTANDING_GUIDES.values():
        assert guide["context"]
        assert guide["question"].endswith("?")
        assert len(guide["evidence"]) == 3
        assert guide["caution"]

    source = inspect.getsource(CaseStudyPanel._build_introduction)
    for heading in (
        "Case 배경",
        "이번 Case의 핵심 질문",
        "학습 목표",
        "결과에서 확인할 근거",
        "이번 Case의 실험 조건",
        "변경 변수",
        "고정 변수",
    ):
        assert heading in source


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


def test_case_one_prediction_covers_three_target_metrics() -> None:
    topic = load_topic("sce_channel_length")
    prompts = " ".join(
        question.prompt for question in topic.prediction_questions
    )
    assert all(metric in prompts for metric in ("Ion", "Ioff", "DIBL"))
    assert {question.question_id for question in topic.prediction_questions} == {
        "sce_pred_ion",
        "sce_pred_ioff",
        "sce_pred_dibl",
    }
    assert all(
        question.type.startswith("single_select")
        for question in topic.prediction_questions
    )
    dibl_question = next(
        question
        for question in topic.prediction_questions
        if question.question_id == "sce_pred_dibl"
    )
    assert dibl_question.reason_required
    assert "DIBL의 정의" in dibl_question.prompt
    collection_source = inspect.getsource(CaseStudyPanel._collect_answers)
    assert "questions[question_id].reason_required" in collection_source
    assert "근거가 필요한 질문에 설명을 입력해주세요" in collection_source


def test_case_eight_prediction_repeats_candidate_conditions_and_intent() -> None:
    topic = load_topic("integrated_device_design")
    labels = tuple(label for label, _conditions in topic_condition_rows(topic))
    assert labels == ("Drive", "Leakage", "Control", "Balanced")
    assert set(topic.condition_descriptions) == set(labels)
    assert all(topic.condition_descriptions[label] for label in labels)
    source = inspect.getsource(CaseStudyPanel._build_prediction)
    guide_source = inspect.getsource(
        CaseStudyPanel._build_prediction_condition_guide
    )
    assert "self._build_prediction_condition_guide(wrapper)" in source
    assert "예측에 사용할 후보 조건" in guide_source
    assert "후보 이름만으로 고르지 말고" in guide_source
    assert "format_condition_details" in guide_source
    details = format_condition_details(
        topic.reference_conditions[0].conditions,
        topic.display_parameters,
    )
    assert "L 300 nm" in details
    assert "T 10 nm" in details
    assert "B 1e16 cm⁻³" in details


def test_multi_condition_curve_labels_use_actual_parameter_values() -> None:
    compensation = load_topic("channel_oxide_electrostatic_compensation")
    rows = topic_condition_rows(compensation)
    assert [
        format_curve_condition_label(compensation, label, conditions)
        for label, conditions in rows
    ] == ["L700 T20", "L700 T10", "L300 T20", "L300 T10"]

    integrated = load_topic("integrated_device_design")
    drive = integrated.reference_conditions[0]
    assert format_curve_condition_label(
        integrated,
        drive.label,
        drive.conditions,
    ) == "Drive | L300 T10 B1e16 SD1e20 LDD5e18"


def test_curve_legend_separates_condition_color_from_bias_line_style() -> None:
    grid = np.asarray([0.0, 1.0])
    biases = np.asarray([0.05, 1.5])
    currents = np.asarray([[0.0, 1.0], [0.0, 2.0]])
    idvd = CurvePrediction("idvd", grid, biases, currents)
    idvg = CurvePrediction("idvg", grid, biases, currents)
    figure = Figure()

    render_curve_figure(
        figure,
        [
            ("L700 T20", idvd, idvg),
            ("L300 T10", idvd, idvg),
        ],
    )

    axes = figure.axes[0]
    labels = tuple(text.get_text() for text in axes.get_legend().get_texts())
    assert "Condition: L700 T20" in labels
    assert "Condition: L300 T10" in labels
    assert "Bias: Vg=0.05 V" in labels
    assert "Bias: Vg=1.5 V" in labels
    assert axes.lines[0].get_color() == axes.lines[1].get_color()
    assert axes.lines[0].get_linestyle() != axes.lines[1].get_linestyle()


def test_prediction_reason_keeps_native_text_input_behavior() -> None:
    source = inspect.getsource(CaseStudyPanel._build_question)
    assert 'font="TkDefaultFont"' not in source
    assert "_grow_text_to_content" in source
    prediction_source = inspect.getsource(CaseStudyPanel._build_prediction)
    review_source = inspect.getsource(CaseStudyPanel._build_prediction_review)
    assert "scrollregion" in prediction_source
    assert "scrollregion" in review_source
    answer_review_source = inspect.getsource(CaseStudyPanel._build_answer_review)
    assert "_grow_text_to_content" in answer_review_source


def test_result_ready_opens_observation_questions_without_an_extra_gate() -> None:
    render_source = inspect.getsource(CaseStudyPanel.render)
    simulation_source = inspect.getsource(CaseStudyPanel._start_simulation)
    assert "관찰 질문 시작" not in inspect.getsource(CaseStudyPanel)
    assert "LearningStep.OBSERVATION_QUESTION" in render_source
    assert "LearningStep.OBSERVATION_QUESTION" in simulation_source


def test_case_study_panel_is_catalog_driven_for_future_topics() -> None:
    source = inspect.getsource(CaseStudyPanel.__init__)
    activate_source = inspect.getsource(CaseStudyPanel._activate_topic)
    assert "load_topics()" in source
    assert "topic_choice_box" not in source
    assert "self.topics[topic_id]" in activate_source
    assert "self._case_heading()" in activate_source
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


def test_oxide_question_reviews_link_each_question_to_its_evidence() -> None:
    topic = load_topic("oxide_gate_control")
    expected_metrics = {
        "oxide_pred_gm": ("gm_max",),
        "oxide_pred_ss": ("ss",),
        "oxide_pred_ioff": ("ioff",),
        "oxide_obs_iv_gate_control": ("gm_max", "ss"),
        "oxide_obs_iv_tradeoff": ("gm_max", "ss", "ioff"),
        "oxide_obs_field_evidence": (),
    }

    questions = (*topic.prediction_questions, *topic.observation_questions)
    assert {question.question_id for question in questions} == set(expected_metrics)
    for question in questions:
        guide = QUESTION_REVIEW_GUIDES[question.question_id]
        assert guide["metric_keys"] == expected_metrics[question.question_id]
        assert len(guide["model_sections"]) >= 3

    assert METRIC_LABELS["gm_max"] == "gm max"


def test_observation_questions_require_result_interpretation_without_giveaway_options() -> None:
    topics = tuple(
        load_topic(topic_id)
        for topic_id in (
            "sce_channel_length",
            "oxide_gate_control",
            "body_doping_design_window",
            "source_drain_on_state_conduction",
            "ldd_field_resistance_tradeoff",
            "channel_oxide_electrostatic_compensation",
            "source_drain_ldd_junction_engineering",
            "integrated_device_design",
        )
    )
    questions = tuple(
        question
        for topic in topics
        for question in topic.observation_questions
    )
    options = " ".join(
        option for question in questions for option in question.options
    )
    assert all(len(topic.observation_questions) == 3 for topic in topics)
    assert all(question.reason_required for question in questions)
    assert all(
        token not in options
        for token in (
            "만 보고",
            "없이",
            "모든 전기적 특성",
            "악화된 특성 없음",
            "breakdown을 확정",
            "둘 중 하나",
            "만 해석한다",
            "라 확정한다",
            "무관하게",
        )
    )


def test_answer_draft_is_session_scoped_and_survives_rerender() -> None:
    panel = object.__new__(CaseStudyPanel)
    panel._answer_drafts = {}
    panel._collectors_session_id = "session-a"
    panel.answer_collectors = {
        "question-a": lambda: {
            "selected": ["선택 A"],
            "reason": "작성 중인 근거",
        }
    }
    panel._capture_answer_draft()

    assert panel._answer_drafts == {
        "session-a": {
            "question-a": {
                "selected": ["선택 A"],
                "reason": "작성 중인 근거",
            }
        }
    }
    panel._discard_answer_draft("session-a")
    assert panel._answer_drafts == {}
    assert panel.answer_collectors == {}


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
    assert not hasattr(CaseStudyPanel, "_clone_selected_session")
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
    assert headline == "AI 튜터 · 현재 결과"
    assert "설명 수준" not in details
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
    chat_source = inspect.getsource(CaseStudyPanel._build_chat)
    assert 'turn.question_type != "current_result"' in chat_source


def test_case_result_and_observation_columns_use_fixed_non_draggable_layout() -> None:
    result_source = inspect.getsource(CaseStudyPanel._build_results)
    observation_source = inspect.getsource(CaseStudyPanel._build_observation)
    assert "Panedwindow" not in result_source
    assert "Panedwindow" not in observation_source
    assert "parameters.pack_propagate(False)" in result_source
    assert "questions.pack_propagate(False)" in observation_source


def test_compact_parameter_table_reserves_the_change_column_width() -> None:
    source = inspect.getsource(CaseStudyPanel._build_parameter_table)
    assert '("direction", "변화", 50)' in source
    assert "stretch=False" in source
    assert 'style="CaseMetric.Treeview"' in source
    assert "self._format_metric_table_value(before)" in source
    assert "self._format_metric_table_value(after)" in source
    assert "rows = self._metric_table_rows()" in source
    assert "_block_treeview_resize" in source
    assert METRIC_LABELS["vth"] == "Vth"
    assert METRIC_LABELS["dibl"] == "DIBL"
    assert METRIC_LABELS["ion"] == "Ion"
    assert METRIC_LABELS["ion_ioff_ratio"] == "Ion/Ioff ratio"
    assert '("metric", "Metric", 135)' in source
    assert '("before", baseline_label, 78)' in source
    assert '("after", comparison_label, 78)' in source
    assert tuple(item[0] for item in METRIC_TABLE_SPECS) == (
        "vth_low",
        "vth_high",
        "ion",
        "ioff",
        "ion_ioff_ratio",
        "ss",
        "dibl",
        "gm_max",
        "gds",
        "ron",
        "lambda_clm",
    )


def test_metric_table_snapshot_always_returns_the_canonical_eleven_rows() -> None:
    panel = object.__new__(CaseStudyPanel)
    panel.context = LearningAnalysisContext(
        experiment={
            "display_electrical_parameters": {
                "baseline": {
                    "values": {
                        "vth_low_v": 0.4,
                        "dibl_gm_v_per_v": 0.05,
                    }
                },
                "comparison": {
                    "values": {
                        "vth_low_v": 0.35,
                        "dibl_gm_v_per_v": 0.08,
                    }
                },
            }
        },
        electrical_changes={},
    )

    rows = panel._metric_table_rows()

    assert tuple(row[0] for row in rows) == tuple(
        item[0] for item in METRIC_TABLE_SPECS
    )
    assert len(rows) == 11
    assert rows[0] == ("vth_low", 0.4, 0.35, "decrease", "V")
    assert rows[1][1:4] == (None, None, "unavailable")
    assert rows[6] == ("dibl", 50.0, 80.0, "increase", "mV/V")
    assert panel._format_metric_table_value(None) == "—"


def test_legacy_metric_table_keeps_missing_metrics_visible() -> None:
    panel = object.__new__(CaseStudyPanel)
    panel.context = LearningAnalysisContext(
        experiment={},
        electrical_changes={},
    )

    rows = panel._metric_table_rows()

    assert len(rows) == 11
    assert all(row[1:4] == (None, None, "unavailable") for row in rows)


def test_saved_observation_answers_resume_evaluation_without_manual_button() -> None:
    source = inspect.getsource(CaseStudyPanel._build_loading)
    assert "저장된 답변 평가 계속" not in source
    assert "self.window.after_idle(self._resume_evaluation_if_idle)" in source


def test_observation_and_feedback_use_fixed_wider_explanation_columns() -> None:
    result_source = inspect.getsource(CaseStudyPanel._build_results)
    observation_source = inspect.getsource(CaseStudyPanel._build_observation)
    observation_review_source = inspect.getsource(
        CaseStudyPanel._build_observation_review
    )
    feedback_source = inspect.getsource(CaseStudyPanel._build_feedback)
    assert "width=COMPACT_PARAMETER_PANEL_WIDTH" in result_source
    assert "width=OBSERVATION_PANEL_WIDTH" in observation_source
    assert "width=OBSERVATION_PANEL_WIDTH" in observation_review_source
    assert COMPACT_PARAMETER_PANEL_WIDTH == 360
    assert OBSERVATION_PANEL_WIDTH == 560
    assert "width=620" in feedback_source
    assert "actions.pack(side=tk.BOTTOM" in observation_source
    assert "scrollregion" in observation_source
    assert "fit_question_width" in observation_source
    assert "_bind_feedback_mousewheel(canvas)" in observation_source
    assert "scrollregion" in observation_review_source
    assert "fit_answer_width" in observation_review_source
    assert "_bind_feedback_mousewheel(canvas)" in observation_review_source
    assert "wraplength: int = 540" in inspect.getsource(
        CaseStudyPanel._feedback_cards
    )
    assert "추천 행동 진행" not in feedback_source
    personalized_source = inspect.getsource(
        CaseStudyPanel._build_personalized_feedback
    )
    assert "I–V Curve에서 확인" in personalized_source
    assert "Field Map에서 확인" in personalized_source
    assert "다시 확인할 근거" in personalized_source
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


def test_case_study_cover_pairs_completed_result_with_new_session_action() -> None:
    init_source = inspect.getsource(CaseStudyPanel.__init__)
    render_source = inspect.getsource(CaseStudyPanel.render)
    cover_source = inspect.getsource(CaseStudyPanel._build_cover)
    assert "self.show_cover = True" in init_source
    assert "if self.show_cover" in render_source
    assert "Case Study Learning Lab" in cover_source
    assert "내 학습 현황" in cover_source
    assert "이어서 하기" in cover_source
    assert "결과 보기" in cover_source
    assert 'text="새 세션 시작"' in cover_source
    assert "latest.current_step is LearningStep.SESSION_COMPLETE" in cover_source
    assert "Case 살펴보기" in cover_source
    assert "portfolio.recommendation_reason" not in cover_source
    assert "추천 Case 복습" not in cover_source
    assert "새로 시작" not in cover_source
    assert "portfolio_button" not in init_source


def test_case_study_cover_scrolls_through_eight_case_slots() -> None:
    cover_source = inspect.getsource(CaseStudyPanel._build_cover)
    wheel_source = inspect.getsource(CaseStudyPanel._bind_cover_mousewheel)
    assert PLANNED_CASES == ()
    assert len(load_topics()) + len(PLANNED_CASES) == 8
    assert "tk.Canvas(" in cover_source
    assert "ttk.Scrollbar(" in cover_source
    assert "scrollregion=canvas.bbox" in cover_source
    assert "PLANNED_CASES" in cover_source
    assert 'text="준비 중"' in cover_source
    assert "state=tk.DISABLED" in cover_source
    assert '"<MouseWheel>"' in wheel_source
    assert 'canvas.yview_scroll(units, "units")' in wheel_source


def test_case_study_cover_expands_grouped_learning_records_inline() -> None:
    init_source = inspect.getsource(CaseStudyPanel.__init__)
    cover_source = inspect.getsource(CaseStudyPanel._build_cover)
    toggle_source = inspect.getsource(CaseStudyPanel._toggle_cover_records)
    topic_toggle_source = inspect.getsource(
        CaseStudyPanel._toggle_cover_record_topic
    )
    assert "self.show_cover_records = False" in init_source
    assert "self.expanded_cover_record_topics" in init_source
    assert "학습 기록 {record_count}개 보기" in cover_source
    assert "학습 기록 {record_count}개 접기" in cover_source
    assert "sessions_by_topic" in cover_source
    assert "session.display_name" in cover_source
    assert "topic_expanded" in cover_source
    assert "Case {topic_index:02d}" in cover_source
    assert "len(topic_sessions)}개 보기" in cover_source
    assert "len(topic_sessions)}개 접기" in cover_source
    assert '"결과 보기"' in cover_source
    assert '"이어서 하기"' in cover_source
    assert "_delete_selected_session" not in cover_source
    assert "_rename_selected_session" not in cover_source
    assert "self.show_cover_records = not self.show_cover_records" in toggle_source
    assert "self.expanded_cover_record_topics.add(topic_id)" in topic_toggle_source
    assert "self.expanded_cover_record_topics.remove(topic_id)" in topic_toggle_source


def test_cover_hides_case_learning_chrome_until_a_case_is_opened() -> None:
    chrome_source = inspect.getsource(CaseStudyPanel._set_cover_chrome)
    assert "self.case_header.pack_forget()" in chrome_source
    assert "self.session_bar.pack_forget()" in chrome_source
    assert "self.learning_flow.pack_forget()" in chrome_source
    assert "self.case_header.pack(fill=tk.X, before=self.body)" in chrome_source
    assert "self.learning_flow.pack(fill=tk.X, before=self.body)" in chrome_source


def test_open_case_header_prioritizes_identity_and_collapses_record_management() -> None:
    init_source = inspect.getsource(CaseStudyPanel.__init__)
    refresh_source = inspect.getsource(CaseStudyPanel._refresh_session_controls)
    manager_source = inspect.getsource(CaseStudyPanel._sync_session_manager_visibility)
    assert 'text="← Case 목록"' in init_source
    assert 'text="학습 기록 ▼"' in init_source
    assert 'text="불러오기"' in init_source
    assert 'text="이름 변경"' in init_source
    assert 'text="선택 기록 삭제"' in init_source
    assert 'text="새 학습 시작"' in init_source
    assert 'text="현재 학습 초기화"' in init_source
    assert 'text="복제"' not in init_source
    assert 'text="기타 관리 ▼"' not in init_source
    assert "self.session_bar.pack(" not in init_source
    assert "self.current_session_var.set" in refresh_source
    assert "self.show_session_manager and not self.show_cover" in manager_source
    assert "session_current.pack(side=tk.RIGHT)" in init_source
    assert init_source.index('text="현재 학습"') < init_source.index(
        'text="새 학습 시작"'
    ) < init_source.index('text="현재 학습 초기화"')


def test_cover_navigation_preserves_sessions_and_enters_selected_case() -> None:
    open_source = inspect.getsource(CaseStudyPanel._open_case_session)
    start_source = inspect.getsource(CaseStudyPanel._start_new_case)
    show_source = inspect.getsource(CaseStudyPanel._show_cover)
    assert "self.repository.load(session_id)" in open_source
    assert "self.show_cover = False" in open_source
    assert "LearningSession.create(self.topic)" in start_source
    assert "self._save()" in start_source
    assert "self.show_cover = True" in show_source
