from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any, Callable

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from backend.learning import (
    LearningAnalysisContext,
    LearningLLMService,
    LearningSession,
    LearningStateMachine,
    LearningStep,
    audit_learning_session,
    apply_observation_review,
    load_topic,
    review_observations,
)
from backend.learning.experiment_runner import LearningExperimentResult, LearningExperimentRunner
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
    "external_timeout": "Groq 시간 초과",
    "external_validation_failed": "Groq 응답 검증 실패",
    "external_request_failed": "Groq 요청 실패",
    "external_response_unavailable": "Groq 응답 사용 불가",
    "external_network_error": "Groq 네트워크 연결 실패",
    "external_provider_error": "Groq 서비스 오류",
    "external_http_400": "Groq HTTP 400 · 요청 형식 또는 모델 호환성 오류",
    "external_http_401": "Groq HTTP 401 · API 키 인증 실패",
    "external_http_403": "Groq HTTP 403 · API 접근 권한 부족",
    "external_http_404": "Groq HTTP 404 · 모델 또는 API 경로 없음",
    "external_http_413": "Groq HTTP 413 · 요청 크기 초과",
    "external_http_422": "Groq HTTP 422 · 요청 내용 처리 불가",
    "external_http_429": "Groq HTTP 429 · 요청 한도 초과",
    "external_http_500": "Groq HTTP 500 · 서비스 내부 오류",
    "external_http_502": "Groq HTTP 502 · 게이트웨이 오류",
    "external_http_503": "Groq HTTP 503 · 서비스 일시 중단",
    "external_http_504": "Groq HTTP 504 · 게이트웨이 시간 초과",
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
        "저장된 예측 답변을 유지한 채 700 nm/300 nm 실험을 다시 실행합니다."
    ),
}


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


