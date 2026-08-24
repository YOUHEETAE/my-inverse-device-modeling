from __future__ import annotations

import math
import re
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any, Callable

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from ai.shared.field_data import FIELD_DISPLAYS
from backend.answer_contract import evidence_display_label
from backend.public_presentation import (
    public_failure_label,
    public_source_label,
)
# 학습 콘텐츠와 조건 표기는 backend/learning/case_presentation.py로 옮겼다.
# 웹도 같은 문구를 써야 해서 두 앱이 공유하는 자리로 내렸다. 여기서 다시
# 내보내므로 이 모듈을 통해 쓰던 코드와 테스트는 그대로 동작한다.
from backend.learning.case_presentation import (  # noqa: F401
    CASE_CORE_SUMMARIES,
    CASE_UNDERSTANDING_GUIDES,
    CONCEPT_FEEDBACK_LABELS,
    MODEL_ANSWER_SECTION_TITLES,
    QUESTION_REVIEW_GUIDES,
    CONDITION_LABELS,
    CONDITION_UNITS,
    format_case_comparison,
)
from backend.learning import (
    LearningAnalysisContext,
    LearningLLMService,
    LearningPortfolio,
    LearningSession,
    LearningStateMachine,
    LearningStep,
    audit_learning_session,
    apply_observation_review,
    build_learning_portfolio,
    load_topics,
    review_observations,
)
from backend.learning.experiment_runner import LearningExperimentResult, LearningExperimentRunner
from backend.learning.model_answer import build_grounded_model_answer
from backend.learning.session_repository import LearningSessionRepository, SessionStorageError
from frontend.visualization.curve_rendering import render_curve_figure
from frontend.visualization.field_rendering import render_model_field_comparison


STEP_ORDER = (
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
)
STEP_LABELS = {
    LearningStep.INTRODUCTION: "학습 소개",
    LearningStep.BASELINE_SETUP: "비교 조건",
    LearningStep.PREDICTION_QUESTION: "사전 예측",
    LearningStep.PREDICTION_SUBMITTED: "예측 제출",
    LearningStep.SIMULATION_RUNNING: "모델 실행",
    LearningStep.RESULT_READY: "결과 관찰",
    LearningStep.OBSERVATION_QUESTION: "관찰 질문",
    LearningStep.OBSERVATION_SUBMITTED: "답변 평가",
    LearningStep.FEEDBACK_READY: "맞춤 피드백",
    LearningStep.NEXT_EXPERIMENT: "다음 행동",
    LearningStep.SESSION_COMPLETE: "학습 완료",
    LearningStep.ERROR: "오류 복구",
}
LEARNING_PAGE_ORDER = (
    "understanding",
    "prediction",
    "observation",
    "explanation",
)
LEARNING_PAGE_LABELS = {
    "understanding": "1. Case 이해",
    "prediction": "2. 초기 예측",
    "observation": "3. 결과 관찰",
    "explanation": "4. 최종 설명",
}
QUESTION_TYPE_LABELS = {
    "current_result": "현재 결과",
    "case_theory": "Case 이론",
    "adjacent_theory": "인접 반도체 이론",
    "hypothetical": "가상 조건",
    "new_experiment": "새 실험",
    "out_of_scope": "학습 범위 밖",
    # Backward-compatible labels for sessions saved before Tutor Core v2.
    "general_theory": "일반 이론",
    "unsupported": "근거 부족",
}
RELEVANCE_LABELS = {
    "direct": "직접 관련",
    "related": "관련",
    "domain_adjacent": "간접 관련",
    "unrelated": "관련 없음",
}
FALLBACK_LABELS = {
    "external_timeout": "AI 응답 시간 초과",
    "external_validation_failed": "AI 응답 확인 실패",
    "external_request_failed": "AI 요청 실패",
    "external_response_unavailable": "AI 응답 사용 불가",
    "external_network_error": "AI 서비스 연결 실패",
    "external_provider_error": "AI 서비스 오류",
    "external_http_400": "AI 요청 처리 실패",
    "external_http_401": "AI 서비스 인증 실패",
    "external_http_403": "AI 서비스 접근 권한 없음",
    "external_http_404": "AI 서비스 설정 오류",
    "external_http_413": "AI 요청 정보 과다",
    "external_http_422": "AI 요청 처리 실패",
    "external_http_429": "AI 요청 한도 초과",
    "external_http_500": "AI 서비스 일시 오류",
    "external_http_502": "AI 서비스 일시 오류",
    "external_http_503": "AI 서비스 일시 오류",
    "external_http_504": "AI 서비스 응답 시간 초과",
}
FOLLOWUP_EXAMPLES = (
    ("현재 결과", "이번 결과에서 Vth가 왜 감소했나요?"),
    ("후속 원리", "그 변화가 생기는 물리적 이유는 무엇인가요?"),
    ("인접 이론", "PN 접합이 무엇이며 공핍영역은 어떻게 형성되나요?"),
    ("가상 조건", "Body doping을 높이면 DIBL은 어떻게 달라질까요?"),
)
ERROR_GUIDANCE = {
    "learning_feedback_failed": (
        "저장된 관찰 답변과 분석 결과로 피드백 생성을 다시 시도합니다."
    ),
    "simulation_failed": (
        "저장된 예측 답변을 유지한 채 현재 Case 실험을 다시 실행합니다."
    ),
}
METRIC_LABELS = {
    "vth": "Vth",
    "vth_low": "Vth (low Vd)",
    "vth_high": "Vth (high Vd)",
    "dibl": "DIBL",
    "ss": "SS",
    "ion": "Ion",
    "ioff": "Ioff",
    "ron": "Ron",
    "gm": "gm",
    "gm_max": "gm max",
    "gds": "gds",
    "lambda_clm": "λ (CLM)",
    "ion_ioff_ratio": "Ion/Ioff ratio",
    "ratio": "Ion/Ioff ratio",
}
METRIC_TABLE_SPECS = (
    ("vth_low", "vth_low_v", "V", 1.0),
    ("vth_high", "vth_high_v", "V", 1.0),
    ("ion", "ion_ma_per_um", "mA/µm", 1.0),
    ("ioff", "ioff_ma_per_um", "mA/µm", 1.0),
    ("ion_ioff_ratio", "ion_ioff_ratio", "", 1.0),
    ("ss", "ss_mv_per_dec", "mV/dec", 1.0),
    ("dibl", "dibl_gm_v_per_v", "mV/V", 1000.0),
    ("gm_max", "gm_max_ms_per_um", "mS/µm", 1.0),
    ("gds", "gds_ms_per_um", "mS/µm", 1.0),
    ("ron", "ron_kohm_um", "kΩ·µm", 1.0),
    ("lambda_clm", "lambda_per_v", "1/V", 1.0),
)
COMPACT_PARAMETER_PANEL_WIDTH = 360
OBSERVATION_PANEL_WIDTH = 560

PLANNED_CASES = ()


def format_error_guidance(error_code: str | None, recovery_step: LearningStep | None) -> str:
    code = error_code or "unknown"
    if code.startswith("learning_experiment_failed:"):
        detail = (
            "모델 실행 또는 결과 분석 단계가 완료되지 않았습니다. "
            "저장된 예측 답변을 유지한 채 실험을 다시 실행합니다."
        )
    else:
        detail = ERROR_GUIDANCE.get(
            code,
            "저장된 마지막 안전 단계로 돌아가 다시 시도합니다.",
        )
    recovery = STEP_LABELS.get(recovery_step, recovery_step.value) if recovery_step else "확인 불가"
    return f"{detail}\n재시도 단계: {recovery}\n기존 세션 기록은 삭제되지 않습니다."


def topic_condition_rows(
    topic: Any,
) -> tuple[tuple[str, dict[str, float]], ...]:
    return (
        *(
            (reference.label, reference.conditions)
            for reference in getattr(topic, "reference_conditions", ())
        ),
        (topic.baseline_label, topic.baseline_conditions),
        (topic.comparison_label, topic.comparison_conditions),
    )


def _format_compact_condition_value(value: float) -> str:
    if value != 0 and abs(value) >= 1e4:
        return f"{value:.3g}".replace("e+", "e")
    return f"{value:g}"


def format_curve_condition_label(
    topic: Any,
    label: str,
    conditions: dict[str, float],
) -> str:
    parameters = topic.display_parameters or tuple(conditions)
    signature = " ".join(
        f"{name}{_format_compact_condition_value(conditions[name])}"
        for name in parameters
    )
    if topic.comparison_design == "candidate_set":
        return f"{label} | {signature}"
    return signature


def format_condition_details(
    conditions: dict[str, float],
    parameters: tuple[str, ...],
) -> str:
    return " · ".join(
        (
            f"{name} {_format_compact_condition_value(conditions[name])}"
            f" {CONDITION_UNITS.get(name, '')}"
        ).rstrip()
        for name in parameters
    )


def split_model_answer_sections(text: str) -> tuple[tuple[str, str], ...]:
    """Split the canonical bracketed model answer into visible UI sections."""

    value = str(text or "").strip()
    if not value:
        return ()
    matches = tuple(re.finditer(r"^\[([^\]]+)\]\s*$", value, flags=re.MULTILINE))
    if not matches:
        return (("모범 답안", value),)
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(value)
        body = value[start:end].strip()
        if body:
            raw_title = match.group(1).strip()
            sections.append(
                (MODEL_ANSWER_SECTION_TITLES.get(raw_title, raw_title), body)
            )
    return tuple(sections)


def format_followup_metadata(turn: Any) -> tuple[str, str]:
    source = getattr(turn, "source", "local")
    fallback = getattr(turn, "fallback_reason", None)
    engine = public_source_label(source, has_fallback=bool(fallback))
    question_type = getattr(turn, "question_type", "")
    labels = [
        engine,
        QUESTION_TYPE_LABELS.get(question_type, question_type or "분류 없음"),
    ]
    if question_type != "current_result":
        labels.append(
            RELEVANCE_LABELS.get(
                getattr(turn, "relevance_to_case", "related"),
                getattr(turn, "relevance_to_case", "related"),
            )
        )
    if getattr(turn, "needs_new_experiment", False):
        labels.append("추가 실험 필요")
    if getattr(turn, "needs_clarification", False):
        labels.append("의미 확인 필요")
    learning_move = str(
        getattr(turn, "learning_move", "answer_question")
        or "answer_question"
    )
    move_labels = {
        "evaluate_claim": "학습자 주장 검토",
        "acknowledge_correction": "정정 반영",
        "confirm_experiment": "실험 조건 확인",
    }
    if learning_move in move_labels:
        labels.append(move_labels[learning_move])
    details = []
    evidence = tuple(getattr(turn, "evidence_ids", ()) or ())
    theory = tuple(getattr(turn, "theory_concepts", ()) or ())
    if evidence:
        details.append(
            "근거: "
            + ", ".join(evidence_display_label(item) for item in evidence)
        )
    if theory:
        details.append(
            "연결 개념: "
            + ", ".join(
                str(item).replace("_", " ")
                for item in theory
            )
        )
    if fallback:
        prefix = "오류" if source == "external_error" else "보조 해설"
        details.append(
            prefix + ": " + FALLBACK_LABELS.get(fallback, fallback)
        )
    diagnostics = tuple(
        item
        for item in (
            getattr(turn, "pipeline_diagnostics", ()) or ()
        )
        if isinstance(item, dict)
    )
    for diagnostic in reversed(diagnostics):
        recommended_wait = diagnostic.get(
            "recommended_retry_after_seconds"
        )
        if isinstance(recommended_wait, int):
            details.append(f"다시 시도: {recommended_wait}초 후")
            break
    assessment = str(
        getattr(turn, "claim_assessment", "not_applicable")
        or "not_applicable"
    )
    assessment_labels = {
        "supported": "근거와 일치",
        "partially_supported": "일부 일치",
        "contradicted": "근거와 불일치",
        "unverified": "추가 확인 필요",
    }
    if assessment in assessment_labels:
        details.append("주장 피드백: " + assessment_labels[assessment])
    return " · ".join(labels), " | ".join(details)