def format_followup_metadata(turn: Any) -> tuple[str, str]:
    source = getattr(turn, "source", "local")
    fallback = getattr(turn, "fallback_reason", None)
    if source == "external_llm":
        engine = "Groq LLM"
    elif fallback:
        engine = "로컬 fallback"
    else:
        engine = "로컬 튜터"
    labels = [
        engine,
        QUESTION_TYPE_LABELS.get(
            getattr(turn, "question_type", ""),
            getattr(turn, "question_type", "분류 없음"),
        ),
        RELEVANCE_LABELS.get(
            getattr(turn, "relevance_to_case", "related"),
            getattr(turn, "relevance_to_case", "related"),
        ),
    ]
    if getattr(turn, "uses_current_result", False):
        labels.append("현재 결과 사용")
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
        details.append("근거: " + ", ".join(evidence))
    if theory:
        details.append("이론: " + ", ".join(theory))
    if fallback:
        details.append("fallback: " + FALLBACK_LABELS.get(fallback, fallback))
    intent = dict(getattr(turn, "interpreted_intent", {}) or {})
    if intent:
        details.append(
            "의도: "
            + str(intent.get("intent", "-"))
            + " / "
            + str(intent.get("answer_structure", "-"))
        )
    interpretation_source = str(
        getattr(turn, "interpretation_source", "") or ""
    )
    if interpretation_source == "deterministic_fallback":
        details.append("질문 해석: Python 복구")
    warnings = tuple(getattr(turn, "pipeline_warnings", ()) or ())
    if warnings:
        details.append("파이프라인: " + ", ".join(warnings))
    fallback_detail = getattr(turn, "fallback_detail", None)
    if fallback_detail:
        details.append("실패 코드: " + str(fallback_detail))
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
    level = str(
        getattr(turn, "explanation_level", "foundational")
        or "foundational"
    )
    level_labels = {
        "foundational": "기초 연결",
        "intermediate": "메커니즘 연결",
        "advanced": "심화·전이",
    }
    if level in level_labels:
        details.append("설명 수준: " + level_labels[level])
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
        self.topic = load_topic("sce_channel_length")
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
        self._busy = False
        self._plot_canvases: list[FigureCanvasTkAgg] = []
        self.field_display_var = tk.StringVar(value="Potential")
        self.result_view_tab = "I–V Curve"
        self.completion_view_tab = "학습 요약"
        self.status_var = tk.StringVar(value="")
        self.step_var = tk.StringVar(value="")
        self.tutor_mode_var = tk.StringVar(value="")
        self.session_choice_var = tk.StringVar(value="")
        self.session_meta_var = tk.StringVar(value="")
        self._session_choice_ids: dict[str, str] = {}
        self._update_tutor_mode()

        self.session = self._restore_or_create_session()
        self._restore_session_snapshots()

        header = ttk.Frame(self, padding=(12, 9))
        header.pack(fill=tk.X)
        ttk.Label(header, text=self.topic.title, font=("TkDefaultFont", 12, "bold")).pack(side=tk.LEFT)
        ttk.Label(header, textvariable=self.step_var, foreground="#1d4ed8").pack(side=tk.RIGHT)

        session_bar = ttk.Frame(self, padding=(12, 0, 12, 6))
        session_bar.pack(fill=tk.X)
        ttk.Label(session_bar, text="저장 세션").pack(side=tk.LEFT)
        self.session_choice_box = ttk.Combobox(
            session_bar,
            textvariable=self.session_choice_var,
            state="readonly",
            width=49,
        )
        self.session_choice_box.pack(side=tk.LEFT, padx=(5, 4))
        self.resume_session_button = ttk.Button(
            session_bar,
            text="계속하기",
            command=self._resume_selected_session,
        )
        self.resume_session_button.pack(side=tk.LEFT, padx=2)
        self.new_session_button = ttk.Button(
            session_bar,
            text="새 세션",
            command=self._new_session,
        )
        self.new_session_button.pack(side=tk.LEFT, padx=2)
        self.reset_session_button = ttk.Button(
            session_bar,
            text="현재 세션 초기화",
            command=self._reset_current_session,
        )
        self.reset_session_button.pack(side=tk.LEFT, padx=2)
        self.delete_session_button = ttk.Button(
            session_bar,
            text="선택 세션 삭제",
            command=self._delete_selected_session,
        )
        self.delete_session_button.pack(side=tk.LEFT, padx=2)
        ttk.Label(
            session_bar,
            textvariable=self.session_meta_var,
            foreground="#4b5563",
        ).pack(side=tk.RIGHT)
        self._refresh_session_controls()

        self.progress = ttk.Progressbar(self, maximum=len(STEP_ORDER), mode="determinate")
        self.progress.pack(fill=tk.X, padx=12)
        ttk.Label(self, textvariable=self.status_var, foreground="#4b5563").pack(fill=tk.X, padx=12, pady=(4, 0))
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
            "Case Study 전용 Groq LLM 연결됨"
            if self._provider_name == "external_llm"
            else "Case Study Groq 미연결 · 로컬 fallback"
        )
        self.tutor_mode_var.set(mode)

    def _restore_session_snapshots(self) -> None:
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

    @staticmethod
    def _session_label(session: LearningSession) -> str:
        updated = session.updated_at.replace("T", " ")[:16]
        step = STEP_LABELS.get(session.current_step, session.current_step.value)
        return f"{updated} · {step} · {session.session_id[:8]}"

    def _refresh_session_controls(self) -> None:
        if not hasattr(self, "session_choice_box"):
            return
        try:
            sessions = [
                item
                for item in self.repository.list_sessions()
                if item.topic_id == self.topic.topic_id
            ]
        except SessionStorageError:
            sessions = [self.session]
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
        for button in (
            self.resume_session_button,
            self.new_session_button,
            self.reset_session_button,
            self.delete_session_button,
        ):
            button.configure(state=state)

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
                if item.topic_id == self.topic.topic_id
            ]
        except SessionStorageError:
            messagebox.showerror(
                "세션 삭제 실패",
                "선택한 학습 세션을 삭제하지 못했습니다.",
                parent=self.window,
            )
            return
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
        replacement = LearningSession.create(self.topic)
        replacement.session_id = session_id
        self.session = replacement
        self._restore_session_snapshots()
        self._save()
        self.status_var.set("현재 세션을 처음 단계로 초기화했습니다.")
        self.render()

    def _restore_or_create_session(self) -> LearningSession:
        try:
            matching = [
                item for item in self.repository.list_sessions()
                if item.topic_id == self.topic.topic_id
            ]
        except SessionStorageError:
            matching = []
        if matching:
            return matching[0]
        session = LearningSession.create(self.topic)
        self._save(session)
        return session

    def _save(self, session: LearningSession | None = None) -> None:
        try:
            self.repository.save(session or self.session)
            self._refresh_session_controls()
        except SessionStorageError:
            self.status_var.set("학습 기록을 저장하지 못했습니다. 현재 실행에서는 계속 진행할 수 있습니다.")

    def _set_step_header(self) -> None:
        step = self.session.current_step
        self.step_var.set(STEP_LABELS.get(step, step.value))
        value = STEP_ORDER.index(step) + 1 if step in STEP_ORDER else 0
        self.progress.configure(value=value)

    def _clear_body(self) -> None:
        self.answer_collectors.clear()
        self._plot_canvases.clear()
        for widget in self.body.winfo_children():
            widget.destroy()

    def render(self) -> None:
        self._clear_body()
        self._set_step_header()
        step = self.session.current_step
        if step in {LearningStep.INTRODUCTION, LearningStep.BASELINE_SETUP}:
            self._build_introduction()
        elif step == LearningStep.PREDICTION_QUESTION:
            self._build_prediction()
        elif step in {LearningStep.PREDICTION_SUBMITTED, LearningStep.SIMULATION_RUNNING, LearningStep.OBSERVATION_SUBMITTED}:
            self._build_loading()
        elif step == LearningStep.RESULT_READY:
            self._build_result_ready()
        elif step == LearningStep.OBSERVATION_QUESTION:
            self._build_observation()
        elif step == LearningStep.FEEDBACK_READY:
            self._build_feedback()
        elif step == LearningStep.NEXT_EXPERIMENT:
            self._build_next_action()
        elif step == LearningStep.SESSION_COMPLETE:
            self._build_complete()
        elif step == LearningStep.ERROR:
            self._build_error()

    def _build_introduction(self) -> None:
        left = ttk.LabelFrame(self.body, text="학습 목표", padding=14)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        ttk.Label(left, text=self.topic.description, wraplength=650, justify=tk.LEFT).pack(anchor="w", pady=(0, 10))
        for objective in self.topic.learning_objectives:
            ttk.Label(left, text=f"• {objective}", wraplength=650, justify=tk.LEFT).pack(anchor="w", pady=3)
        ttk.Label(
            left,
            text="결과를 보기 전에 먼저 변화를 예측하고, 그래프와 Field Map에서 근거를 찾습니다.",
            foreground="#4b5563",
            wraplength=650,
        ).pack(anchor="w", pady=(14, 0))

        right = ttk.LabelFrame(self.body, text="기준·비교 조건", padding=14)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 0))
        tree = ttk.Treeview(right, columns=("parameter", "baseline", "comparison"), show="headings", height=5)
        for name, title, width in (
            ("parameter", "Parameter", 110), ("baseline", "Baseline", 110), ("comparison", "Comparison", 110),
        ):
            tree.heading(name, text=title)
            tree.column(name, width=width, anchor=tk.CENTER)
        for name in ("L", "T", "B", "SD", "LDD"):
            tree.insert("", tk.END, values=(name, f"{self.topic.baseline_conditions[name]:g}", f"{self.topic.comparison_conditions[name]:g}"))
        tree.pack()
        ttk.Label(right, text="한 번에 L만 변경합니다.", foreground="#1d4ed8").pack(pady=(10, 8))
        ttk.Button(right, text="사전 예측 시작", command=self._begin_prediction).pack(fill=tk.X)

    def _begin_prediction(self) -> None:
        if self.session.current_step == LearningStep.INTRODUCTION:
            self.state_machine.transition(self.session, LearningStep.BASELINE_SETUP)
        self.state_machine.transition(self.session, LearningStep.PREDICTION_QUESTION)
        self._save()
        self.render()

    def _build_question(self, parent: tk.Misc, question) -> Callable[[], Any]:
        frame = ttk.LabelFrame(parent, text=question.prompt, padding=10)
        frame.pack(fill=tk.X, pady=5)
        if question.type.startswith("single_select"):
            selected = tk.StringVar(value="")
            for option in question.options:
                ttk.Radiobutton(frame, text=option, value=option, variable=selected).pack(anchor="w", pady=2)
            get_selected = lambda: [selected.get()] if selected.get() else []
        else:
            variables = {option: tk.BooleanVar(value=False) for option in question.options}
            for option, variable in variables.items():
                ttk.Checkbutton(frame, text=option, variable=variable).pack(anchor="w", pady=2)
            get_selected = lambda: [option for option, variable in variables.items() if variable.get()]
        reason = None
        if question.reason_required:
            ttk.Label(frame, text="근거").pack(anchor="w", pady=(7, 2))
            reason = tk.Text(frame, height=3, wrap=tk.WORD)
            reason.pack(fill=tk.X)

        def collect() -> dict[str, Any]:
            return {
                "selected": get_selected(),
                "reason": reason.get("1.0", tk.END).strip() if reason else "",
            }

        return collect

    def _build_prediction(self) -> None:
        wrapper = ttk.Frame(self.body)
        wrapper.pack(fill=tk.BOTH, expand=True)
        ttk.Label(wrapper, text="결과를 실행하기 전에 예상해보세요.", font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        for question in self.topic.prediction_questions:
            self.answer_collectors[question.question_id] = self._build_question(wrapper, question)
        ttk.Button(wrapper, text="예측 제출 후 모델 실행", command=self._submit_prediction).pack(anchor="e", pady=12)

    def _collect_answers(self) -> dict[str, Any] | None:
        answers = {question_id: collect() for question_id, collect in self.answer_collectors.items()}
        if any(not answer["selected"] for answer in answers.values()):
            messagebox.showinfo("답변 필요", "각 질문에서 하나 이상의 답을 선택해주세요.", parent=self.window)
            return None
        return answers

    def _submit_prediction(self) -> None:
        answers = self._collect_answers()
        if answers is None:
            return
        self.state_machine.submit_predictions(self.session, answers)
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
            ttk.Button(
                box,
                text="저장된 답변 평가 계속",
                command=self._resume_evaluation,
            ).pack(fill=tk.X, pady=(12, 0))

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
            self._save()
            self.status_var.set("예측과 분석이 완료되었습니다.")
            self.render()

        self._run_async(task, complete, "Case Study 실행 실패")

    def _build_result_ready(self) -> None:
        self._build_results(self.body)
        ttk.Button(self.body, text="관찰 질문 시작", command=self._begin_observation).pack(anchor="e", pady=(7, 0))

    def _begin_observation(self) -> None:
        self.state_machine.transition(self.session, LearningStep.OBSERVATION_QUESTION)
        self._save()
        self.render()

    def _build_results(self, parent: tk.Misc) -> None:
        pane = ttk.Panedwindow(parent, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True)
        content = ttk.Frame(pane)
        parameters = ttk.LabelFrame(
            pane,
            text="전기적 파라미터 (700 nm → 300 nm)",
            padding=5,
            width=430,
        )
        pane.add(content, weight=4)
        pane.add(parameters, weight=1)
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

        notebook.bind("<<NotebookTabChanged>>", remember_tab)
        if self.result is None:
            for tab in (curve_tab, field_tab):
                ttk.Label(tab, text="저장된 분석 결과가 있습니다. 그래프를 다시 생성하면 시각화할 수 있습니다.").pack(expand=True)
            ttk.Button(curve_tab, text="그래프 다시 생성", command=lambda: self._start_simulation(use_session_transition=False)).pack(pady=8)
        else:
            figure = Figure(figsize=(9, 5), dpi=90)
            render_curve_figure(figure, [
                ("Baseline", self.result.baseline.idvd, self.result.baseline.idvg),
                ("Comparison", self.result.comparison.idvd, self.result.comparison.idvg),
            ])
            canvas = FigureCanvasTkAgg(figure, master=curve_tab)
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            canvas.draw_idle()
            self._plot_canvases.append(canvas)

            controls = ttk.Frame(field_tab, padding=5)
            controls.pack(fill=tk.X)
            ttk.Label(controls, text="Display").pack(side=tk.LEFT)
            display_box = ttk.Combobox(
                controls, textvariable=self.field_display_var,
                values=("Potential", "Electric field"), state="readonly", width=18,
            )
            display_box.pack(side=tk.LEFT, padx=5)
            field_figure = Figure(figsize=(9, 5), dpi=90)
            field_canvas = FigureCanvasTkAgg(field_figure, master=field_tab)
            field_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            self._plot_canvases.append(field_canvas)

            def draw_field(_event=None) -> None:
                render_model_field_comparison(
                    field_figure,
                    [("Baseline", self.result.baseline.field_map), ("Comparison", self.result.comparison.field_map)],
                    self.field_display_var.get(),
                    "Auto",
                    "Robust 1-99%",
                )
                field_canvas.draw_idle()

            display_box.bind("<<ComboboxSelected>>", draw_field)
            draw_field()
        self._build_parameter_table(parameters, compact=True)
        self._build_chat(chat_tab)

    def _build_parameter_table(self, parent: tk.Misc, *, compact: bool = False) -> None:
        if self.context is None:
            ttk.Label(parent, text="분석 문맥을 복원할 수 없습니다.").pack(expand=True)
            return
        columns = (
            ("metric", "Metric", 115),
            ("before", "700 nm", 92),
            ("after", "300 nm", 92),
            ("direction", "변화", 62),
        ) if compact else (
            ("metric", "Metric", 130),
            ("before", "Baseline", 140),
            ("after", "Comparison", 140),
            ("direction", "Direction", 100),
            ("unit", "Unit", 100),
        )
        tree = ttk.Treeview(
            parent,
            columns=tuple(item[0] for item in columns),
            show="headings",
            height=max(10, sum(
                1 for change in self.context.electrical_changes.values()
                if change.available
            )),
        )
        for name, title, width in columns:
            tree.heading(name, text=title)
            tree.column(name, width=width, anchor=tk.CENTER)
        for name, change in self.context.electrical_changes.items():
            if not change.available:
                continue
            metric = f"{name} ({change.unit})" if compact and change.unit else name
            values = (
                metric,
                f"{change.before:.6g}",
                f"{change.after:.6g}",
                {"increase": "↑", "decrease": "↓", "stable": "→"}.get(
                    change.direction,
                    "?",
                ),
            ) if compact else (
                name,
                f"{change.before:.6g}",
                f"{change.after:.6g}",
                change.direction,
                change.unit or "",
            )
            tree.insert("", tk.END, values=(
                *values,
            ))
        tree.pack(fill=tk.BOTH, expand=True)

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
            if turn.next_learning_question:
                history.insert(
                    tk.END,
                    f"이어서 생각해 볼 질문: {turn.next_learning_question}\n",
                    "detail",
                )
        history.configure(state=tk.DISABLED)
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
                }
                for turn in self.session.followup_history
            ]

            def complete(response) -> None:
                LearningLLMService.record_followup(self.session, text, response)
                self._save()
                if response.source == "external_llm":
                    status = "Groq LLM 답변이 생성되었습니다."
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

    def _build_observation(self) -> None:
        pane = ttk.Panedwindow(self.body, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True)
        results = ttk.Frame(pane)
        questions = ttk.Frame(pane, padding=8, width=390)
        pane.add(results, weight=3)
        pane.add(questions, weight=2)
        self._build_results(results)
        ttk.Label(questions, text="그래프와 Field Map을 관찰한 뒤 답하세요.", font=("TkDefaultFont", 10, "bold"), wraplength=360).pack(anchor="w")
        for question in self.topic.observation_questions:
            self.answer_collectors[question.question_id] = self._build_question(questions, question)
        ttk.Button(questions, text="관찰 답변 제출", command=self._submit_observation).pack(fill=tk.X, pady=8)

    def _submit_observation(self) -> None:
        answers = self._collect_answers()
        if answers is None or self.context is None:
            return
        self.state_machine.submit_observations(self.session, answers)
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
        for record in reversed(self.session.prediction_answers):
            if record.question_id in expected and record.question_id not in answers:
                answers[record.question_id] = record.raw_answer
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
            self.feedback_data = dict(self.session.feedback_snapshot)
            self.summary_data = dict(self.session.summary_snapshot)
            self._save()
            self.status_var.set("답변 평가와 맞춤 피드백이 완료되었습니다.")
            self.render()

        def fail_evaluation() -> None:
            if self.session.current_step is LearningStep.OBSERVATION_SUBMITTED:
                self.state_machine.fail(self.session, "learning_feedback_failed")

        self._run_async(task, complete, "학습 피드백 생성 실패", fail_evaluation)

    def _build_feedback(self) -> None:
        pane = ttk.Panedwindow(self.body, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True)
        results = ttk.Frame(pane)
        feedback = ttk.Frame(pane, padding=8, width=420)
        pane.add(results, weight=3)
        pane.add(feedback, weight=2)
        self._build_results(results)
        self._feedback_cards(feedback)
        ttk.Button(feedback, text="추천 행동 진행", command=self._take_next_action).pack(fill=tk.X, pady=(8, 3))
        ttk.Button(feedback, text="현재 Case 완료", command=self._complete).pack(fill=tk.X)

    def _feedback_cards(self, parent: tk.Misc) -> None:
        data = self.feedback_data
        ttk.Label(parent, text=data.get("headline", "학습 피드백"), font=("TkDefaultFont", 11, "bold"), wraplength=390).pack(anchor="w", pady=(0, 6))
        sections = (
            ("잘 이해한 부분", data.get("positive_feedback", [])),
            ("보완할 부분", data.get("corrections", [])),
            ("Curve 관찰 위치", [data.get("curve_focus", "")]),
            ("Field Map 관찰 위치", [data.get("field_focus", "")]),
            ("핵심 정리", [data.get("summary", "")]),
        )
        for title, lines in sections:
            frame = ttk.LabelFrame(parent, text=title, padding=7)
            frame.pack(fill=tk.X, pady=3)
            text = "\n".join(f"• {line}" for line in lines if line) or "• 추가 보완 사항 없음"
            ttk.Label(frame, text=text, wraplength=370, justify=tk.LEFT).pack(anchor="w")
        action = self.session.recommended_next_action or "-"
        ttk.Label(parent, text=f"추천 다음 행동: {action}", foreground="#1d4ed8", wraplength=390).pack(anchor="w", pady=(7, 0))

    def _take_next_action(self) -> None:
        action = self.session.recommended_next_action
        self.state_machine.transition(self.session, LearningStep.NEXT_EXPERIMENT)
        if action == "retry_sce_prediction":
            self.state_machine.transition(self.session, LearningStep.PREDICTION_QUESTION)
        elif action == "review_sce_theory" and self.on_open_theory:
            self.on_open_theory()
        elif action == "observe_potential_map":
            self.field_display_var.set("Potential")
        self._save()
        self.render()

    def _build_next_action(self) -> None:
        pane = ttk.Panedwindow(self.body, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True)
        results, summary = ttk.Frame(pane), ttk.Frame(pane, padding=12, width=400)
        pane.add(results, weight=3)
        pane.add(summary, weight=2)
        self._build_results(results)
        ttk.Label(summary, text=self.summary_data.get("headline", "학습 요약"), font=("TkDefaultFont", 11, "bold"), wraplength=370).pack(anchor="w")
        ttk.Label(summary, text=self.summary_data.get("summary", ""), wraplength=370, justify=tk.LEFT).pack(anchor="w", pady=10)
        ttk.Label(summary, text=f"선택한 행동: {self.session.recommended_next_action}", foreground="#1d4ed8").pack(anchor="w")
        ttk.Button(summary, text="Case 학습 완료", command=self._complete).pack(fill=tk.X, pady=(15, 0))

    def _complete(self) -> None:
        if self.session.current_step in {LearningStep.FEEDBACK_READY, LearningStep.NEXT_EXPERIMENT}:
            self.state_machine.transition(self.session, LearningStep.SESSION_COMPLETE)
        self._save()
        self.render()

    def _build_complete(self) -> None:
        notebook = ttk.Notebook(self.body)
        notebook.pack(fill=tk.BOTH, expand=True)
        box = ttk.Frame(notebook, padding=20)
        results = ttk.Frame(notebook)
        chat = ttk.Frame(notebook)
        notebook.add(box, text="학습 요약")
        notebook.add(results, text="결과 다시 보기")
        notebook.add(chat, text="AI 자유 질문")
        tab_ids = {
            notebook.tab(tab_id, "text"): tab_id for tab_id in notebook.tabs()
        }
        if self.completion_view_tab in tab_ids:
            notebook.select(tab_ids[self.completion_view_tab])

        def remember_tab(_event=None) -> None:
            selected = notebook.select()
            if selected:
                self.completion_view_tab = notebook.tab(selected, "text")

        notebook.bind("<<NotebookTabChanged>>", remember_tab)
        ttk.Label(box, text=self.summary_data.get("headline", "Channel Length Case 완료"), font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        ttk.Label(box, text=self.summary_data.get("summary", ""), wraplength=850, justify=tk.LEFT).pack(anchor="w", pady=10)
        understood = self.summary_data.get("understood_concepts", self.session.completed_concepts)
        review = self.summary_data.get("needs_review", self.session.remaining_concepts)
        ttk.Label(box, text="확인한 개념: " + (", ".join(understood) or "-"), wraplength=850).pack(anchor="w", pady=3)
        ttk.Label(box, text="복습할 개념: " + (", ".join(review) or "-"), wraplength=850).pack(anchor="w", pady=3)
        ttk.Label(
            box,
            text="완료 후에도 ‘결과 다시 보기’와 ‘AI 자유 질문’에서 학습을 이어갈 수 있습니다.",
            foreground="#1d4ed8",
            wraplength=850,
        ).pack(anchor="w", pady=(10, 0))
        ttk.Button(box, text="새 세션 시작", command=self._new_session).pack(anchor="e", pady=(15, 0))
        self._build_results(results)
        self._build_chat(chat)

    def _new_session(self) -> None:
        if self._busy:
            return
        self.session = LearningSession.create(self.topic)
        self._restore_session_snapshots()
        self._save()
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