class CaseStudyPanel(ttk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        window: tk.Tk,
        runner: LearningExperimentRunner,
        repository: LearningSessionRepository,
        provider: Any | None = None,
        on_open_theory: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.window = window
        self.runner = runner
        self.repository = repository
        self.on_open_theory = on_open_theory
        self.topics = load_topics()
        if not self.topics:
            raise RuntimeError("no_learning_topics")
        initial_topic_id = (
            "sce_channel_length"
            if "sce_channel_length" in self.topics
            else next(iter(self.topics))
        )
        try:
            latest = next(
                (
                    item for item in self.repository.list_sessions()
                    if item.topic_id in self.topics
                ),
                None,
            )
        except SessionStorageError:
            latest = None
        if latest is not None and latest.topic_id:
            initial_topic_id = latest.topic_id
        self.topic = self.topics[initial_topic_id]
        self.state_machine = LearningStateMachine()
        self._provider_name = getattr(provider, "name", "")
        self.llm_service = LearningLLMService(
            provider if self._provider_name == "external_llm" else None
        )
        self.result: LearningExperimentResult | None = None
        self.context: LearningAnalysisContext | None = None
        self.feedback_data: dict[str, Any] = {}
        self.summary_data: dict[str, Any] = {}
        self.answer_collectors: dict[str, Callable[[], Any]] = {}
        self._answer_drafts: dict[str, dict[str, dict[str, Any]]] = {}
        self._collectors_session_id: str | None = None
        self._review_variables: list[tk.Variable] = []
        self._busy = False
        self._plot_canvases: list[FigureCanvasTkAgg] = []
        self.field_display_var = tk.StringVar(value="Potential")
        self.result_view_tab = "I–V Curve"
        self.completion_view_tab = "학습 요약"
        self.status_var = tk.StringVar(value="")
        self.tutor_mode_var = tk.StringVar(value="")
        self.session_choice_var = tk.StringVar(value="")
        self.session_meta_var = tk.StringVar(value="")
        self.current_session_var = tk.StringVar(value="")
        self.topic_choice_var = tk.StringVar(value="")
        self.topic_title_var = tk.StringVar(value=self._case_heading())
        self.portfolio_var = tk.StringVar(value="")
        self._topic_choice_ids = {
            f"{topic.title} · {topic.topic_id}": topic_id
            for topic_id, topic in self.topics.items()
        }
        self._session_choice_ids: dict[str, str] = {}
        self.show_cover = True
        self.show_cover_records = False
        self.show_session_manager = False
        self.expanded_cover_record_topics: set[str] = set()
        self.learning_view: str | None = None
        self._update_tutor_mode()

        self.session = self._restore_or_create_session()
        self._restore_session_snapshots()

        self.case_header = ttk.Frame(self, padding=(12, 9, 12, 7))
        self.case_header.pack(fill=tk.X)
        self.cover_button = ttk.Button(
            self.case_header,
            text="← Case 목록",
            command=self._show_cover,
        )
        self.cover_button.pack(side=tk.LEFT, padx=(0, 10))
        self.topic_title_label = ttk.Label(
            self.case_header,
            textvariable=self.topic_title_var,
            font=("TkDefaultFont", 12, "bold"),
        )
        self.topic_title_label.pack(side=tk.LEFT)
        self.learning_records_button = ttk.Button(
            self.case_header,
            text="학습 기록 ▼",
            command=self._toggle_session_manager,
        )
        self.learning_records_button.pack(side=tk.RIGHT)
        ttk.Label(
            self.case_header,
            textvariable=self.current_session_var,
            foreground="#4b5563",
        ).pack(side=tk.RIGHT, padx=(10, 8))

        self.session_bar = ttk.LabelFrame(
            self,
            text="학습 기록 관리",
            padding=(10, 8),
        )
        session_primary = ttk.Frame(self.session_bar)
        session_primary.pack(fill=tk.X)
        ttk.Label(session_primary, text="저장 기록").pack(side=tk.LEFT)
        self.session_choice_box = ttk.Combobox(
            session_primary,
            textvariable=self.session_choice_var,
            state="readonly",
            width=44,
        )
        self.session_choice_box.pack(side=tk.LEFT, padx=(5, 4))
        self.resume_session_button = ttk.Button(
            session_primary,
            text="불러오기",
            command=self._resume_selected_session,
        )
        self.resume_session_button.pack(side=tk.LEFT, padx=2)
        self.rename_session_button = ttk.Button(
            session_primary,
            text="이름 변경",
            command=self._rename_selected_session,
        )
        self.rename_session_button.pack(side=tk.LEFT, padx=2)
        self.delete_session_button = ttk.Button(
            session_primary,
            text="선택 기록 삭제",
            command=self._delete_selected_session,
        )
        self.delete_session_button.pack(side=tk.LEFT, padx=(2, 0))

        session_current = ttk.Frame(session_primary)
        session_current.pack(side=tk.RIGHT)
        ttk.Label(session_current, text="현재 학습").pack(side=tk.LEFT)
        self.new_session_button = ttk.Button(
            session_current,
            text="새 학습 시작",
            command=self._new_session,
        )
        self.new_session_button.pack(side=tk.LEFT, padx=(7, 2))
        self.reset_session_button = ttk.Button(
            session_current,
            text="현재 학습 초기화",
            command=self._reset_current_session,
        )
        self.reset_session_button.pack(side=tk.LEFT, padx=2)
        ttk.Label(
            session_current,
            textvariable=self.session_meta_var,
            foreground="#4b5563",
        ).pack(side=tk.LEFT, padx=(8, 0))
        self._refresh_session_controls()

        self.learning_flow = ttk.Frame(self, padding=(12, 3, 12, 0))
        self.learning_flow.pack(fill=tk.X)
        nav_style = ttk.Style(self)
        nav_style.configure(
            "LearningActive.TButton",
            foreground="#1d4ed8",
            font=("TkDefaultFont", 9, "bold"),
        )
        nav_style.configure("CaseMetric.Treeview", rowheight=24)
        self.learning_nav_buttons: dict[str, ttk.Button] = {}
        self.learning_progress_segments: dict[str, tk.Frame] = {}
        for page in LEARNING_PAGE_ORDER:
            cell = ttk.Frame(self.learning_flow)
            cell.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
            segment = tk.Frame(
                cell,
                height=4,
                background="#d1d5db",
                borderwidth=0,
            )
            segment.pack(fill=tk.X, pady=(0, 4))
            segment.pack_propagate(False)
            button = ttk.Button(
                cell,
                command=lambda selected=page: self._show_learning_page(selected),
            )
            button.pack(fill=tk.X)
            self.learning_nav_buttons[page] = button
            self.learning_progress_segments[page] = segment
        self.status_label = ttk.Label(
            self,
            textvariable=self.status_var,
            foreground="#4b5563",
            padding=(12, 4, 12, 0),
        )
        self.body = ttk.Frame(self, padding=12)
        self.body.pack(fill=tk.BOTH, expand=True)
        self.render()

    def set_provider(self, provider: Any) -> None:
        self._provider_name = getattr(provider, "name", "")
        self.llm_service = LearningLLMService(
            provider if self._provider_name == "external_llm" else None
        )
        self._update_tutor_mode()
        self.status_var.set(f"학습 튜터: {self.tutor_mode_var.get()}")

    def _update_tutor_mode(self) -> None:
        mode = (
            "Case Study AI 튜터 사용 가능"
            if self._provider_name == "external_llm"
            else "Case Study AI 미연결 · 로컬 보조 해설"
        )
        self.tutor_mode_var.set(mode)

    def _restore_session_snapshots(self) -> None:
        self.learning_view = None
        self.result = None
        self.context = None
        if self.session.analysis_snapshot:
            try:
                self.context = LearningAnalysisContext.from_dict(
                    self.session.analysis_snapshot
                )
            except (TypeError, ValueError):
                self.context = None
        self.feedback_data = dict(self.session.feedback_snapshot)
        self.summary_data = dict(self.session.summary_snapshot)
        state = dict(self.session.ui_state)
        self.result_view_tab = state.get("result_view_tab", "I–V Curve")
        saved_completion_tab = state.get("completion_view_tab", "학습 요약")
        if saved_completion_tab == "AI 자유 질문":
            self.completion_view_tab = "AI 자유 질문"
            self.result_view_tab = "AI 자유 질문"
        elif saved_completion_tab in {"결과", "결과 다시 보기"}:
            self.completion_view_tab = self.result_view_tab
        else:
            self.completion_view_tab = saved_completion_tab
        self.field_display_var.set(
            state.get("field_display", "Potential")
        )

    def _topic_label(self, topic_id: str) -> str:
        return next(
            (
                label for label, value in self._topic_choice_ids.items()
                if value == topic_id
            ),
            topic_id,
        )

    def _case_heading(self) -> str:
        order = max(1, int(getattr(self.topic, "catalog_order", 1)))
        return f"Case {order:02d} · {self.topic.title}"

    def _current_session_header_text(self) -> str:
        if self.session.current_step is LearningStep.SESSION_COMPLETE:
            status = "완료"
        elif self.session.current_step is LearningStep.INTRODUCTION:
            status = "시작 전"
        else:
            status = "진행 중"
        name = str(self.session.display_name or "학습 기록")
        if len(name) > 28:
            name = name[:27] + "…"
        return f"현재 기록 · {name} · {status}"

    def _switch_topic(self, _event=None) -> None:
        if self._busy:
            self.topic_choice_var.set(self._topic_label(self.topic.topic_id))
            return
        topic_id = self._topic_choice_ids.get(self.topic_choice_var.get())
        if not topic_id or topic_id == self.topic.topic_id:
            return
        self.topic = self.topics[topic_id]
        self.topic_title_var.set(self._case_heading())
        self.session = self._restore_or_create_session()
        self._restore_session_snapshots()
        self.status_var.set(
            f"‘{self.topic.title}’ Case로 전환했습니다. Case별 세션은 분리 저장됩니다."
        )
        self._refresh_session_controls()
        self.render()

    @staticmethod
    def _session_label(session: LearningSession) -> str:
        updated = session.updated_at.replace("T", " ")[:16]
        step = STEP_LABELS.get(session.current_step, session.current_step.value)
        return (
            f"{session.display_name} · {updated} · {step} · "
            f"{session.session_id[:8]}"
        )

    def _session_matches_current_topic(
        self, session: LearningSession
    ) -> bool:
        return self._session_matches_topic(session, self.topic)

    @staticmethod
    def _session_matches_topic(
        session: LearningSession,
        topic: Any,
    ) -> bool:
        return (
            session.topic_id == topic.topic_id
            and session.baseline_conditions == topic.baseline_conditions
            and session.comparison_conditions == topic.comparison_conditions
        )

    def _refresh_session_controls(self) -> None:
        if not hasattr(self, "session_choice_box"):
            return
        try:
            sessions = [
                item
                for item in self.repository.list_sessions()
                if self._session_matches_current_topic(item)
            ]
        except SessionStorageError:
            sessions = [self.session]
        notices = self.repository.consume_recovery_notices()
        if notices:
            recovered = sum(
                item.get("code") == "session_recovered_from_backup"
                for item in notices
            )
            skipped = sum(
                item.get("code") == "session_skipped_unrecoverable"
                for item in notices
            )
            if recovered:
                self.status_var.set(
                    f"손상된 세션 {recovered}개를 마지막 백업에서 복구했습니다."
                )
            elif skipped:
                self.status_var.set(
                    f"복구할 수 없는 세션 {skipped}개를 목록에서 제외했습니다."
                )
        if not any(item.session_id == self.session.session_id for item in sessions):
            sessions.insert(0, self.session)
        self._session_choice_ids = {
            self._session_label(item): item.session_id for item in sessions
        }
        labels = tuple(self._session_choice_ids)
        self.session_choice_box.configure(values=labels)
        current = next(
            (
                label
                for label, session_id in self._session_choice_ids.items()
                if session_id == self.session.session_id
            ),
            labels[0] if labels else "",
        )
        self.session_choice_var.set(current)
        self.session_meta_var.set(
            f"자동 저장 · {self.session.updated_at.replace('T', ' ')[:16]}"
        )
        self.current_session_var.set(self._current_session_header_text())
        self._refresh_portfolio_summary()
        self._refresh_status_visibility()

    def _toggle_session_manager(self) -> None:
        if self._busy or self.show_cover:
            return
        self.show_session_manager = not self.show_session_manager
        self._sync_session_manager_visibility()

    def _sync_session_manager_visibility(self) -> None:
        expanded = self.show_session_manager and not self.show_cover
        self.learning_records_button.configure(
            text="학습 기록 ▲" if expanded else "학습 기록 ▼"
        )
        if expanded:
            if not self.session_bar.winfo_manager():
                self.session_bar.pack(
                    fill=tk.X,
                    padx=12,
                    pady=(0, 6),
                    before=self.learning_flow,
                )
        else:
            self.session_bar.pack_forget()

    def _learning_portfolio(self) -> LearningPortfolio:
        try:
            sessions = self.repository.list_sessions()
        except SessionStorageError:
            sessions = [self.session]
        return build_learning_portfolio(self.topics, sessions)

    def _refresh_portfolio_summary(self) -> None:
        portfolio = self._learning_portfolio()
        self.portfolio_var.set(
            f"전체 Case {portfolio.completed_case_count}/"
            f"{portfolio.total_case_count} 완료"
        )

    def _show_learning_portfolio(self) -> None:
        if self._busy:
            return
        portfolio = self._learning_portfolio()
        dialog = tk.Toplevel(self.window)
        dialog.title("전체 Case 학습 현황")
        dialog.transient(self.window)
        dialog.geometry("920x430")
        outer = ttk.Frame(dialog, padding=14)
        outer.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            outer,
            text=(
                f"전체 Case {portfolio.completed_case_count}/"
                f"{portfolio.total_case_count} 완료"
            ),
            font=("TkDefaultFont", 12, "bold"),
        ).pack(anchor="w")
        columns = ("case", "status", "sessions", "concepts", "updated")
        tree = ttk.Treeview(
            outer, columns=columns, show="headings", height=8
        )
        headings = {
            "case": ("Case", 330),
            "status": ("상태", 100),
            "sessions": ("세션", 70),
            "concepts": ("개념 진도", 120),
            "updated": ("최근 학습", 180),
        }
        for name, (title, width) in headings.items():
            tree.heading(name, text=title)
            tree.column(name, width=width, anchor=tk.CENTER)
        status_labels = {
            "completed": "완료",
            "in_progress": "진행 중",
            "not_started": "시작 전",
            "locked": "선행 학습 필요",
        }
        for item in portfolio.cases:
            tree.insert(
                "",
                tk.END,
                iid=item.topic_id,
                values=(
                    item.title,
                    status_labels.get(item.status, item.status),
                    item.session_count,
                    f"{len(item.completed_concepts)}/"
                    f"{len(item.completed_concepts) + len(item.remaining_concepts)}",
                    (
                        item.updated_at.replace("T", " ")[:16]
                        if item.updated_at
                        else "-"
                    ),
                ),
            )
        tree.pack(fill=tk.BOTH, expand=True, pady=(10, 8))
        ttk.Label(
            outer,
            text="추천: " + portfolio.recommendation_reason,
            foreground="#1d4ed8",
            wraplength=860,
            justify=tk.LEFT,
        ).pack(anchor="w")
        if portfolio.archived_incompatible_session_count:
            ttk.Label(
                outer,
                text=(
                    "현재 Case 조건과 다른 이전 세션 "
                    f"{portfolio.archived_incompatible_session_count}개는 "
                    "진도 계산에서 분리했습니다."
                ),
                foreground="#92400e",
            ).pack(anchor="w", pady=(4, 0))
        actions = ttk.Frame(outer)
        actions.pack(fill=tk.X, pady=(10, 0))

        def open_recommended() -> None:
            topic_id = portfolio.next_topic_id
            if topic_id:
                self.topic_choice_var.set(self._topic_label(topic_id))
                dialog.destroy()
                self._switch_topic()

        ttk.Button(
            actions,
            text="추천 Case 열기",
            command=open_recommended,
            state=(
                tk.NORMAL if portfolio.next_topic_id else tk.DISABLED
            ),
        ).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(
            actions, text="닫기", command=dialog.destroy
        ).pack(side=tk.RIGHT)

    def _resume_selected_session(self) -> None:
        if self._busy:
            return
        session_id = self._session_choice_ids.get(self.session_choice_var.get())
        if not session_id:
            return
        try:
            session = self.repository.load(session_id)
        except SessionStorageError:
            session = None
        if session is None:
            messagebox.showerror(
                "세션 불러오기 실패",
                "선택한 학습 세션을 불러올 수 없습니다.",
                parent=self.window,
            )
            return
        self.session = session
        self._restore_session_snapshots()
        self.show_cover = False
        self.status_var.set("저장된 학습 세션을 불러왔습니다.")
        self._refresh_session_controls()
        self.render()

    def _set_session_controls_enabled(self, enabled: bool) -> None:
        if not hasattr(self, "session_choice_box"):
            return
        self.session_choice_box.configure(
            state="readonly" if enabled else tk.DISABLED
        )
        state = tk.NORMAL if enabled else tk.DISABLED
        self.learning_records_button.configure(state=state)
        for button in (
            self.resume_session_button,
            self.new_session_button,
            self.reset_session_button,
            self.delete_session_button,
            self.rename_session_button,
        ):
            button.configure(state=state)

    def _rename_selected_session(self) -> None:
        if self._busy:
            return
        session_id = self._session_choice_ids.get(
            self.session_choice_var.get()
        )
        if not session_id:
            return
        try:
            target = self.repository.load(session_id)
        except SessionStorageError:
            target = None
        if target is None:
            messagebox.showerror(
                "세션 이름 변경 실패",
                "선택한 세션을 불러올 수 없습니다.",
                parent=self.window,
            )
            return
        value = simpledialog.askstring(
            "세션 이름 변경",
            "새 세션 이름을 입력하세요.",
            initialvalue=target.display_name,
            parent=self.window,
        )
        if value is None:
            return
        try:
            target.rename(value)
            self.repository.save(target)
        except (ValueError, SessionStorageError):
            messagebox.showerror(
                "세션 이름 변경 실패",
                "세션 이름은 1~60자의 텍스트여야 합니다.",
                parent=self.window,
            )
            return
        if target.session_id == self.session.session_id:
            self.session = target
        self.status_var.set("세션 이름을 변경했습니다.")
        self._refresh_session_controls()

    def _delete_selected_session(self) -> None:
        if self._busy:
            return
        session_id = self._session_choice_ids.get(self.session_choice_var.get())
        if not session_id:
            return
        if not messagebox.askyesno(
            "저장 세션 삭제",
            "선택한 학습 세션을 영구 삭제할까요?\n이 작업은 되돌릴 수 없습니다.",
            parent=self.window,
        ):
            return
        try:
            self.repository.delete(session_id)
            remaining = [
                item
                for item in self.repository.list_sessions()
                if self._session_matches_current_topic(item)
            ]
        except SessionStorageError:
            messagebox.showerror(
                "세션 삭제 실패",
                "선택한 학습 세션을 삭제하지 못했습니다.",
                parent=self.window,
            )
            return
        self._discard_answer_draft(session_id)
        if session_id == self.session.session_id:
            if remaining:
                self.session = remaining[0]
            else:
                self.session = LearningSession.create(self.topic)
                self.repository.save(self.session)
            self._restore_session_snapshots()
        self.status_var.set("선택한 학습 세션을 삭제했습니다.")
        self._refresh_session_controls()
        self.render()

    def _reset_current_session(self) -> None:
        if self._busy:
            return
        if not messagebox.askyesno(
            "현재 세션 초기화",
            "현재 세션의 답변, 분석, 대화 기록을 지우고 처음부터 시작할까요?\n"
            "다른 세션 기록은 유지됩니다.",
            parent=self.window,
        ):
            return
        session_id = self.session.session_id
        self._discard_answer_draft(session_id)
        display_name = self.session.display_name
        ui_state = dict(self.session.ui_state)
        replacement = LearningSession.create(self.topic)
        replacement.session_id = session_id
        replacement.display_name = display_name
        replacement.ui_state = ui_state
        self.session = replacement
        self._restore_session_snapshots()
        self._save()
        self.status_var.set("현재 세션을 처음 단계로 초기화했습니다.")
        self.render()

    def _restore_or_create_session(self) -> LearningSession:
        try:
            matching = [
                item for item in self.repository.list_sessions()
                if self._session_matches_current_topic(item)
            ]
        except SessionStorageError:
            matching = []
        if matching:
            return matching[0]
        session = LearningSession.create(self.topic)
        self._save(session)
        return session

    def _save(
        self,
        session: LearningSession | None = None,
        *,
        refresh_controls: bool = True,
    ) -> None:
        try:
            self.repository.save(session or self.session)
            if refresh_controls:
                self._refresh_session_controls()
        except SessionStorageError:
            self.status_var.set("학습 기록을 저장하지 못했습니다. 현재 실행에서는 계속 진행할 수 있습니다.")

    def _clear_body(self) -> None:
        self.answer_collectors.clear()
        self._collectors_session_id = None
        self._review_variables.clear()
        self._plot_canvases.clear()
        for widget in self.body.winfo_children():
            widget.destroy()

    def _set_cover_chrome(self, cover: bool) -> None:
        if cover:
            self.case_header.pack_forget()
            self.session_bar.pack_forget()
            self.status_label.pack_forget()
            self.learning_flow.pack_forget()
            return
        if not self.case_header.winfo_manager():
            self.case_header.pack(fill=tk.X, before=self.body)
        if not self.learning_flow.winfo_manager():
            self.learning_flow.pack(fill=tk.X, before=self.body)
        self._sync_session_manager_visibility()
        self._refresh_status_visibility()

    def _refresh_status_visibility(self) -> None:
        if not hasattr(self, "status_label"):
            return
        visible = bool(self.status_var.get().strip()) and not self.show_cover
        if visible:
            if not self.status_label.winfo_manager():
                self.status_label.pack(fill=tk.X, before=self.body)
        else:
            self.status_label.pack_forget()

    def _default_learning_page(self) -> str:
        step = self.session.current_step
        if step is LearningStep.ERROR:
            step = self.session.recovery_step or LearningStep.INTRODUCTION
        if step in {LearningStep.INTRODUCTION, LearningStep.BASELINE_SETUP}:
            return "understanding"
        if step in {
            LearningStep.PREDICTION_QUESTION,
            LearningStep.PREDICTION_SUBMITTED,
            LearningStep.SIMULATION_RUNNING,
        }:
            return "prediction"
        if step in {
            LearningStep.RESULT_READY,
            LearningStep.OBSERVATION_QUESTION,
            LearningStep.OBSERVATION_SUBMITTED,
        }:
            return "observation"
        return "explanation"

    def _is_learning_page_unlocked(self, page: str) -> bool:
        step = self.session.current_step
        if step is LearningStep.ERROR:
            step = self.session.recovery_step or LearningStep.INTRODUCTION
        if page == "understanding":
            return True
        if page == "prediction":
            return bool(self.session.prediction_answers) or step not in {
                LearningStep.INTRODUCTION,
                LearningStep.BASELINE_SETUP,
            }
        if page == "observation":
            return bool(self.session.analysis_snapshot) or step in {
                LearningStep.RESULT_READY,
                LearningStep.OBSERVATION_QUESTION,
                LearningStep.OBSERVATION_SUBMITTED,
                LearningStep.FEEDBACK_READY,
                LearningStep.NEXT_EXPERIMENT,
                LearningStep.SESSION_COMPLETE,
            }
        if page == "explanation":
            return bool(self.session.feedback_snapshot or self.session.summary_snapshot) or step in {
                LearningStep.FEEDBACK_READY,
                LearningStep.NEXT_EXPERIMENT,
                LearningStep.SESSION_COMPLETE,
            }
        return False

    def _show_learning_page(self, page: str) -> None:
        if self._busy or not self._is_learning_page_unlocked(page):
            return
        self.learning_view = page
        self.render()

    def _capture_answer_draft(self) -> None:
        session_id = self._collectors_session_id
        if not session_id or not self.answer_collectors:
            return
        answers: dict[str, dict[str, Any]] = {}
        for question_id, collect in self.answer_collectors.items():
            try:
                value = collect()
            except tk.TclError:
                continue
            if isinstance(value, dict):
                answers[question_id] = {
                    "selected": list(value.get("selected", ())),
                    "reason": str(value.get("reason", "")),
                }
        if answers:
            self._answer_drafts[session_id] = answers

    def _discard_answer_draft(self, session_id: str | None = None) -> None:
        target = session_id or self.session.session_id
        self._answer_drafts.pop(target, None)
        if self._collectors_session_id == target:
            self.answer_collectors.clear()
            self._collectors_session_id = None

    def _draft_answer(self, question_id: str) -> dict[str, Any]:
        return dict(
            self._answer_drafts.get(self.session.session_id, {}).get(
                question_id,
                {},
            )
        )

    def _refresh_learning_navigation(self) -> None:
        current = self.learning_view or self._default_learning_page()
        if not self._is_learning_page_unlocked(current):
            current = self._default_learning_page()
        self.learning_view = current
        for page, button in self.learning_nav_buttons.items():
            unlocked = self._is_learning_page_unlocked(page)
            label = LEARNING_PAGE_LABELS[page]
            if not unlocked:
                label = f"{label} · 잠김"
            button.configure(
                text=label,
                state=(tk.NORMAL if unlocked and not self._busy else tk.DISABLED),
                style=(
                    "LearningActive.TButton"
                    if page == current
                    else "TButton"
                ),
            )
            self.learning_progress_segments[page].configure(
                background="#16a34a" if unlocked else "#d1d5db"
            )

    def _show_cover(self) -> None:
        if self._busy:
            return
        self.show_session_manager = False
        self.show_cover = True
        self.render()

    def _toggle_cover_records(self) -> None:
        if self._busy:
            return
        self.show_cover_records = not self.show_cover_records
        self.render()

    def _toggle_cover_record_topic(self, topic_id: str) -> None:
        if self._busy:
            return
        if topic_id in self.expanded_cover_record_topics:
            self.expanded_cover_record_topics.remove(topic_id)
        else:
            self.expanded_cover_record_topics.add(topic_id)
        self.render()

    def _sessions_for_topic(self, topic_id: str) -> list[LearningSession]:
        topic = self.topics[topic_id]
        try:
            sessions = [
                item
                for item in self.repository.list_sessions()
                if self._session_matches_topic(item, topic)
            ]
        except SessionStorageError:
            sessions = []
        return sorted(
            sessions,
            key=lambda item: item.updated_at,
            reverse=True,
        )

    def _activate_topic(self, topic_id: str) -> None:
        self.topic = self.topics[topic_id]
        self.topic_choice_var.set(self._topic_label(topic_id))
        self.topic_title_var.set(self._case_heading())

    def _open_case_session(self, topic_id: str, session_id: str) -> None:
        if self._busy:
            return
        try:
            session = self.repository.load(session_id)
        except SessionStorageError:
            session = None
        if session is None:
            messagebox.showerror(
                "세션 불러오기 실패",
                "선택한 Case의 최근 학습 기록을 불러올 수 없습니다.",
                parent=self.window,
            )
            return
        self._activate_topic(topic_id)
        self.session = session
        self._restore_session_snapshots()
        self.show_session_manager = False
        self.show_cover = False
        self.status_var.set("저장된 학습 세션을 이어서 엽니다.")
        self._refresh_session_controls()
        self.render()

    def _start_new_case(self, topic_id: str) -> None:
        if self._busy:
            return
        self._activate_topic(topic_id)
        self.session = LearningSession.create(self.topic)
        self._restore_session_snapshots()
        self.show_session_manager = False
        self._save()
        self.show_cover = False
        self.status_var.set(
            "새 학습 세션을 시작했습니다. 이전 기록은 그대로 유지됩니다."
        )
        self.render()

    def _open_recommended_case(self) -> None:
        portfolio = self._learning_portfolio()
        topic_id = portfolio.next_topic_id
        if not topic_id:
            return
        sessions = self._sessions_for_topic(topic_id)
        if portfolio.recommendation_kind in {"resume", "review"} and sessions:
            self._open_case_session(topic_id, sessions[0].session_id)
        else:
            self._start_new_case(topic_id)

    @staticmethod
    def _cover_step_label(step: LearningStep) -> str:
        if step is LearningStep.INTRODUCTION:
            return "시작 전"
        return STEP_LABELS.get(step, step.value)

    @staticmethod
    def _bind_cover_mousewheel(canvas: tk.Canvas, root: tk.Misc) -> None:
        def on_mousewheel(event: tk.Event) -> str:
            if getattr(event, "num", None) == 4:
                units = -1
            elif getattr(event, "num", None) == 5:
                units = 1
            else:
                units = -1 if int(getattr(event, "delta", 0)) > 0 else 1
            canvas.yview_scroll(units, "units")
            return "break"

        def bind_tree(widget: tk.Misc) -> None:
            widget.bind("<MouseWheel>", on_mousewheel, add="+")
            widget.bind("<Button-4>", on_mousewheel, add="+")
            widget.bind("<Button-5>", on_mousewheel, add="+")
            for child in widget.winfo_children():
                bind_tree(child)

        bind_tree(root)

    def _build_cover(self) -> None:
        portfolio = self._learning_portfolio()
        ordered_topics = sorted(
            self.topics.values(),
            key=lambda item: (item.catalog_order, item.topic_id),
        )
        sessions_by_topic = {
            topic.topic_id: self._sessions_for_topic(topic.topic_id)
            for topic in ordered_topics
        }
        record_count = sum(len(items) for items in sessions_by_topic.values())
        shell = ttk.Frame(self.body)
        shell.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(
            shell,
            highlightthickness=0,
            borderwidth=0,
            yscrollincrement=16,
        )
        scrollbar = ttk.Scrollbar(
            shell,
            orient=tk.VERTICAL,
            command=canvas.yview,
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        content = ttk.Frame(canvas)
        content_window = canvas.create_window(
            (0, 0), window=content, anchor="nw"
        )
        content.bind(
            "<Configure>",
            lambda _event: canvas.configure(
                scrollregion=canvas.bbox("all")
            ),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(
                content_window, width=event.width
            ),
        )

        hero = ttk.Frame(content, padding=(12, 8, 12, 14))
        hero.pack(fill=tk.X)
        ttk.Label(
            hero,
            text="Case Study Learning Lab",
            font=("TkDefaultFont", 20, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            hero,
            text="Case별 진행 상황을 확인하고 학습을 이어가세요.",
            foreground="#4b5563",
            font=("TkDefaultFont", 10),
        ).pack(anchor="w", pady=(6, 0))

        overview = ttk.LabelFrame(
            content,
            text="내 학습 현황",
            padding=12,
        )
        overview.pack(fill=tk.X, padx=12, pady=(0, 10))
        ttk.Label(
            overview,
            text=(
                f"현재 제공 Case {portfolio.completed_case_count}/"
                f"{portfolio.total_case_count} 완료"
            ),
            font=("TkDefaultFont", 11, "bold"),
        ).pack(anchor="w")
        progress = ttk.Progressbar(
            overview,
            maximum=max(portfolio.total_case_count, 1),
            value=portfolio.completed_case_count,
            mode="determinate",
        )
        progress.pack(fill=tk.X, pady=(7, 5))
        ttk.Label(
            overview,
            text=(
                f"전체 {portfolio.total_case_count + len(PLANNED_CASES)}개 중 "
                f"{portfolio.total_case_count}개 제공 · "
                f"{len(PLANNED_CASES)}개 준비 중"
            ),
            foreground="#4b5563",
        ).pack(anchor="w")

        recent = max(
            (item for item in portfolio.cases if item.updated_at),
            key=lambda item: item.updated_at or "",
            default=None,
        )
        if recent is not None:
            recent_row = ttk.Frame(overview)
            recent_row.pack(fill=tk.X, pady=(9, 0))
            ttk.Label(
                recent_row,
                text=(
                    f"최근 학습 · {recent.title} · "
                    f"{recent.updated_at.replace('T', ' ')[:16]}"
                ),
                foreground="#4b5563",
            ).pack(side=tk.LEFT)
            if recent.latest_step != LearningStep.SESSION_COMPLETE.value:
                recent_sessions = sessions_by_topic[recent.topic_id]
                if recent_sessions:
                    latest_recent = recent_sessions[0]
                    ttk.Button(
                        recent_row,
                        text="이어서 하기",
                        command=lambda topic_id=recent.topic_id,
                        session_id=latest_recent.session_id: (
                            self._open_case_session(topic_id, session_id)
                        ),
                    ).pack(side=tk.RIGHT)

        record_toggle = ttk.Button(
            overview,
            text=(
                f"학습 기록 {record_count}개 접기 ▲"
                if self.show_cover_records
                else f"학습 기록 {record_count}개 보기 ▼"
            ),
            command=self._toggle_cover_records,
            state=tk.NORMAL if record_count else tk.DISABLED,
        )
        record_toggle.pack(anchor="w", pady=(10, 0))
        if self.show_cover_records and record_count:
            records = ttk.Frame(overview, padding=(10, 7, 0, 0))
            records.pack(fill=tk.X)
            for topic_index, topic in enumerate(ordered_topics, start=1):
                topic_sessions = sessions_by_topic[topic.topic_id]
                if not topic_sessions:
                    continue
                topic_expanded = (
                    topic.topic_id in self.expanded_cover_record_topics
                )
                ttk.Button(
                    records,
                    text=(
                        f"Case {topic_index:02d} · {topic.title} · "
                        f"{len(topic_sessions)}개 접기 ▲"
                        if topic_expanded
                        else f"Case {topic_index:02d} · {topic.title} · "
                        f"{len(topic_sessions)}개 보기 ▼"
                    ),
                    command=lambda topic_id=topic.topic_id: (
                        self._toggle_cover_record_topic(topic_id)
                    ),
                ).pack(fill=tk.X, pady=(6, 3))
                if not topic_expanded:
                    continue
                for session in topic_sessions:
                    row = ttk.Frame(records)
                    row.pack(fill=tk.X, pady=2)
                    ttk.Label(
                        row,
                        text=(
                            f"{session.display_name} · "
                            f"{self._cover_step_label(session.current_step)} · "
                            f"{session.updated_at.replace('T', ' ')[:16]}"
                        ),
                        foreground="#4b5563",
                        wraplength=760,
                        justify=tk.LEFT,
                    ).pack(side=tk.LEFT, fill=tk.X, expand=True)
                    ttk.Button(
                        row,
                        text=(
                            "결과 보기"
                            if session.current_step
                            is LearningStep.SESSION_COMPLETE
                            else "이어서 하기"
                        ),
                        command=lambda topic_id=topic.topic_id,
                        session_id=session.session_id: (
                            self._open_case_session(topic_id, session_id)
                        ),
                    ).pack(side=tk.RIGHT, padx=(8, 0))

        cards = ttk.Frame(content, padding=(6, 0, 6, 12))
        cards.pack(fill=tk.BOTH, expand=True)
        cards.columnconfigure(0, weight=1, uniform="case_card")
        cards.columnconfigure(1, weight=1, uniform="case_card")
        progress_by_topic = {
            item.topic_id: item for item in portfolio.cases
        }
        status_labels = {
            "completed": "완료",
            "in_progress": "진행 중",
            "not_started": "시작 전",
            "locked": "선행 학습 필요",
        }
        status_colors = {
            "completed": "#047857",
            "in_progress": "#1d4ed8",
            "not_started": "#4b5563",
            "locked": "#92400e",
        }
        for index, topic in enumerate(ordered_topics):
            item = progress_by_topic[topic.topic_id]
            sessions = sessions_by_topic[topic.topic_id]
            latest = sessions[0] if sessions else None
            card = ttk.LabelFrame(
                cards,
                text=f"Case {index + 1:02d}",
                padding=14,
            )
            card.grid(
                row=index // 2,
                column=index % 2,
                sticky="nsew",
                padx=6,
                pady=6,
            )
            ttk.Label(
                card,
                text=topic.title,
                font=("TkDefaultFont", 13, "bold"),
                wraplength=500,
                justify=tk.LEFT,
            ).pack(anchor="w")
            ttk.Label(
                card,
                text=status_labels.get(item.status, item.status),
                foreground=status_colors.get(item.status, "#4b5563"),
                font=("TkDefaultFont", 9, "bold"),
            ).pack(anchor="w", pady=(4, 8))
            ttk.Label(
                card,
                text=topic.description,
                wraplength=500,
                justify=tk.LEFT,
            ).pack(anchor="w")
            caption, _baseline, _comparison = format_case_comparison(topic)
            comparison_name = (
                caption.removeprefix("전기적 파라미터 (")
                .removesuffix(")")
            )
            ttk.Label(
                card,
                text=f"변경 조건 · {comparison_name}",
                foreground="#1d4ed8",
            ).pack(anchor="w", pady=(9, 4))
            latest_text = (
                f"최근 학습 · {latest.updated_at.replace('T', ' ')[:16]}"
                if latest is not None
                else "아직 학습 기록이 없습니다."
            )
            ttk.Label(
                card,
                text=latest_text,
                foreground="#4b5563",
            ).pack(anchor="w", pady=(2, 10))
            unlocked = item.prerequisites_met
            if latest is not None:
                primary_text = (
                    "결과 보기"
                    if latest.current_step is LearningStep.SESSION_COMPLETE
                    else "이어서 하기"
                )
                command = (
                    lambda topic_id=topic.topic_id,
                    session_id=latest.session_id: self._open_case_session(
                        topic_id, session_id
                    )
                )
            else:
                primary_text = (
                    "Case 살펴보기"
                    if unlocked
                    else "선행 Case 완료 후 열림"
                )
                command = lambda topic_id=topic.topic_id: (
                    self._start_new_case(topic_id)
                )
            actions = ttk.Frame(card)
            actions.pack(fill=tk.X, side=tk.BOTTOM)
            ttk.Button(
                actions,
                text=primary_text,
                command=command,
                state=tk.NORMAL if unlocked else tk.DISABLED,
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)
            if (
                latest is not None
                and latest.current_step is LearningStep.SESSION_COMPLETE
            ):
                ttk.Button(
                    actions,
                    text="새 세션 시작",
                    command=lambda topic_id=topic.topic_id: (
                        self._start_new_case(topic_id)
                    ),
                    state=tk.NORMAL if unlocked else tk.DISABLED,
                ).pack(side=tk.RIGHT, padx=(6, 0))

        first_placeholder_index = len(ordered_topics)
        for offset, (number, title, description, parameter) in enumerate(
            PLANNED_CASES
        ):
            index = first_placeholder_index + offset
            card = ttk.LabelFrame(
                cards,
                text=f"Case {number:02d}",
                padding=14,
            )
            card.grid(
                row=index // 2,
                column=index % 2,
                sticky="nsew",
                padx=6,
                pady=6,
            )
            ttk.Label(
                card,
                text=title,
                font=("TkDefaultFont", 13, "bold"),
                wraplength=500,
                justify=tk.LEFT,
            ).pack(anchor="w")
            ttk.Label(
                card,
                text="준비 중",
                foreground="#6b7280",
                font=("TkDefaultFont", 9, "bold"),
            ).pack(anchor="w", pady=(4, 8))
            ttk.Label(
                card,
                text=description,
                foreground="#4b5563",
                wraplength=500,
                justify=tk.LEFT,
            ).pack(anchor="w")
            ttk.Label(
                card,
                text=f"예정 파라미터 · {parameter}",
                foreground="#6b7280",
            ).pack(anchor="w", pady=(9, 10))
            ttk.Button(
                card,
                text="준비 중",
                state=tk.DISABLED,
            ).pack(fill=tk.X, side=tk.BOTTOM)

        self._bind_cover_mousewheel(canvas, content)

    def render(self) -> None:
        self._capture_answer_draft()
        self._clear_body()
        self.current_session_var.set(self._current_session_header_text())
        if self.show_cover:
            self._set_cover_chrome(True)
            self._build_cover()
            return
        self._set_cover_chrome(False)
        self._refresh_learning_navigation()
        step = self.session.current_step
        if step is LearningStep.RESULT_READY:
            self.state_machine.transition(
                self.session,
                LearningStep.OBSERVATION_QUESTION,
            )
            self._save(refresh_controls=False)
            step = self.session.current_step
        if step in {LearningStep.FEEDBACK_READY, LearningStep.NEXT_EXPERIMENT}:
            self.state_machine.transition(
                self.session,
                LearningStep.SESSION_COMPLETE,
            )
            self._save(refresh_controls=False)
            step = self.session.current_step
        if step is LearningStep.ERROR:
            self._build_error()
            return
        page = self.learning_view or self._default_learning_page()
        if page == "understanding":
            self._build_introduction()
        elif page == "prediction":
            if step == LearningStep.PREDICTION_QUESTION:
                self._build_prediction()
            elif step in {LearningStep.PREDICTION_SUBMITTED, LearningStep.SIMULATION_RUNNING}:
                self._build_loading()
            else:
                self._build_prediction_review()
        elif page == "observation":
            if step == LearningStep.OBSERVATION_QUESTION:
                self._build_observation()
            elif step == LearningStep.OBSERVATION_SUBMITTED:
                self._build_loading()
            else:
                self._build_observation_review()
        elif step in {
            LearningStep.FEEDBACK_READY,
            LearningStep.NEXT_EXPERIMENT,
            LearningStep.SESSION_COMPLETE,
        }:
            self._build_complete()
        else:
            self._build_feedback()

    def _build_introduction(self) -> None:
        guide = CASE_UNDERSTANDING_GUIDES.get(
            self.topic.topic_id,
            {
                "context": self.topic.description,
                "question": self.topic.prediction_questions[0].prompt,
                "evidence": tuple(self.topic.required_outputs),
                "caution": "한 가지 결과만으로 원인을 단정하지 않습니다.",
            },
        )
        left = ttk.Frame(self.body)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        overview = ttk.LabelFrame(left, text="Case 배경", padding=14)
        overview.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(
            overview,
            text=guide["context"],
            wraplength=650,
            justify=tk.LEFT,
        ).pack(anchor="w")

        question = ttk.LabelFrame(left, text="이번 Case의 핵심 질문", padding=14)
        question.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(
            question,
            text=guide["question"],
            font=("TkDefaultFont", 10, "bold"),
            foreground="#1d4ed8",
            wraplength=650,
            justify=tk.LEFT,
        ).pack(anchor="w")

        goals = ttk.LabelFrame(left, text="학습 목표", padding=14)
        goals.pack(fill=tk.X, pady=(0, 8))
        for objective in self.topic.learning_objectives:
            ttk.Label(
                goals,
                text=f"• {objective}",
                wraplength=650,
                justify=tk.LEFT,
            ).pack(anchor="w", pady=2)

        evidence = ttk.LabelFrame(left, text="결과에서 확인할 근거", padding=14)
        evidence.pack(fill=tk.X)
        for item in guide["evidence"]:
            ttk.Label(
                evidence,
                text=f"• {item}",
                wraplength=650,
                justify=tk.LEFT,
            ).pack(anchor="w", pady=2)
        ttk.Label(
            evidence,
            text=f"해석할 때 주의: {guide['caution']}",
            foreground="#4b5563",
            wraplength=650,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(9, 0))

        right = ttk.LabelFrame(self.body, text="이번 Case의 실험 조건", padding=14)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 0))
        references = getattr(self.topic, "reference_conditions", ())
        if references:
            display_parameters = (
                self.topic.display_parameters
                or tuple(self.topic.baseline_conditions)
            )
            parameter_width = 72 if len(display_parameters) > 2 else 90
            tree = ttk.Treeview(
                right,
                columns=("condition", *display_parameters),
                show="headings",
                height=4,
            )
            columns = [
                ("condition", "Condition", 120),
                *(
                    (
                        name,
                        name,
                        parameter_width,
                    )
                    for name in display_parameters
                ),
            ]
            for name, title, width in columns:
                tree.heading(name, text=title)
                tree.column(name, width=width, anchor=tk.CENTER)
            for label, conditions in topic_condition_rows(self.topic):
                tree.insert(
                    "",
                    tk.END,
                    values=(
                        label,
                        *(
                            f"{conditions[name]:g}"
                            for name in display_parameters
                        ),
                    ),
                )
        else:
            tree = ttk.Treeview(right, columns=("parameter", "baseline", "comparison"), show="headings", height=5)
            for name, title, width in (
                ("parameter", "Parameter", 110), ("baseline", "Baseline", 110), ("comparison", "Comparison", 110),
            ):
                tree.heading(name, text=title)
                tree.column(name, width=width, anchor=tk.CENTER)
            for name in ("L", "T", "B", "SD", "LDD"):
                tree.insert("", tk.END, values=(name, f"{self.topic.baseline_conditions[name]:g}", f"{self.topic.comparison_conditions[name]:g}"))
        tree.pack()
        changed = [
            name
            for name in self.topic.baseline_conditions
            if (
                self.topic.baseline_conditions[name]
                != self.topic.comparison_conditions[name]
            )
        ]
        changed_label = (
            " × ".join(
                CONDITION_LABELS.get(name, name)
                for name in self.topic.display_parameters
            )
            if references
            else CONDITION_LABELS.get(changed[0], changed[0])
            if len(changed) == 1
            else "하나의 parameter"
        )
        ttk.Label(
            right,
            text=f"변경 변수 · {changed_label}",
            foreground="#1d4ed8",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(pady=(10, 8))
        fixed_names = (
            [
                name
                for name in self.topic.baseline_conditions
                if name not in self.topic.display_parameters
                and all(
                    reference.conditions[name]
                    == self.topic.baseline_conditions[name]
                    for reference in references
                )
                and self.topic.comparison_conditions[name]
                == self.topic.baseline_conditions[name]
            ]
            if references
            else self.session.fixed_parameters
        )
        fixed_labels = [
            CONDITION_LABELS.get(name, name)
            for name in fixed_names
        ]
        ttk.Label(
            right,
            text=(
                "고정 변수 · " + ", ".join(fixed_labels)
                if fixed_labels
                else "고정 변수 · 없음 (후보별 설계값 비교)"
            ),
            foreground="#4b5563",
            wraplength=320,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 10))
        if self.session.current_step in {
            LearningStep.INTRODUCTION,
            LearningStep.BASELINE_SETUP,
        }:
            ttk.Button(right, text="사전 예측 시작", command=self._begin_prediction).pack(fill=tk.X)
        else:
            ttk.Label(
                right,
                text="학습 목표와 비교 조건을 다시 보는 화면입니다.",
                foreground="#4b5563",
                wraplength=320,
            ).pack(pady=(4, 0))

    def _begin_prediction(self) -> None:
        if self.session.current_step == LearningStep.INTRODUCTION:
            self.state_machine.transition(self.session, LearningStep.BASELINE_SETUP)
        self.state_machine.transition(self.session, LearningStep.PREDICTION_QUESTION)
        self.learning_view = "prediction"
        self._save()
        self.render()

    def _build_question(
        self,
        parent: tk.Misc,
        question,
        *,
        wraplength: int = 820,
        initial_answer: dict[str, Any] | None = None,
    ) -> Callable[[], Any]:
        initial = dict(initial_answer or {})
        initial_selected = {
            str(item) for item in initial.get("selected", ())
        }
        frame = ttk.LabelFrame(parent, text="질문", padding=10)
        frame.pack(fill=tk.X, pady=5)
        ttk.Label(
            frame,
            text=question.prompt,
            font=("TkDefaultFont", 9, "bold"),
            wraplength=wraplength,
            justify=tk.LEFT,
        ).pack(anchor="w", fill=tk.X, pady=(0, 5))
        if question.type.startswith("single_select"):
            selected = tk.StringVar(
                value=next(
                    (
                        option for option in question.options
                        if option in initial_selected
                    ),
                    "",
                )
            )
            for option in question.options:
                row = ttk.Frame(frame)
                row.pack(fill=tk.X, pady=2)
                ttk.Radiobutton(
                    row,
                    value=option,
                    variable=selected,
                ).pack(side=tk.LEFT, anchor="n")
                label = ttk.Label(
                    row,
                    text=option,
                    wraplength=max(180, wraplength - 40),
                    justify=tk.LEFT,
                )
                label.pack(side=tk.LEFT, fill=tk.X, expand=True)
                label.bind(
                    "<Button-1>",
                    lambda _event, value=option: selected.set(value),
                )
            get_selected = lambda: [selected.get()] if selected.get() else []
        else:
            variables = {
                option: tk.BooleanVar(value=option in initial_selected)
                for option in question.options
            }
            for option, variable in variables.items():
                row = ttk.Frame(frame)
                row.pack(fill=tk.X, pady=2)
                ttk.Checkbutton(row, variable=variable).pack(
                    side=tk.LEFT,
                    anchor="n",
                )
                label = ttk.Label(
                    row,
                    text=option,
                    wraplength=max(180, wraplength - 40),
                    justify=tk.LEFT,
                )
                label.pack(side=tk.LEFT, fill=tk.X, expand=True)
                label.bind(
                    "<Button-1>",
                    lambda _event, value=variable: value.set(not value.get()),
                )
            get_selected = lambda: [option for option, variable in variables.items() if variable.get()]
        reason = None
        if question.reason_required:
            ttk.Label(frame, text="근거").pack(anchor="w", pady=(7, 2))
            reason = tk.Text(frame, height=3, wrap=tk.WORD)
            initial_reason = str(initial.get("reason", ""))
            if initial_reason:
                reason.insert("1.0", initial_reason)
                self._grow_text_to_content(
                    reason,
                    minimum=3,
                    text=initial_reason,
                    wraplength=wraplength,
                )
            reason.pack(fill=tk.X)
            reason.bind(
                "<<Modified>>",
                lambda _event, widget=reason: self._grow_text_to_content(
                    widget,
                    minimum=3,
                ),
            )

        def collect() -> dict[str, Any]:
            return {
                "selected": get_selected(),
                "reason": reason.get("1.0", tk.END).strip() if reason else "",
            }

        return collect

    @staticmethod
    def _grow_text_to_content(
        widget: tk.Text,
        *,
        minimum: int = 3,
        text: str | None = None,
        wraplength: int | None = None,
    ) -> None:
        content = widget.get("1.0", "end-1c") if text is None else text
        if wraplength:
            characters_per_line = max(20, wraplength // 8)
            lines = sum(
                max(1, (len(line) + characters_per_line - 1) // characters_per_line)
                for line in content.splitlines() or [""]
            )
        else:
            try:
                lines = int(widget.count("1.0", "end-1c", "displaylines")[0])
            except (TypeError, tk.TclError):
                lines = max(1, len(content.splitlines()))
        widget.configure(height=max(minimum, lines))
        try:
            widget.edit_modified(False)
        except tk.TclError:
            pass

    def _build_prediction(self) -> None:
        self._collectors_session_id = self.session.session_id
        actions = ttk.Frame(self.body)
        actions.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 0))
        ttk.Button(
            actions,
            text="예측 제출 후 모델 실행",
            command=self._submit_prediction,
        ).pack(side=tk.RIGHT, ipady=3)
        canvas = tk.Canvas(
            self.body,
            highlightthickness=0,
            borderwidth=0,
            yscrollincrement=12,
        )
        scrollbar = ttk.Scrollbar(
            self.body,
            orient=tk.VERTICAL,
            command=canvas.yview,
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        wrapper = ttk.Frame(canvas, padding=(0, 0, 8, 0))
        wrapper_window = canvas.create_window(
            (0, 0),
            window=wrapper,
            anchor="nw",
        )
        wrapper.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(
                wrapper_window,
                width=max(360, int(event.width)),
            ),
        )
        ttk.Label(wrapper, text="결과를 실행하기 전에 예상해보세요.", font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        self._build_prediction_condition_guide(wrapper)
        for question in self.topic.prediction_questions:
            self.answer_collectors[question.question_id] = self._build_question(
                wrapper,
                question,
                initial_answer=self._draft_answer(question.question_id),
            )
        self._bind_feedback_mousewheel(canvas)

    def _build_prediction_condition_guide(self, parent: tk.Misc) -> None:
        descriptions = self.topic.condition_descriptions
        if not descriptions:
            return
        guide = ttk.LabelFrame(
            parent,
            text="예측에 사용할 후보 조건",
            padding=10,
        )
        guide.pack(fill=tk.X, pady=(8, 10))
        ttk.Label(
            guide,
            text=(
                "후보 이름만으로 고르지 말고 아래 수치 조건에서 예상되는 "
                "Ion·Ioff·DIBL·SS의 방향을 근거로 선택하세요."
            ),
            foreground="#4b5563",
            wraplength=920,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 7))
        parameters = self.topic.display_parameters or tuple(
            self.topic.baseline_conditions
        )
        for label, conditions in topic_condition_rows(self.topic):
            row = ttk.Frame(guide, padding=(0, 5))
            row.pack(fill=tk.X)
            ttk.Label(
                row,
                text=label,
                width=10,
                font=("TkDefaultFont", 9, "bold"),
                foreground="#1d4ed8",
            ).pack(side=tk.LEFT, anchor="n")
            details = ttk.Frame(row)
            details.pack(side=tk.LEFT, fill=tk.X, expand=True)
            ttk.Label(
                details,
                text=format_condition_details(conditions, parameters),
                font=("TkFixedFont", 9),
                wraplength=850,
                justify=tk.LEFT,
            ).pack(anchor="w")
            ttk.Label(
                details,
                text=descriptions[label],
                wraplength=850,
                justify=tk.LEFT,
            ).pack(anchor="w", pady=(2, 0))

    @staticmethod
    def _format_saved_answer(answer: Any) -> tuple[str, str]:
        if not isinstance(answer, dict):
            return str(answer or "-"), ""
        selected = answer.get("selected", [])
        if isinstance(selected, (list, tuple)):
            selected_text = ", ".join(str(item) for item in selected) or "-"
        else:
            selected_text = str(selected or "-")
        return selected_text, str(answer.get("reason", "") or "").strip()

    def _build_answer_review(
        self,
        parent: tk.Misc,
        questions: tuple[Any, ...],
        answers: dict[str, Any],
        *,
        wraplength: int = 820,
    ) -> None:
        for question in questions:
            frame = ttk.LabelFrame(parent, text="질문", padding=10)
            frame.pack(fill=tk.X, pady=5)
            ttk.Label(
                frame,
                text=question.prompt,
                font=("TkDefaultFont", 9, "bold"),
                wraplength=wraplength,
                justify=tk.LEFT,
            ).pack(anchor="w", fill=tk.X, pady=(0, 5))
            raw_answer = answers.get(question.question_id)
            _selected_text, reason = self._format_saved_answer(raw_answer)
            selected_values = set(
                raw_answer.get("selected", [])
                if isinstance(raw_answer, dict)
                else []
            )
            if question.type.startswith("single_select"):
                selected_var = tk.StringVar(
                    value=next(iter(selected_values), "")
                )
                self._review_variables.append(selected_var)
                for option in question.options:
                    row = ttk.Frame(frame)
                    row.pack(fill=tk.X, pady=2)
                    ttk.Radiobutton(
                        row,
                        variable=selected_var,
                        value=option,
                        state=tk.DISABLED,
                    ).pack(side=tk.LEFT, anchor="n")
                    ttk.Label(
                        row,
                        text=option,
                        wraplength=max(180, wraplength - 40),
                        justify=tk.LEFT,
                    ).pack(side=tk.LEFT, fill=tk.X, expand=True)
            else:
                for option in question.options:
                    row = ttk.Frame(frame)
                    row.pack(fill=tk.X, pady=2)
                    checked = tk.BooleanVar(value=option in selected_values)
                    self._review_variables.append(checked)
                    ttk.Checkbutton(
                        row,
                        variable=checked,
                        state=tk.DISABLED,
                    ).pack(side=tk.LEFT, anchor="n")
                    ttk.Label(
                        row,
                        text=option,
                        wraplength=max(180, wraplength - 40),
                        justify=tk.LEFT,
                    ).pack(side=tk.LEFT, fill=tk.X, expand=True)
            if question.reason_required:
                ttk.Label(frame, text="근거").pack(anchor="w", pady=(7, 2))
                reason_box = tk.Text(frame, height=3, wrap=tk.WORD)
                reason_box.insert("1.0", reason or "-")
                self._grow_text_to_content(
                    reason_box,
                    minimum=3,
                    text=reason or "-",
                    wraplength=wraplength,
                )
                reason_box.configure(state=tk.DISABLED)
                reason_box.pack(fill=tk.X)

    def _build_prediction_review(self) -> None:
        canvas = tk.Canvas(
            self.body,
            highlightthickness=0,
            borderwidth=0,
            yscrollincrement=12,
        )
        scrollbar = ttk.Scrollbar(
            self.body,
            orient=tk.VERTICAL,
            command=canvas.yview,
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        wrapper = ttk.Frame(canvas, padding=(0, 0, 8, 0))
        wrapper_window = canvas.create_window(
            (0, 0),
            window=wrapper,
            anchor="nw",
        )
        wrapper.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(
                wrapper_window,
                width=max(360, int(event.width)),
            ),
        )
        ttk.Label(
            wrapper,
            text="제출한 초기 예측",
            font=("TkDefaultFont", 11, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            wrapper,
            text="결과를 보기 전에 기록한 답변입니다. 제출 후에는 수정되지 않습니다.",
            foreground="#4b5563",
        ).pack(anchor="w", pady=(3, 7))
        self._build_answer_review(
            wrapper,
            self.topic.prediction_questions,
            self._latest_prediction_answers(),
            wraplength=820,
        )
        self._bind_feedback_mousewheel(canvas)

    def _collect_answers(self) -> dict[str, Any] | None:
        answers = {question_id: collect() for question_id, collect in self.answer_collectors.items()}
        if any(not answer["selected"] for answer in answers.values()):
            messagebox.showinfo("답변 필요", "각 질문에서 하나 이상의 답을 선택해주세요.", parent=self.window)
            return None
        questions = {
            question.question_id: question
            for question in (
                *self.topic.prediction_questions,
                *self.topic.observation_questions,
            )
        }
        if any(
            questions[question_id].reason_required
            and not str(answer.get("reason", "")).strip()
            for question_id, answer in answers.items()
        ):
            messagebox.showinfo(
                "근거 필요",
                "근거가 필요한 질문에 설명을 입력해주세요.",
                parent=self.window,
            )
            return None
        return answers

    def _submit_prediction(self) -> None:
        answers = self._collect_answers()
        if answers is None:
            return
        self.state_machine.submit_predictions(self.session, answers)
        self._discard_answer_draft()
        self._save()
        self._start_simulation(use_session_transition=True)

    def _build_loading(self) -> None:
        box = ttk.LabelFrame(self.body, text="처리 중", padding=30)
        box.pack(expand=True)
        ttk.Label(box, text="예측 모델과 분석 파이프라인을 실행하고 있습니다.", font=("TkDefaultFont", 11, "bold")).pack()
        progress = ttk.Progressbar(box, mode="indeterminate", length=360)
        progress.pack(pady=15)
        progress.start(12)
        ttk.Label(box, text="Curve, 전기적 파라미터, Potential, Electric Field를 생성합니다.").pack()
        if self.session.current_step is LearningStep.PREDICTION_SUBMITTED:
            ttk.Button(
                box,
                text="저장된 예측으로 실험 계속",
                command=lambda: self._start_simulation(use_session_transition=True),
            ).pack(fill=tk.X, pady=(12, 0))
        elif self.session.current_step is LearningStep.SIMULATION_RUNNING:
            ttk.Button(
                box,
                text="실험 다시 실행",
                command=lambda: self._start_simulation(use_session_transition=False),
            ).pack(fill=tk.X, pady=(12, 0))
        elif self.session.current_step is LearningStep.OBSERVATION_SUBMITTED:
            ttk.Label(
                box,
                text="저장된 관찰 답변을 평가하고 학습 요약을 준비합니다.",
            ).pack(pady=(12, 0))
            if not self._busy:
                self.window.after_idle(self._resume_evaluation_if_idle)

    def _run_async(
        self,
        task: Callable[[], Any],
        on_success: Callable[[Any], None],
        failure_title: str,
        on_failure: Callable[[], None] | None = None,
    ) -> None:
        if self._busy:
            return
        self._busy = True
        self._set_session_controls_enabled(False)

        def worker() -> None:
            try:
                result = task()
            except Exception as error:
                self.window.after(
                    0,
                    lambda captured=error: self._async_failed(
                        failure_title,
                        captured,
                        on_failure,
                    ),
                )
            else:
                self.window.after(0, lambda: self._async_succeeded(result, on_success))

        threading.Thread(target=worker, daemon=True).start()

    def _async_succeeded(self, result: Any, callback: Callable[[Any], None]) -> None:
        self._busy = False
        self._set_session_controls_enabled(True)
        callback(result)

    def _async_failed(
        self,
        title: str,
        error: Exception,
        on_failure: Callable[[], None] | None = None,
    ) -> None:
        self._busy = False
        self._set_session_controls_enabled(True)
        if on_failure is not None:
            on_failure()
        self._save()
        self.render()
        error_code = str(error)
        if not error_code.startswith("learning_experiment_failed:"):
            error_code = error.__class__.__name__
        messagebox.showerror(
            title,
            "처리를 완료하지 못했습니다. 저장된 상태에서 다시 시도할 수 있습니다."
            f"\n\n오류 코드: {error_code}",
            parent=self.window,
        )

    def _start_simulation(self, *, use_session_transition: bool) -> None:
        return_learning_view = (
            "observation" if use_session_transition else self.learning_view
        )
        return_completion_tab = self.completion_view_tab
        self.status_var.set("학습 실험을 실행하는 중입니다.")
        if use_session_transition:
            task = lambda: self.runner.execute_for_session(self.session, self.topic, self.state_machine)
        else:
            task = lambda: self.runner.execute(self.topic)
        # PREDICTION_SUBMITTED also renders the loading page. The worker owns
        # the PREDICTION_SUBMITTED -> SIMULATION_RUNNING -> RESULT_READY path.
        self.render()

        def complete(result: LearningExperimentResult) -> None:
            self.result = result
            self.context = result.learning_context
            self.session.analysis_snapshot = self.context.to_dict()
            if self.session.current_step == LearningStep.SIMULATION_RUNNING:
                self.state_machine.transition(self.session, LearningStep.RESULT_READY)
            if self.session.current_step == LearningStep.RESULT_READY:
                self.state_machine.transition(
                    self.session,
                    LearningStep.OBSERVATION_QUESTION,
                )
            self.learning_view = return_learning_view
            self.completion_view_tab = return_completion_tab
            self._save()
            self.status_var.set("예측과 분석이 완료되었습니다.")
            self.render()

        self._run_async(task, complete, "Case Study 실행 실패")

    def _build_results(self, parent: tk.Misc) -> None:
        container = ttk.Frame(parent)
        container.pack(fill=tk.BOTH, expand=True)
        content = ttk.Frame(container)
        parameter_caption, _baseline_label, _comparison_label = (
            format_case_comparison(self.topic)
        )
        parameters = ttk.LabelFrame(
            container,
            text=parameter_caption,
            padding=5,
            width=COMPACT_PARAMETER_PANEL_WIDTH,
        )
        content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        parameters.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 0))
        parameters.pack_propagate(False)
        notebook = ttk.Notebook(content)
        notebook.pack(fill=tk.BOTH, expand=True)
        curve_tab, field_tab = ttk.Frame(notebook), ttk.Frame(notebook)
        chat_tab = ttk.Frame(notebook)
        notebook.add(curve_tab, text="I–V Curve")
        notebook.add(field_tab, text="Field Map")
        notebook.add(chat_tab, text="AI 자유 질문")
        tab_ids = {
            notebook.tab(tab_id, "text"): tab_id for tab_id in notebook.tabs()
        }
        if self.result_view_tab in tab_ids:
            notebook.select(tab_ids[self.result_view_tab])

        def remember_tab(_event=None) -> None:
            selected = notebook.select()
            if selected:
                self.result_view_tab = notebook.tab(selected, "text")
                self.session.remember_ui(
                    result_view_tab=self.result_view_tab
                )
                self._save(refresh_controls=False)

        notebook.bind("<<NotebookTabChanged>>", remember_tab)
        self._build_curve_view(curve_tab)
        self._build_field_view(field_tab)
        self._build_parameter_table(parameters, compact=True)
        self._build_chat(chat_tab)

    def _build_curve_view(self, parent: tk.Misc) -> None:
        if self.result is None:
            ttk.Label(
                parent,
                text="저장된 분석 결과가 있습니다. 그래프를 다시 생성하면 시각화할 수 있습니다.",
                wraplength=620,
            ).pack(expand=True)
            ttk.Button(
                parent,
                text="그래프 다시 생성",
                command=lambda: self._start_simulation(
                    use_session_transition=False
                ),
            ).pack(pady=8)
            return
        figure = Figure(figsize=(9, 5), dpi=90)
        display_runs = self._labeled_display_runs()
        render_curve_figure(
            figure,
            [
                (label, run.idvd, run.idvg)
                for label, run in display_runs
            ],
        )
        canvas = FigureCanvasTkAgg(figure, master=parent)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        canvas.draw_idle()
        self._plot_canvases.append(canvas)

    def _build_field_view(self, parent: tk.Misc) -> None:
        if self.result is None:
            ttk.Label(
                parent,
                text="저장된 분석 결과가 있습니다. Field Map을 다시 생성하면 시각화할 수 있습니다.",
                wraplength=620,
            ).pack(expand=True)
            ttk.Button(
                parent,
                text="Field Map 다시 생성",
                command=lambda: self._start_simulation(
                    use_session_transition=False
                ),
            ).pack(pady=8)
            return
        controls = ttk.Frame(parent, padding=5)
        controls.pack(fill=tk.X)
        ttk.Label(controls, text="Display").pack(side=tk.LEFT)
        display_box = ttk.Combobox(
            controls,
            textvariable=self.field_display_var,
            values=FIELD_DISPLAYS,
            state="readonly",
            width=30,
        )
        display_box.pack(side=tk.LEFT, padx=5)
        field_figure = Figure(figsize=(9, 5), dpi=90)
        field_canvas = FigureCanvasTkAgg(field_figure, master=parent)
        field_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self._plot_canvases.append(field_canvas)

        def draw_field(_event=None) -> None:
            display_runs = self._labeled_display_runs()
            render_model_field_comparison(
                field_figure,
                [
                    (label, run.field_map)
                    for label, run in display_runs
                ],
                self.field_display_var.get(),
                "Auto",
                "Robust 1-99%",
            )
            field_canvas.draw_idle()
            self.session.remember_ui(
                field_display=self.field_display_var.get()
            )
            self._save(refresh_controls=False)

        display_box.bind("<<ComboboxSelected>>", draw_field)
        draw_field()

    def _labeled_display_runs(self) -> list[tuple[str, Any]]:
        if self.result.references:
            return [
                (
                    format_curve_condition_label(
                        self.topic,
                        run.label,
                        run.conditions,
                    ),
                    run,
                )
                for run in self.result.display_runs
            ]
        baseline_label, comparison_label = format_case_comparison(
            self.topic
        )[1:]
        return [
            (baseline_label, self.result.baseline),
            (comparison_label, self.result.comparison),
        ]

    def _build_parameter_table(self, parent: tk.Misc, *, compact: bool = False) -> None:
        if self.context is None:
            ttk.Label(parent, text="분석 문맥을 복원할 수 없습니다.").pack(expand=True)
            return
        _caption, baseline_label, comparison_label = format_case_comparison(
            self.topic
        )
        columns = (
            ("metric", "Metric", 135),
            ("before", baseline_label, 78),
            ("after", comparison_label, 78),
            ("direction", "변화", 50),
        ) if compact else (
            ("metric", "Metric", 130),
            ("before", "Baseline", 140),
            ("after", "Comparison", 140),
            ("direction", "Direction", 100),
            ("unit", "Unit", 100),
        )
        rows = self._metric_table_rows()
        tree = ttk.Treeview(
            parent,
            columns=tuple(item[0] for item in columns),
            show="headings",
            style="CaseMetric.Treeview",
            height=max(10, len(rows)),
        )
        for name, title, width in columns:
            tree.heading(name, text=title)
            tree.column(
                name,
                width=width,
                minwidth=width,
                anchor=tk.CENTER,
                stretch=False,
            )
        tree.bind("<Button-1>", self._block_treeview_resize, add="+")
        tree.bind("<B1-Motion>", self._block_treeview_resize, add="+")
        for name, before, after, direction, unit in rows:
            display_name = METRIC_LABELS.get(name, name)
            metric = (
                f"{display_name} ({unit})"
                if compact and unit
                else display_name
            )
            values = (
                metric,
                self._format_metric_table_value(before),
                self._format_metric_table_value(after),
                {"increase": "↑", "decrease": "↓", "stable": "→"}.get(
                    direction,
                    "—",
                ),
            ) if compact else (
                display_name,
                self._format_metric_table_value(before),
                self._format_metric_table_value(after),
                direction if direction != "unavailable" else "확인 불가",
                unit,
            )
            tree.insert("", tk.END, values=(
                *values,
            ))
        tree.pack(fill=tk.BOTH, expand=True)

    def _metric_table_rows(
        self,
    ) -> tuple[tuple[str, float | None, float | None, str, str], ...]:
        if self.context is None:
            return ()
        display = self.context.experiment.get(
            "display_electrical_parameters",
            {},
        )
        has_display_snapshot = (
            isinstance(display, dict)
            and "baseline" in display
            and "comparison" in display
        )
        baseline = display.get("baseline", {}).get("values", {}) if has_display_snapshot else {}
        comparison = display.get("comparison", {}).get("values", {}) if has_display_snapshot else {}
        rows = []
        if (
            has_display_snapshot
            and isinstance(baseline, dict)
            and isinstance(comparison, dict)
        ):
            for name, raw_name, unit, factor in METRIC_TABLE_SPECS:
                before_value = self._metric_table_number(
                    baseline.get(raw_name),
                    factor,
                )
                after_value = self._metric_table_number(
                    comparison.get(raw_name),
                    factor,
                )
                direction = (
                    "increase"
                    if (
                        before_value is not None
                        and after_value is not None
                        and after_value > before_value
                    )
                    else "decrease"
                    if (
                        before_value is not None
                        and after_value is not None
                        and after_value < before_value
                    )
                    else "stable"
                    if before_value is not None and after_value is not None
                    else "unavailable"
                )
                rows.append(
                    (name, before_value, after_value, direction, unit)
                )
            return tuple(rows)
        for name, _raw_name, unit, _factor in METRIC_TABLE_SPECS:
            change = self.context.electrical_changes.get(name)
            if (
                change is None
                or not change.available
                or change.before is None
                or change.after is None
            ):
                rows.append((name, None, None, "unavailable", unit))
            else:
                rows.append(
                    (
                        name,
                        change.before,
                        change.after,
                        change.direction,
                        change.unit or unit,
                    )
                )
        return tuple(rows)

    @staticmethod
    def _metric_table_number(value: Any, factor: float) -> float | None:
        try:
            number = float(value) * factor
        except (TypeError, ValueError, OverflowError):
            return None
        return number if math.isfinite(number) else None

    @staticmethod
    def _format_metric_table_value(value: float | None) -> str:
        return "—" if value is None else f"{value:.7g}"

    @staticmethod
    def _block_treeview_resize(event: tk.Event) -> str | None:
        tree = event.widget
        if tree.identify_region(event.x, event.y) == "separator":
            return "break"
        return None

    def _build_chat(self, parent: tk.Misc) -> None:
        banner = ttk.Frame(parent, padding=(8, 7))
        banner.pack(fill=tk.X)
        ttk.Label(
            banner,
            textvariable=self.tutor_mode_var,
            foreground="#1d4ed8",
            font=("TkDefaultFont", 9, "bold"),
        ).pack(side=tk.LEFT)
        quality_text = "답변마다 실제 생성 방식과 사용 근거를 표시합니다."
        quality_color = "#4b5563"
        if self.session.followup_history and self.context is not None:
            quality = audit_learning_session(self.session, self.context)
            quality_text = (
                f"대화 검증 {quality.coverage_text}"
                f" · fallback {quality.fallback_turns}"
            )
            if not quality.passed:
                quality_text += f" · 점검 {len(quality.gate_failures)}"
                quality_color = "#b45309"
        ttk.Label(
            banner,
            text=quality_text,
            foreground=quality_color,
        ).pack(side=tk.RIGHT)
        history = ScrolledText(parent, height=14, wrap=tk.WORD, state=tk.NORMAL)
        history.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))
        history.tag_configure("user", font=("TkDefaultFont", 9, "bold"))
        history.tag_configure("meta", foreground="#1d4ed8")
        history.tag_configure("detail", foreground="#4b5563")
        if not self.session.followup_history:
            history.insert(
                tk.END,
                "현재 결과, Case 이론, 인접 반도체 이론에 대해 자유롭게 질문할 수 있습니다.\n"
                "새 조건의 결과가 필요하면 추가 실험 여부를 구분해 안내합니다.\n",
            )
        for turn in self.session.followup_history:
            metadata, details = format_followup_metadata(turn)
            history.insert(tk.END, "\n사용자: ", "user")
            history.insert(tk.END, f"{turn.question}\n")
            history.insert(tk.END, f"AI [{metadata}]\n", "meta")
            history.insert(tk.END, f"{turn.answer}\n")
            if details:
                history.insert(tk.END, f"{details}\n", "detail")
            if turn.case_connection:
                history.insert(
                    tk.END,
                    f"Case 연결: {turn.case_connection}\n",
                    "detail",
                )
            if (
                turn.next_learning_question
                and (
                    turn.question_type != "current_result"
                    or turn.needs_clarification
                    or getattr(
                        turn,
                        "learning_move",
                        "answer_question",
                    ) != "answer_question"
                )
            ):
                history.insert(
                    tk.END,
                    f"이어서 생각해 볼 질문: {turn.next_learning_question}\n",
                    "detail",
                )
        history.configure(state=tk.DISABLED)
        history.see(tk.END)
        history.after_idle(
            lambda widget=history: widget.yview_moveto(1.0)
        )
        examples = ttk.Frame(parent, padding=(8, 2))
        examples.pack(fill=tk.X)
        ttk.Label(examples, text="질문 예시").pack(side=tk.LEFT, padx=(0, 5))
        row = ttk.Frame(parent, padding=(8, 4, 8, 8))
        row.pack(fill=tk.X)
        question = tk.Text(row, height=3, wrap=tk.WORD)
        question.pack(side=tk.LEFT, fill=tk.X, expand=True)
        for label, example in FOLLOWUP_EXAMPLES:
            ttk.Button(
                examples,
                text=label,
                command=lambda value=example: (
                    question.delete("1.0", tk.END),
                    question.insert("1.0", value),
                    question.focus_set(),
                ),
            ).pack(side=tk.LEFT, padx=2)
        send = ttk.Button(
            row,
            text="질문 보내기",
            state=tk.NORMAL if self.context is not None else tk.DISABLED,
        )
        send.pack(side=tk.RIGHT, padx=(6, 0))
        retry = ttk.Button(
            row,
            text="최근 실패 재시도",
            state=tk.DISABLED,
        )
        retry.pack(side=tk.RIGHT, padx=(6, 0))
        if self.context is None:
            ttk.Label(
                row,
                text="분석 결과를 복원하거나 그래프를 다시 생성한 뒤 질문할 수 있습니다.",
                foreground="#b45309",
            ).pack(side=tk.BOTTOM, anchor="w")

        def submit() -> None:
            text = question.get("1.0", tk.END).strip()
            if not text or self.context is None:
                return
            send.configure(state=tk.DISABLED)
            self.status_var.set("학습 AI가 근거를 확인하는 중입니다.")
            history_data = [
                {
                    "question": turn.question,
                    "answer": turn.answer,
                    "question_type": turn.question_type,
                    "matched_concepts": turn.matched_concepts,
                    "source": turn.source,
                    "interpreted_intent": turn.interpreted_intent,
                    "pipeline_diagnostics": turn.pipeline_diagnostics,
                }
                for turn in self.session.followup_history
            ]

            def complete(response) -> None:
                LearningLLMService.record_followup(self.session, text, response)
                self._save()
                if response.source == "external_llm":
                    status = "AI 답변이 생성되었습니다."
                elif response.source == "external_error":
                    reason = public_failure_label(
                        response.fallback_reason,
                        (
                            dict(response.pipeline_diagnostics[-1])
                            if response.pipeline_diagnostics
                            else {}
                        ),
                    )
                    status = f"{reason}: 오류 안내를 확인해 주세요."
                elif response.fallback_reason:
                    reason = FALLBACK_LABELS.get(
                        response.fallback_reason,
                        response.fallback_reason,
                    )
                    status = f"{reason}: 로컬 튜터 답변을 사용했습니다."
                else:
                    status = "로컬 지식 기반 답변이 생성되었습니다."
                self.status_var.set(status)
                self.render()

            self._run_async(
                lambda: self.llm_service.ask_followup(
                    self.topic,
                    text,
                    self.context,
                    history_data,
                    self.session.dialogue_state.to_dict(),
                    {
                        "understanding_level": (
                            self.session.understanding_level.value
                        ),
                        "completed_concepts": self.session.completed_concepts,
                        "remaining_concepts": self.session.remaining_concepts,
                        "detected_misconceptions": (
                            self.session.detected_misconceptions
                        ),
                    },
                ),
                complete,
                "자유 질문 처리 실패",
            )

        send.configure(command=submit)
        latest = (
            self.session.followup_history[-1]
            if self.session.followup_history
            else None
        )

        def retry_latest() -> None:
            if latest is None:
                return
            question.delete("1.0", tk.END)
            question.insert("1.0", latest.question)
            submit()

        retry.configure(command=retry_latest)
        retry_seconds = 0
        retry_enabled = bool(
            latest is not None and latest.source == "external_error"
        )
        if retry_enabled:
            for diagnostic in reversed(latest.pipeline_diagnostics):
                value = diagnostic.get(
                    "recommended_retry_after_seconds"
                )
                if isinstance(value, int):
                    retry_seconds = max(0, value)
                    break
        self._arm_case_retry_button(
            retry,
            retry_seconds,
            enabled=retry_enabled,
        )

    @staticmethod
    def _arm_case_retry_button(
        button: ttk.Button,
        seconds: int,
        *,
        enabled: bool,
    ) -> None:
        def tick(value: int) -> None:
            try:
                if value > 0:
                    button.configure(
                        state=tk.DISABLED,
                        text=f"재시도 {value}초",
                    )
                    button.after(1000, lambda: tick(value - 1))
                else:
                    button.configure(
                        state=(tk.NORMAL if enabled else tk.DISABLED),
                        text="최근 실패 재시도",
                    )
            except tk.TclError:
                return

        tick(max(0, int(seconds)))

    def _build_observation(self) -> None:
        self._collectors_session_id = self.session.session_id
        container = ttk.Frame(self.body)
        container.pack(fill=tk.BOTH, expand=True)
        results = ttk.Frame(container)
        questions = ttk.Frame(
            container,
            padding=8,
            width=OBSERVATION_PANEL_WIDTH,
        )
        results.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        questions.pack(side=tk.RIGHT, fill=tk.Y)
        questions.pack_propagate(False)
        self._build_results(results)
        actions = ttk.Frame(questions)
        actions.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 0))
        ttk.Button(
            actions,
            text="관찰 답변 제출",
            command=self._submit_observation,
        ).pack(fill=tk.X, ipady=3)
        canvas = tk.Canvas(
            questions,
            highlightthickness=0,
            borderwidth=0,
            yscrollincrement=12,
        )
        scrollbar = ttk.Scrollbar(
            questions,
            orient=tk.VERTICAL,
            command=canvas.yview,
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cards = ttk.Frame(canvas, padding=(0, 0, 8, 0))
        cards_window = canvas.create_window((0, 0), window=cards, anchor="nw")
        cards.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        def fit_question_width(event) -> None:
            content_width = max(260, int(event.width))
            canvas.itemconfigure(cards_window, width=content_width)
            self._set_feedback_wraplength(
                cards,
                max(220, content_width - 48),
            )

        canvas.bind("<Configure>", fit_question_width)
        ttk.Label(
            cards,
            text="그래프와 Field Map을 관찰한 뒤 답하세요.",
            font=("TkDefaultFont", 10, "bold"),
            wraplength=400,
        ).pack(anchor="w", fill=tk.X)
        for question in self.topic.observation_questions:
            self.answer_collectors[question.question_id] = self._build_question(
                cards,
                question,
                wraplength=400,
                initial_answer=self._draft_answer(question.question_id),
            )
        self._bind_feedback_mousewheel(canvas)

    def _build_observation_review(self) -> None:
        container = ttk.Frame(self.body)
        container.pack(fill=tk.BOTH, expand=True)
        results = ttk.Frame(container)
        answers = ttk.Frame(
            container,
            padding=8,
            width=OBSERVATION_PANEL_WIDTH,
        )
        results.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        answers.pack(side=tk.RIGHT, fill=tk.Y)
        answers.pack_propagate(False)
        self._build_results(results)
        canvas = tk.Canvas(
            answers,
            highlightthickness=0,
            borderwidth=0,
            yscrollincrement=12,
        )
        scrollbar = ttk.Scrollbar(
            answers,
            orient=tk.VERTICAL,
            command=canvas.yview,
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cards = ttk.Frame(canvas, padding=(0, 0, 8, 0))
        cards_window = canvas.create_window((0, 0), window=cards, anchor="nw")
        cards.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        def fit_answer_width(event) -> None:
            content_width = max(260, int(event.width))
            canvas.itemconfigure(cards_window, width=content_width)
            self._set_feedback_wraplength(
                cards,
                max(220, content_width - 48),
            )

        canvas.bind("<Configure>", fit_answer_width)
        ttk.Label(
            cards,
            text="제출한 결과 관찰",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(anchor="w", pady=(0, 5))
        self._build_answer_review(
            cards,
            self.topic.observation_questions,
            self._latest_observation_answers(),
            wraplength=400,
        )
        self._bind_feedback_mousewheel(canvas)

    def _submit_observation(self) -> None:
        answers = self._collect_answers()
        if answers is None or self.context is None:
            return
        self.state_machine.submit_observations(self.session, answers)
        self._discard_answer_draft()
        self._save()
        self._start_evaluation(answers)

    def _latest_observation_answers(self) -> dict[str, Any]:
        expected = {question.question_id for question in self.topic.observation_questions}
        answers: dict[str, Any] = {}
        for record in reversed(self.session.observation_answers):
            if record.question_id in expected and record.question_id not in answers:
                answers[record.question_id] = record.raw_answer
        return answers

    def _latest_prediction_answers(self) -> dict[str, Any]:
        expected = {question.question_id for question in self.topic.prediction_questions}
        answers: dict[str, Any] = {}
        legacy_answer: Any = None
        for record in reversed(self.session.prediction_answers):
            if record.question_id in expected and record.question_id not in answers:
                answers[record.question_id] = record.raw_answer
            elif record.question_id == "sce_pred_ion_ioff" and legacy_answer is None:
                legacy_answer = record.raw_answer
        if isinstance(legacy_answer, dict):
            legacy_selected = set(legacy_answer.get("selected", []))
            legacy_reason = str(legacy_answer.get("reason", "") or "")
            for question_id, prefix in (
                ("sce_pred_ion", "Ion "),
                ("sce_pred_ioff", "Ioff "),
            ):
                if question_id in expected and question_id not in answers:
                    selected = next(
                        (
                            option.removeprefix(prefix)
                            for option in legacy_selected
                            if option.startswith(prefix)
                        ),
                        "",
                    )
                    answers[question_id] = {
                        "selected": [selected] if selected else [],
                        "reason": legacy_reason,
                    }
        return answers

    def _resume_evaluation(self) -> None:
        answers = self._latest_observation_answers()
        if len(answers) != len(self.topic.observation_questions) or self.context is None:
            messagebox.showerror(
                "평가 재개 실패",
                "저장된 답변 또는 분석 결과가 부족합니다. 새 세션에서 다시 진행해주세요.",
                parent=self.window,
            )
            return
        self._start_evaluation(answers)

    def _resume_evaluation_if_idle(self) -> None:
        if (
            not self._busy
            and self.session.current_step is LearningStep.OBSERVATION_SUBMITTED
        ):
            self._resume_evaluation()

    def _start_evaluation(self, answers: dict[str, Any]) -> None:
        self.render()

        def task():
            return review_observations(
                self.topic,
                answers,
                self.context,
                self.llm_service,
                prediction_answers=self._latest_prediction_answers(),
            )

        def complete(review) -> None:
            apply_observation_review(self.session, review, self.state_machine)
            if self.session.current_step is LearningStep.FEEDBACK_READY:
                self.state_machine.transition(
                    self.session,
                    LearningStep.SESSION_COMPLETE,
                )
            self.feedback_data = dict(self.session.feedback_snapshot)
            self.summary_data = dict(self.session.summary_snapshot)
            self.learning_view = "explanation"
            self._save()
            self.status_var.set("답변 평가와 맞춤 피드백이 완료되었습니다.")
            self.render()

        def fail_evaluation() -> None:
            if self.session.current_step is LearningStep.OBSERVATION_SUBMITTED:
                self.state_machine.fail(self.session, "learning_feedback_failed")

        self._run_async(task, complete, "학습 피드백 생성 실패", fail_evaluation)

    def _build_feedback(self) -> None:
        container = ttk.Frame(self.body)
        container.pack(fill=tk.BOTH, expand=True)
        results = ttk.Frame(container)
        feedback = ttk.Frame(container, padding=8, width=620)
        results.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        feedback.pack(side=tk.RIGHT, fill=tk.Y)
        feedback.pack_propagate(False)
        self._build_results(results)
        canvas = tk.Canvas(
            feedback,
            highlightthickness=0,
            borderwidth=0,
            yscrollincrement=12,
        )
        scrollbar = ttk.Scrollbar(
            feedback,
            orient=tk.VERTICAL,
            command=canvas.yview,
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cards = ttk.Frame(canvas)
        cards_window = canvas.create_window((0, 0), window=cards, anchor="nw")
        cards.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        def fit_feedback_width(event) -> None:
            content_width = max(260, int(event.width))
            canvas.itemconfigure(cards_window, width=content_width)
            self._set_feedback_wraplength(
                cards,
                max(220, content_width - 48),
            )

        canvas.bind(
            "<Configure>",
            fit_feedback_width,
        )
        self._feedback_cards(cards)
        self._bind_feedback_mousewheel(canvas)

    @staticmethod
    def _bind_feedback_mousewheel(
        canvas: tk.Canvas,
    ) -> None:
        """Scroll the complete feedback column from any widget under the pointer."""

        def scroll_units(units: int) -> str:
            if canvas.winfo_exists():
                canvas.yview_scroll(units, "units")
            return "break"

        def on_mousewheel(event: tk.Event) -> str:
            delta = int(getattr(event, "delta", 0) or 0)
            if delta == 0:
                return "break"
            notches = max(1, abs(delta) // 120)
            return scroll_units((-3 if delta > 0 else 3) * notches)

        def bind_tree(widget: tk.Misc) -> None:
            widget.bind("<MouseWheel>", on_mousewheel, add="+")
            widget.bind("<Button-4>", lambda _event: scroll_units(-3), add="+")
            widget.bind("<Button-5>", lambda _event: scroll_units(3), add="+")
            for child in widget.winfo_children():
                bind_tree(child)

        bind_tree(canvas)

    @staticmethod
    def _set_feedback_wraplength(
        parent: tk.Misc,
        wraplength: int,
    ) -> None:
        for child in parent.winfo_children():
            if isinstance(child, ttk.Label):
                try:
                    current = int(float(child.cget("wraplength")))
                except (TypeError, ValueError, tk.TclError):
                    current = 0
                if current > 0:
                    child.configure(wraplength=wraplength)
            CaseStudyPanel._set_feedback_wraplength(child, wraplength)

    @staticmethod
    def _answer_parts(answer: Any) -> tuple[tuple[str, ...], str]:
        if isinstance(answer, dict):
            selected = answer.get("selected", answer.get("selection", []))
            if isinstance(selected, str):
                selected = (selected,)
            return (
                tuple(str(item).strip() for item in selected if str(item).strip()),
                str(answer.get("reason", "") or "").strip(),
            )
        if isinstance(answer, (list, tuple, set)):
            return tuple(str(item).strip() for item in answer if str(item).strip()), ""
        value = str(answer or "").strip()
        return ((value,) if value else ()), ""

    @staticmethod
    def _question_verdict(
        question: Any,
        selected: tuple[str, ...],
        *,
        phase: str,
    ) -> tuple[str, str]:
        selected_set = set(selected)
        correct_set = set(question.correct_options)
        if not correct_set:
            return "확인 필요", "#4b5563"
        if selected_set == correct_set:
            return (
                "현재 결과와 일치" if phase == "prediction" else "관찰 일치",
                "#15803d",
            )
        if selected_set & correct_set:
            return (
                "현재 결과와 일부 일치"
                if phase == "prediction"
                else "일부 일치",
                "#a16207",
            )
        return (
            "현재 결과와 다름" if phase == "prediction" else "관찰 보완 필요",
            "#4b5563" if phase == "prediction" else "#b91c1c",
        )

    @staticmethod
    def _format_metric_value(value: float | None, unit: str | None) -> str:
        if value is None:
            return "-"
        suffix = f" {unit}" if unit else ""
        return f"{value:.7g}{suffix}"

    def _build_question_actual_results(
        self,
        parent: tk.Misc,
        metric_keys: tuple[str, ...],
        *,
        wraplength: int,
    ) -> None:
        if self.context is None or not metric_keys:
            return
        rows = [
            (name, self.context.electrical_changes.get(name))
            for name in metric_keys
        ]
        rows = [
            (name, change)
            for name, change in rows
            if change is not None and change.available
        ]
        if not rows:
            return
        _caption, baseline_label, comparison_label = format_case_comparison(
            self.topic
        )
        results = ttk.LabelFrame(parent, text="질문과 연결된 실제 결과", padding=6)
        results.pack(fill=tk.X, pady=(5, 0))
        for column, weight in enumerate((1, 2, 2, 2)):
            results.columnconfigure(column, weight=weight)
        for column, heading in enumerate(
            ("지표", baseline_label, comparison_label, "변화")
        ):
            ttk.Label(
                results,
                text=heading,
                font=("TkDefaultFont", 9, "bold"),
                anchor="w",
            ).grid(row=0, column=column, sticky="ew", padx=4, pady=(0, 2))
        direction_labels = {
            "increase": "↑ 증가",
            "decrease": "↓ 감소",
            "stable": "→ 큰 변화 없음",
        }
        for row_index, (name, change) in enumerate(rows, start=1):
            percent = ""
            if change.change_percent is not None:
                percent = f" ({change.change_percent:+.7g}%)"
            values = (
                METRIC_LABELS.get(name, name),
                self._format_metric_value(change.before, change.unit),
                self._format_metric_value(change.after, change.unit),
                f"{direction_labels.get(change.direction, '변화 확인 필요')}{percent}",
            )
            for column, value in enumerate(values):
                ttk.Label(
                    results,
                    text=value,
                    wraplength=max(120, wraplength // 4 - 24),
                    justify=tk.LEFT,
                    anchor="w",
                ).grid(
                    row=row_index,
                    column=column,
                    sticky="ew",
                    padx=4,
                    pady=1,
                )

    def _build_question_review_card(
        self,
        parent: tk.Misc,
        question: Any,
        answer: Any,
        *,
        index: int,
        phase: str,
        wraplength: int,
    ) -> None:
        guide = QUESTION_REVIEW_GUIDES.get(question.question_id, {})
        title = str(guide.get("title", f"질문 {index}"))
        card = ttk.LabelFrame(parent, text=title, padding=8)
        card.pack(fill=tk.X, pady=3)
        ttk.Label(
            card,
            text=question.prompt,
            font=("TkDefaultFont", 9, "bold"),
            wraplength=wraplength,
            justify=tk.LEFT,
        ).pack(anchor="w", fill=tk.X, pady=(0, 4))

        selected, reason = self._answer_parts(answer)
        selected_text = " · ".join(selected) or "답변 없음"
        confirmed_text = " · ".join(question.correct_options) or "확인 필요"
        verdict, verdict_color = self._question_verdict(
            question,
            selected,
            phase=phase,
        )
        comparison = ttk.Frame(card)
        comparison.pack(fill=tk.X)
        for column in range(3):
            comparison.columnconfigure(column, weight=1, uniform="answer_compare")
        for column, (heading, value, color) in enumerate(
            (
                ("내 답변", selected_text, "#1d4ed8"),
                (
                    "현재 Case 결과"
                    if phase == "prediction"
                    else "확인된 결과",
                    confirmed_text,
                    "#111827",
                ),
                ("비교", verdict, verdict_color),
            )
        ):
            cell = ttk.LabelFrame(comparison, text=heading, padding=5)
            cell.grid(
                row=0,
                column=column,
                sticky="nsew",
                padx=(0 if column == 0 else 4, 0),
            )
            ttk.Label(
                cell,
                text=value,
                foreground=color,
                font=("TkDefaultFont", 9, "bold"),
                wraplength=max(150, wraplength // 3 - 38),
                justify=tk.LEFT,
            ).pack(anchor="w", fill=tk.X)

        self._build_question_actual_results(
            card,
            tuple(guide.get("metric_keys", ())),
            wraplength=wraplength,
        )
        if reason:
            reason_frame = ttk.LabelFrame(card, text="내가 작성한 근거", padding=6)
            reason_frame.pack(fill=tk.X, pady=(5, 0))
            ttk.Label(
                reason_frame,
                text=reason,
                foreground="#374151",
                wraplength=max(260, wraplength - 32),
                justify=tk.LEFT,
            ).pack(anchor="w", fill=tk.X)

        model_sections = tuple(guide.get("model_sections", ()))
        if not model_sections:
            model_sections = (
                ("확인 결과", f"확인된 선택은 {confirmed_text}입니다."),
                (
                    "해석 안내",
                    "아래 전체 모범 답안에서 이 결과의 물리적 근거와 해석 범위를 함께 확인하세요.",
                ),
            )
        model = ttk.LabelFrame(card, text="이 질문의 모범 답안", padding=6)
        model.pack(fill=tk.X, pady=(5, 0))
        model_text = "\n".join(
            f"{heading} · {text}" for heading, text in model_sections
        )
        ttk.Label(
            model,
            text=model_text,
            wraplength=max(260, wraplength - 36),
            justify=tk.LEFT,
        ).pack(anchor="w", fill=tk.X)

    def _build_learning_journey_summary(
        self,
        parent: tk.Misc,
        *,
        wraplength: int,
    ) -> None:
        bridge = ttk.LabelFrame(
            parent,
            text="초기 예측 → 실제 결과",
            padding=8,
        )
        bridge.pack(fill=tk.X, pady=(0, 8))
        condition, _baseline, _comparison = format_case_comparison(self.topic)
        ttk.Label(
            bridge,
            text=condition,
            foreground="#4b5563",
            wraplength=max(300, wraplength - 28),
            justify=tk.LEFT,
        ).pack(anchor="w", fill=tk.X, pady=(0, 5))
        prediction_answers = self._latest_prediction_answers()
        for index, question in enumerate(self.topic.prediction_questions, start=1):
            self._build_question_review_card(
                bridge,
                question,
                prediction_answers.get(question.question_id),
                index=index,
                phase="prediction",
                wraplength=max(300, wraplength - 28),
            )

        observations = ttk.LabelFrame(
            parent,
            text="결과를 보고 제출한 관찰",
            padding=8,
        )
        observations.pack(fill=tk.X, pady=(0, 8))
        observation_answers = self._latest_observation_answers()
        for index, question in enumerate(self.topic.observation_questions, start=1):
            self._build_question_review_card(
                observations,
                question,
                observation_answers.get(question.question_id),
                index=index,
                phase="observation",
                wraplength=max(300, wraplength - 28),
            )

    def _build_core_summary(
        self,
        parent: tk.Misc,
        *,
        wraplength: int,
    ) -> None:
        lines = CASE_CORE_SUMMARIES.get(self.topic.topic_id, ())
        if not lines:
            fallback = str(self.feedback_data.get("summary", "") or "").strip()
            lines = (fallback,) if fallback else ()
        if not lines:
            return
        frame = ttk.LabelFrame(parent, text="핵심 정리", padding=10)
        frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(
            frame,
            text="\n".join(f"• {line}" for line in lines),
            wraplength=wraplength,
            justify=tk.LEFT,
        ).pack(anchor="w", fill=tk.X)

    @staticmethod
    def _metric_model_rows(body: str) -> tuple[tuple[str, str, str, str], ...]:
        rows: list[tuple[str, str, str, str]] = []
        pattern = re.compile(
            r"^-\s*(?P<metric>[^:]+):\s*(?P<change>.+?)\s*"
            r"\((?P<direction>[^)]+)\)\.\s*(?P<cause>.+)$"
        )
        for line in body.splitlines():
            match = pattern.match(line.strip())
            if match:
                rows.append(
                    (
                        match.group("metric").strip(),
                        match.group("change").strip(),
                        match.group("direction").strip(),
                        match.group("cause").strip(),
                    )
                )
        return tuple(rows)

    def _build_model_answer_sections(
        self,
        parent: tk.Misc,
        model_answer: str,
        *,
        wraplength: int,
    ) -> None:
        outer = ttk.LabelFrame(parent, text="전체 모범 답안", padding=9)
        outer.pack(fill=tk.X, pady=(0, 8))
        sections = split_model_answer_sections(model_answer)
        if not sections:
            ttk.Label(
                outer,
                text="모범 답안을 구성할 수 있는 분석 결과가 부족합니다.",
                wraplength=wraplength,
                justify=tk.LEFT,
            ).pack(anchor="w", fill=tk.X)
            return
        for title, body in sections:
            section = ttk.LabelFrame(outer, text=title, padding=8)
            section.pack(fill=tk.X, pady=4)
            metric_rows = (
                self._metric_model_rows(body)
                if title == "전기적 파라미터별 변화와 원인"
                else ()
            )
            if not metric_rows:
                ttk.Label(
                    section,
                    text=body,
                    wraplength=max(260, wraplength - 36),
                    justify=tk.LEFT,
                ).pack(anchor="w", fill=tk.X)
                continue
            for column, weight in enumerate((1, 2, 1, 4)):
                section.columnconfigure(column, weight=weight)
            for column, heading in enumerate(
                ("지표", "실제 변화", "방향", "물리적 설명")
            ):
                ttk.Label(
                    section,
                    text=heading,
                    font=("TkDefaultFont", 9, "bold"),
                    anchor="w",
                ).grid(row=0, column=column, sticky="ew", padx=5, pady=(0, 4))
            direction_labels = {
                "increase": "증가",
                "decrease": "감소",
                "stable": "큰 변화 없음",
            }
            for row_index, parsed_row in enumerate(metric_rows, start=1):
                metric, actual_change, direction, cause = parsed_row
                if self.context is not None:
                    matching_changes = (
                        self.context.electrical_changes.get(name)
                        for name, label in METRIC_LABELS.items()
                        if label == metric
                    )
                    current_change = next(
                        (
                            change
                            for change in matching_changes
                            if change is not None and change.available
                        ),
                        None,
                    )
                    if current_change is not None:
                        actual_change = (
                            f"{self._format_metric_value(current_change.before, current_change.unit)}"
                            f" → {self._format_metric_value(current_change.after, current_change.unit)}"
                        )
                        direction = direction_labels.get(
                            current_change.direction,
                            direction,
                        )
                row = (metric, actual_change, direction, cause)
                for column, value in enumerate(row):
                    ttk.Label(
                        section,
                        text=value,
                        wraplength=(
                            max(220, wraplength // 2 - 80)
                            if column == 3
                            else max(100, wraplength // 7)
                        ),
                        justify=tk.LEFT,
                        anchor="w",
                    ).grid(
                        row=row_index,
                        column=column,
                        sticky="new",
                        padx=5,
                        pady=4,
                    )

    @staticmethod
    def _humanize_feedback_line(line: Any) -> str:
        value = str(line or "").strip()
        for concept_id, label in CONCEPT_FEEDBACK_LABELS.items():
            value = value.replace(concept_id, label)
        return value

    @staticmethod
    def _focus_is_actionable(value: Any) -> bool:
        text = str(value or "").strip()
        return bool(text) and "없음" not in text

    def _build_personalized_feedback(
        self,
        parent: tk.Misc,
        *,
        wraplength: int,
        show_summary_line: bool,
    ) -> None:
        data = self.feedback_data
        outer = ttk.LabelFrame(parent, text="내 학습 피드백", padding=9)
        outer.pack(fill=tk.X, pady=(0, 8))
        headline = str(data.get("headline", "") or "").strip()
        if show_summary_line and headline:
            ttk.Label(
                outer,
                text=headline,
                font=("TkDefaultFont", 10, "bold"),
                wraplength=max(260, wraplength - 24),
                justify=tk.LEFT,
            ).pack(anchor="w", fill=tk.X, pady=(0, 7))
        columns = ttk.Frame(outer)
        columns.pack(fill=tk.X)
        columns.columnconfigure(0, weight=1, uniform="personal_feedback")
        columns.columnconfigure(1, weight=1, uniform="personal_feedback")
        feedback_groups = (
            ("잘 이해한 부분", data.get("positive_feedback", [])),
            ("보완할 부분", data.get("corrections", [])),
        )
        for column, (title, raw_lines) in enumerate(feedback_groups):
            frame = ttk.LabelFrame(columns, text=title, padding=8)
            frame.grid(
                row=0,
                column=column,
                sticky="nsew",
                padx=(0 if column == 0 else 4, 4 if column == 0 else 0),
            )
            lines = [
                self._humanize_feedback_line(line)
                for line in raw_lines
                if str(line or "").strip()
            ]
            text = "\n".join(f"• {line}" for line in lines)
            if not text:
                text = (
                    "• 확인된 이해 항목이 없습니다."
                    if column == 0
                    else "• 추가 보완 사항 없음"
                )
            ttk.Label(
                frame,
                text=text,
                wraplength=max(180, wraplength // 2 - 42),
                justify=tk.LEFT,
            ).pack(anchor="w", fill=tk.X)

        focus_items = []
        curve_focus = data.get("curve_focus", "")
        field_focus = data.get("field_focus", "")
        if self._focus_is_actionable(curve_focus):
            focus_items.append(("I–V Curve에서 확인", str(curve_focus).strip()))
        if self._focus_is_actionable(field_focus):
            focus_items.append(("Field Map에서 확인", str(field_focus).strip()))
        if not focus_items:
            return
        focus_frame = ttk.LabelFrame(outer, text="다시 확인할 근거", padding=8)
        focus_frame.pack(fill=tk.X, pady=(8, 0))
        for index, (title, text) in enumerate(focus_items):
            row = ttk.Frame(focus_frame)
            row.pack(fill=tk.X, pady=(0 if index == 0 else 5, 0))
            ttk.Label(
                row,
                text=title,
                font=("TkDefaultFont", 9, "bold"),
                width=20,
                anchor="w",
            ).pack(side=tk.LEFT, anchor="n")
            ttk.Label(
                row,
                text=text,
                wraplength=max(240, wraplength - 210),
                justify=tk.LEFT,
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _feedback_cards(
        self,
        parent: tk.Misc,
        *,
        wraplength: int = 540,
        show_headline: bool = True,
    ) -> None:
        data = self.feedback_data
        if show_headline:
            ttk.Label(
                parent,
                text=data.get("headline", "학습 피드백"),
                font=("TkDefaultFont", 11, "bold"),
                wraplength=wraplength,
            ).pack(anchor="w", pady=(0, 6))
        model_answer = str(data.get("model_answer", "") or "").strip()
        if not model_answer and self.context is not None:
            model_answer = build_grounded_model_answer(
                self.topic,
                self.context,
            )
        self._build_model_answer_sections(
            parent,
            model_answer,
            wraplength=wraplength,
        )
        self._build_personalized_feedback(
            parent,
            wraplength=wraplength,
            show_summary_line=not show_headline,
        )

    def _build_complete(self) -> None:
        notebook = ttk.Notebook(self.body)
        notebook.pack(fill=tk.BOTH, expand=True)
        summary_tab = ttk.Frame(notebook)
        curve_tab = ttk.Frame(notebook)
        field_tab = ttk.Frame(notebook)
        chat_tab = ttk.Frame(notebook)
        notebook.add(summary_tab, text="학습 요약")
        notebook.add(curve_tab, text="I–V Curve")
        notebook.add(field_tab, text="Field Map")
        notebook.add(chat_tab, text="AI 자유 질문")
        tab_ids = {
            notebook.tab(tab_id, "text"): tab_id for tab_id in notebook.tabs()
        }
        if self.completion_view_tab in tab_ids:
            notebook.select(tab_ids[self.completion_view_tab])

        def remember_tab(_event=None) -> None:
            selected = notebook.select()
            if selected:
                selected_label = notebook.tab(selected, "text")
                self.completion_view_tab = selected_label
                remembered = {"completion_view_tab": selected_label}
                if selected_label in {
                    "I–V Curve",
                    "Field Map",
                    "AI 자유 질문",
                }:
                    self.result_view_tab = selected_label
                    remembered["result_view_tab"] = selected_label
                self.session.remember_ui(**remembered)
                self._save(refresh_controls=False)

        notebook.bind("<<NotebookTabChanged>>", remember_tab)
        canvas = tk.Canvas(
            summary_tab,
            highlightthickness=0,
            borderwidth=0,
            yscrollincrement=12,
        )
        scrollbar = ttk.Scrollbar(
            summary_tab,
            orient=tk.VERTICAL,
            command=canvas.yview,
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        box = ttk.Frame(canvas, padding=20)
        box_window = canvas.create_window((0, 0), window=box, anchor="nw")
        box.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        def fit_summary_width(event) -> None:
            content_width = max(360, int(event.width))
            canvas.itemconfigure(box_window, width=content_width)
            self._set_feedback_wraplength(box, max(300, content_width - 48))

        canvas.bind("<Configure>", fit_summary_width)
        ttk.Label(
            box,
            text=self.summary_data.get("headline", f"{self.topic.title} 완료"),
            font=("TkDefaultFont", 12, "bold"),
        ).pack(anchor="w")
        ttk.Separator(box).pack(fill=tk.X, pady=12)
        self._build_core_summary(box, wraplength=820)
        self._build_learning_journey_summary(box, wraplength=820)
        self._feedback_cards(
            box,
            wraplength=820,
            show_headline=False,
        )
        curve_view = ttk.Frame(curve_tab)
        parameter_caption, _baseline_label, _comparison_label = (
            format_case_comparison(self.topic)
        )
        parameters = ttk.LabelFrame(
            curve_tab,
            text=parameter_caption,
            padding=5,
            width=COMPACT_PARAMETER_PANEL_WIDTH,
        )
        curve_view.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        parameters.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 0))
        parameters.pack_propagate(False)
        self._build_curve_view(curve_view)
        self._build_parameter_table(parameters, compact=True)
        self._build_field_view(field_tab)
        self._build_chat(chat_tab)
        self._bind_feedback_mousewheel(canvas)

    def _new_session(self) -> None:
        if self._busy:
            return
        self.session = LearningSession.create(self.topic)
        self._restore_session_snapshots()
        self._save()
        self.show_cover = False
        self.status_var.set(
            "새 학습 세션을 시작했습니다. 이전 세션은 저장 목록에 유지됩니다."
        )
        self.render()

    def _build_error(self) -> None:
        box = ttk.LabelFrame(self.body, text="학습 흐름 복구", padding=20)
        box.pack(expand=True)
        ttk.Label(box, text="이전 처리 단계에서 오류가 발생했습니다.", font=("TkDefaultFont", 11, "bold")).pack()
        ttk.Label(box, text=f"오류 코드: {self.session.error_code or 'unknown'}").pack(pady=8)
        ttk.Label(
            box,
            text=format_error_guidance(
                self.session.error_code,
                self.session.recovery_step,
            ),
            wraplength=620,
            justify=tk.LEFT,
            foreground="#4b5563",
        ).pack(pady=(0, 10))
        ttk.Button(box, text="이전 단계에서 다시 실행", command=self._retry_error).pack(fill=tk.X)

    def _retry_error(self) -> None:
        self.state_machine.recover(self.session)
        self._save()
        if self.session.current_step == LearningStep.SIMULATION_RUNNING:
            self._start_simulation(use_session_transition=False)
        elif self.session.current_step == LearningStep.OBSERVATION_SUBMITTED:
            self._resume_evaluation()
        else:
            self.render()
