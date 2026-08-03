from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from backend.explanation.errors import ExplanationPipelineError
from backend.explanation.iv_chat import IVChatService
from backend.explanation.providers.external import ProviderHTTPError
from backend.public_presentation import (
    public_ai_failure_message,
    public_source_label,
)
from frontend.visualization.analysis_context import (
    build_analysis_context_status,
    ordered_analysis_indices,
)


FIELD_EXPLANATION_EXCLUDED = {"Mesh", "Abs net doping", "Net doping"}
ANSWER_FONT = ("Malgun Gothic", 9)


class ExplanationPanelMixin:
    """Reusable explanation widgets, background execution, and view history."""

    def _build_explanation_panel(self, parent: ttk.LabelFrame, kind: str) -> None:
        automatic_parent = parent
        if kind in {"curve", "field"}:
            notebook = ttk.Notebook(parent)
            notebook.pack(fill=tk.BOTH, expand=True)
            automatic_parent = ttk.Frame(notebook, padding=(4, 4))
            chat_parent = ttk.Frame(notebook, padding=(4, 4))
            notebook.add(automatic_parent, text="자동 설명")
            notebook.add(chat_parent, text="AI 질문")
            if kind == "curve":
                self._build_iv_chat_panel(chat_parent)
            else:
                self._build_field_chat_panel(chat_parent)
        context_row = ttk.Frame(automatic_parent)
        context_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(context_row, text="비교 기준").pack(side=tk.LEFT)
        baseline_var = tk.StringVar()
        baseline = ttk.Combobox(
            context_row, textvariable=baseline_var, width=11,
            state="readonly",
        )
        baseline.pack(side=tk.LEFT, padx=(5, 0))
        baseline.bind(
            "<<ComboboxSelected>>",
            lambda _event, value=kind: self._analysis_baseline_changed(value),
        )
        context_var = tk.StringVar(value="분석 대상을 선택해 주세요.")
        ttk.Label(
            automatic_parent, textvariable=context_var, anchor="w",
            foreground="#374151", wraplength=315, justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 4))
        self.analysis_baseline_vars[kind] = baseline_var
        self.analysis_baseline_widgets[kind] = baseline
        self.analysis_context_vars[kind] = context_var
        controls = ttk.Frame(automatic_parent); controls.pack(fill=tk.X, pady=(0, 3))
        button = ttk.Button(controls, text="Analyze", command=lambda: self._analyze(kind)); button.pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(controls, text="Copy", command=lambda: self._copy_explanation(kind)).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)
        status = tk.StringVar(
            value=(
                "AI 해설 준비됨"
                if getattr(self, "explanation_llm_available", False)
                else "AI 해설 사용 불가"
            )
        )
        ttk.Label(automatic_parent, textvariable=status, anchor="w").pack(fill=tk.X, pady=(0, 4))
        # Keep the side panel compact so the plots receive most of the window.
        text = ScrolledText(automatic_parent, width=34, height=6, wrap=tk.WORD, font=ANSWER_FONT); text.pack(fill=tk.BOTH, expand=True); text.configure(state=tk.DISABLED)
        self.explanation_buttons[kind] = button; self.explanation_status[kind] = status; self.explanation_texts[kind] = text
        self._refresh_analysis_context(kind)

    def _selected_analysis_indices(self, kind: str) -> tuple[int, ...]:
        if kind == "curve":
            return tuple(
                index for index in range(len(self.curve_configs))
                if index in self.visible_curve_indices
            )
        return tuple(
            index for index in sorted(self.field_selected_indices)
            if index < len(self.curve_configs)
        )

    def _ordered_analysis_indices(self, kind: str) -> tuple[int, ...]:
        return ordered_analysis_indices(
            self._selected_analysis_indices(kind),
            self.analysis_baseline_indices.get(kind),
        )

    def _refresh_analysis_context(self, kind: str) -> None:
        if kind not in getattr(self, "analysis_context_vars", {}):
            return
        selected = self._selected_analysis_indices(kind)
        current = self.analysis_baseline_indices.get(kind)
        if current not in selected:
            current = selected[0] if selected else None
            self.analysis_baseline_indices[kind] = current
        labels = tuple(f"Curve {index + 1}" for index in selected)
        widget = self.analysis_baseline_widgets[kind]
        widget.configure(
            values=labels,
            state=("readonly" if len(selected) > 1 else tk.DISABLED),
        )
        self.analysis_baseline_vars[kind].set(
            f"Curve {current + 1}" if current is not None else ""
        )
        status = build_analysis_context_status(
            selected,
            self.curve_configs,
            preferred_baseline_index=current,
        )
        self.analysis_context_vars[kind].set(
            status.display_text(include_representative=(kind == "field"))
            if status else "분석 대상을 선택해 주세요."
        )

    def _analysis_baseline_changed(self, kind: str) -> None:
        label = self.analysis_baseline_vars[kind].get()
        try:
            index = int(label.removeprefix("Curve ").strip()) - 1
        except ValueError:
            return
        if index not in self._selected_analysis_indices(kind):
            return
        self.analysis_baseline_indices[kind] = index
        self._refresh_analysis_context(kind)
        if kind == "field":
            self.render_field()
        self._restore_explanation(kind)

    def _build_iv_chat_panel(self, parent: ttk.Frame) -> None:
        self.iv_chat_snapshot = None
        self.iv_chat_turns = []
        self.iv_chat_checkpoint = {}
        self.iv_chat_checkpoint_question = None
        self.iv_chat_retry_question = None
        self.iv_chat_status = tk.StringVar(value="첫 질문 시 현재 Curve를 고정합니다.")
        ttk.Label(
            parent, textvariable=self.iv_chat_status, anchor="w",
            foreground="#4b5563", wraplength=315,
        ).pack(fill=tk.X, pady=(0, 4))
        self.iv_chat_history_widget = ScrolledText(
            parent, width=34, height=9, wrap=tk.WORD,
            font=ANSWER_FONT,
        )
        self.iv_chat_history_widget.pack(fill=tk.BOTH, expand=True)
        self.iv_chat_history_widget.configure(state=tk.DISABLED)
        self.iv_chat_input = tk.Text(parent, height=3, wrap=tk.WORD)
        self.iv_chat_input.pack(fill=tk.X, pady=(5, 4))
        self.iv_chat_input.bind(
            "<Control-Return>", lambda _event: self._send_iv_chat()
        )
        actions = ttk.Frame(parent); actions.pack(fill=tk.X)
        self.iv_chat_send_button = ttk.Button(
            actions, text="질문 보내기", command=self._send_iv_chat,
        )
        self.iv_chat_send_button.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.iv_chat_new_button = ttk.Button(
            actions, text="새 대화", command=self._reset_iv_chat,
        )
        self.iv_chat_new_button.pack(side=tk.LEFT, padx=(4, 0))
        self.iv_chat_retry_button = ttk.Button(
            actions,
            text="최근 실패 재시도",
            command=self._retry_iv_chat,
            state=tk.DISABLED,
        )
        self.iv_chat_retry_button.pack(side=tk.LEFT, padx=(4, 0))

    def _iv_curve_signature(self) -> tuple:
        indices = self._ordered_analysis_indices("curve")
        return (
            indices,
            tuple(
                tuple(sorted(self.curve_configs[index].items()))
                for index in indices
            ),
        )

    def _reset_iv_chat(self) -> None:
        self.iv_chat_snapshot = None
        self.iv_chat_turns = []
        self.iv_chat_checkpoint = {}
        self.iv_chat_checkpoint_question = None
        self.iv_chat_retry_question = None
        self._arm_chat_retry("iv", None)
        history = self.iv_chat_history_widget
        history.configure(state=tk.NORMAL)
        history.delete("1.0", tk.END)
        history.configure(state=tk.DISABLED)
        self.iv_chat_status.set("첫 질문 시 현재 Curve를 고정합니다.")

    def _update_iv_chat_view_status(self) -> None:
        snapshot = getattr(self, "iv_chat_snapshot", None)
        if snapshot is None:
            return
        labels = ", ".join(snapshot.curve_labels)
        if snapshot.selection_signature != self._iv_curve_signature():
            self.iv_chat_status.set(
                f"{labels} 스냅샷 기준 · 화면 변경됨 (새 대화로 반영)"
            )
        else:
            self.iv_chat_status.set(f"{labels} 스냅샷 기준")

    def _send_iv_chat(self) -> None:
        question = self.iv_chat_input.get("1.0", tk.END).strip()
        if not question:
            return
        try:
            if self.iv_chat_snapshot is None:
                indices = [
                    index for index in self._ordered_analysis_indices("curve")
                    if index < len(self.curve_results)
                ]
                if not indices:
                    raise ValueError("Select at least one visible I–V curve.")
                results = [self.curve_results[index] for index in indices]
                configs = [dict(self.curve_configs[index]) for index in indices]
                signature = self._iv_curve_signature()
            else:
                results = configs = None
                signature = self.iv_chat_snapshot.selection_signature
        except ValueError:
            messagebox.showinfo(
                "I-V 질문 사용 불가",
                "먼저 분석할 I-V Curve를 생성하고 선택해 주세요.",
                parent=self.window,
            )
            return
        checkpoint = (
            dict(self.iv_chat_checkpoint)
            if self.iv_chat_checkpoint_question == question
            else {}
        )
        history = list(self.iv_chat_turns)
        snapshot = self.iv_chat_snapshot
        self.iv_chat_input.delete("1.0", tk.END)
        self.iv_chat_send_button.configure(state=tk.DISABLED)
        self.iv_chat_new_button.configure(state=tk.DISABLED)
        self.iv_chat_status.set("I–V 질문을 해석하고 있습니다.")

        def worker() -> None:
            try:
                active_snapshot = snapshot
                if active_snapshot is None:
                    active_snapshot = self.iv_chat_service.build_snapshot(
                        results, configs, selection_signature=signature,
                    )
                response = self.iv_chat_service.answer(
                    active_snapshot,
                    question,
                    history=history,
                    intent_checkpoint=checkpoint,
                )
            except Exception as exc:
                self.window.after(
                    0, lambda error=exc: self._iv_chat_failed(error)
                )
            else:
                self.window.after(
                    0,
                    lambda: self._show_iv_chat_response(
                        active_snapshot, question, response,
                    ),
                )
        threading.Thread(target=worker, daemon=True).start()

    def _show_iv_chat_response(self, snapshot, question: str, response) -> None:
        self.iv_chat_snapshot = snapshot
        self.iv_chat_turns.append({
            "question": question,
            "answer": response.answer,
            "source": response.source,
            "comparison_focus": response.diagnostic.get(
                "comparison_focus"
            ),
        })
        self.iv_chat_turns = self.iv_chat_turns[-12:]
        if response.source == "external_error" and response.intent_checkpoint:
            self.iv_chat_checkpoint = dict(response.intent_checkpoint)
            self.iv_chat_checkpoint_question = question
        else:
            self.iv_chat_checkpoint = {}
            self.iv_chat_checkpoint_question = None
        self.iv_chat_retry_question = (
            question if response.source == "external_error" else None
        )
        intent = response.intent.intent if response.intent else "분류 실패"
        engine = public_source_label(response.source)
        block = (
            f"사용자: {question}\n"
            f"AI [{engine} · {intent}]\n{response.answer}"
        )
        if response.suggested_followup:
            block += "\n이어서 생각해 볼 질문: " + response.suggested_followup
        history = self.iv_chat_history_widget
        history.configure(state=tk.NORMAL)
        if history.get("1.0", tk.END).strip():
            history.insert(tk.END, "\n\n")
        history.insert(tk.END, block)
        history.configure(state=tk.DISABLED)
        history.see(tk.END)
        self.iv_chat_send_button.configure(state=tk.NORMAL)
        self.iv_chat_new_button.configure(state=tk.NORMAL)
        self._arm_chat_retry(
            "iv",
            response.diagnostic.get("recommended_retry_after_seconds")
            if response.source == "external_error"
            else None,
            enabled=response.source == "external_error",
        )
        self._update_iv_chat_view_status()

    def _retry_iv_chat(self) -> None:
        question = self.iv_chat_retry_question
        if not question:
            return
        self.iv_chat_input.delete("1.0", tk.END)
        self.iv_chat_input.insert("1.0", question)
        self._send_iv_chat()

    def _iv_chat_failed(self, error: Exception) -> None:
        del error
        self.iv_chat_send_button.configure(state=tk.NORMAL)
        self.iv_chat_new_button.configure(state=tk.NORMAL)
        self.iv_chat_status.set("I–V 질문 처리 실패")
        messagebox.showerror(
            "I–V AI unavailable",
            "질문 처리 중 내부 오류가 발생했습니다. 현재 Curve 상태를 확인해 주세요.",
            parent=self.window,
        )

    def _build_field_chat_panel(self, parent: ttk.Frame) -> None:
        self.field_chat_snapshot = None
        self.field_chat_turns = []
        self.field_chat_checkpoint = {}
        self.field_chat_checkpoint_question = None
        self.field_chat_retry_question = None
        self.field_chat_status = tk.StringVar(
            value="첫 질문 시 현재 Field Map을 고정합니다."
        )
        ttk.Label(
            parent, textvariable=self.field_chat_status, anchor="w",
            foreground="#4b5563", wraplength=315,
        ).pack(fill=tk.X, pady=(0, 4))
        self.field_chat_history_widget = ScrolledText(
            parent, width=34, height=9, wrap=tk.WORD,
            font=ANSWER_FONT,
        )
        self.field_chat_history_widget.pack(fill=tk.BOTH, expand=True)
        self.field_chat_history_widget.configure(state=tk.DISABLED)
        self.field_chat_input = tk.Text(parent, height=3, wrap=tk.WORD)
        self.field_chat_input.pack(fill=tk.X, pady=(5, 4))
        self.field_chat_input.bind(
            "<Control-Return>", lambda _event: self._send_field_chat()
        )
        actions = ttk.Frame(parent)
        actions.pack(fill=tk.X)
        self.field_chat_send_button = ttk.Button(
            actions, text="질문 보내기", command=self._send_field_chat,
        )
        self.field_chat_send_button.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.field_chat_new_button = ttk.Button(
            actions, text="새 대화", command=self._reset_field_chat,
        )
        self.field_chat_new_button.pack(side=tk.LEFT, padx=(4, 0))
        self.field_chat_retry_button = ttk.Button(
            actions,
            text="최근 실패 재시도",
            command=self._retry_field_chat,
            state=tk.DISABLED,
        )
        self.field_chat_retry_button.pack(side=tk.LEFT, padx=(4, 0))

    def _field_chat_signature(self) -> tuple:
        indices = self._ordered_analysis_indices("field")
        configs = tuple(
            tuple(sorted(self.curve_configs[index].items()))
            for index in indices
            if index < len(self.curve_configs)
        )
        return (
            self.field_var.get(),
            self.scale_var.get(),
            self.range_var.get(),
            indices,
            configs,
        )

    def _reset_field_chat(self) -> None:
        self.field_chat_snapshot = None
        self.field_chat_turns = []
        self.field_chat_checkpoint = {}
        self.field_chat_checkpoint_question = None
        self.field_chat_retry_question = None
        self._arm_chat_retry("field", None)
        history = self.field_chat_history_widget
        history.configure(state=tk.NORMAL)
        history.delete("1.0", tk.END)
        history.configure(state=tk.DISABLED)
        self.field_chat_status.set("첫 질문 시 현재 Field Map을 고정합니다.")

    def _update_field_chat_view_status(self) -> None:
        snapshot = getattr(self, "field_chat_snapshot", None)
        if snapshot is None:
            return
        labels = ", ".join(snapshot.field_labels)
        iv_status = " · I-V 근거 연동" if snapshot.iv_payload else ""
        if snapshot.selection_signature != self._field_chat_signature():
            self.field_chat_status.set(
                f"{labels} · {snapshot.display}{iv_status} 스냅샷 기준 · 화면 변경됨 "
                "(새 대화로 반영)"
            )
        else:
            self.field_chat_status.set(
                f"{labels} · {snapshot.display}{iv_status} 스냅샷 기준"
            )

    def _send_field_chat(self) -> None:
        question = self.field_chat_input.get("1.0", tk.END).strip()
        if not question:
            return
        try:
            if self.field_chat_snapshot is None:
                if self.field_var.get() in FIELD_EXPLANATION_EXCLUDED:
                    raise ValueError(
                        f"{self.field_var.get()} is excluded from Explanation."
                    )
                outputs = [
                    (f"Curve {index + 1}", self.field_outputs[index])
                    for index in self._ordered_analysis_indices("field")
                    if index in self.field_outputs
                ]
                if not outputs:
                    raise ValueError(
                        "Generate at least one selected field map first."
                    )
                display = self.field_var.get()
                scale = self.scale_var.get()
                range_mode = self.range_var.get()
                signature = self._field_chat_signature()
                aligned_indices = [
                    index for index in self._ordered_analysis_indices("field")
                    if index in self.field_outputs
                    and index < len(self.curve_results)
                    and index < len(self.curve_configs)
                ]
                iv_results = [
                    self.curve_results[index] for index in aligned_indices
                ]
                iv_configs = [
                    dict(self.curve_configs[index]) for index in aligned_indices
                ]
                if len(iv_results) != len(outputs):
                    iv_results = iv_configs = None
            else:
                outputs = None
                display = scale = range_mode = None
                iv_results = iv_configs = None
                signature = self.field_chat_snapshot.selection_signature
        except ValueError:
            messagebox.showinfo(
                "Field Map 질문 사용 불가",
                "먼저 분석할 Field Map을 생성하고 선택해 주세요.",
                parent=self.window,
            )
            return
        checkpoint = (
            dict(self.field_chat_checkpoint)
            if self.field_chat_checkpoint_question == question
            else {}
        )
        history = list(self.field_chat_turns)
        snapshot = self.field_chat_snapshot
        self.field_chat_input.delete("1.0", tk.END)
        self.field_chat_send_button.configure(state=tk.DISABLED)
        self.field_chat_new_button.configure(state=tk.DISABLED)
        self.field_chat_status.set("Field Map 질문을 해석하고 있습니다.")

        def worker() -> None:
            try:
                active_snapshot = snapshot
                if active_snapshot is None:
                    active_snapshot = self.field_chat_service.build_snapshot(
                        outputs, display, scale, range_mode,
                        selection_signature=signature,
                        iv_results=iv_results,
                        iv_configs=iv_configs,
                    )
                response = self.field_chat_service.answer(
                    active_snapshot,
                    question,
                    history=history,
                    intent_checkpoint=checkpoint,
                )
            except Exception as exc:
                self.window.after(
                    0, lambda error=exc: self._field_chat_failed(error)
                )
            else:
                self.window.after(
                    0,
                    lambda: self._show_field_chat_response(
                        active_snapshot, question, response,
                    ),
                )
        threading.Thread(target=worker, daemon=True).start()

    def _show_field_chat_response(self, snapshot, question: str, response) -> None:
        self.field_chat_snapshot = snapshot
        self.field_chat_turns.append({
            "question": question,
            "answer": response.answer,
            "source": response.source,
            "comparison_focus": response.diagnostic.get(
                "comparison_focus"
            ),
        })
        self.field_chat_turns = self.field_chat_turns[-12:]
        if response.source == "external_error" and response.intent_checkpoint:
            self.field_chat_checkpoint = dict(response.intent_checkpoint)
            self.field_chat_checkpoint_question = question
        else:
            self.field_chat_checkpoint = {}
            self.field_chat_checkpoint_question = None
        self.field_chat_retry_question = (
            question if response.source == "external_error" else None
        )
        intent = response.intent.intent if response.intent else "분류 실패"
        engine = public_source_label(response.source)
        block = (
            f"사용자: {question}\n"
            f"AI [{engine} · {intent}]\n{response.answer}"
        )
        if response.suggested_followup:
            block += "\n이어서 생각해 볼 질문: " + response.suggested_followup
        history = self.field_chat_history_widget
        history.configure(state=tk.NORMAL)
        if history.get("1.0", tk.END).strip():
            history.insert(tk.END, "\n\n")
        history.insert(tk.END, block)
        history.configure(state=tk.DISABLED)
        history.see(tk.END)
        self.field_chat_send_button.configure(state=tk.NORMAL)
        self.field_chat_new_button.configure(state=tk.NORMAL)
        self._arm_chat_retry(
            "field",
            response.diagnostic.get("recommended_retry_after_seconds")
            if response.source == "external_error"
            else None,
            enabled=response.source == "external_error",
        )
        self._update_field_chat_view_status()

    def _retry_field_chat(self) -> None:
        question = self.field_chat_retry_question
        if not question:
            return
        self.field_chat_input.delete("1.0", tk.END)
        self.field_chat_input.insert("1.0", question)
        self._send_field_chat()

    def _arm_chat_retry(
        self,
        kind: str,
        seconds,
        *,
        enabled: bool = False,
    ) -> None:
        button = getattr(self, f"{kind}_chat_retry_button", None)
        if button is None:
            return
        generation_name = f"_{kind}_retry_generation"
        generation = int(getattr(self, generation_name, 0)) + 1
        setattr(self, generation_name, generation)
        try:
            remaining = max(0, int(seconds or 0))
        except (TypeError, ValueError):
            remaining = 0

        def tick(value: int) -> None:
            if generation != getattr(self, generation_name, None):
                return
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

        tick(remaining)

    def _field_chat_failed(self, error: Exception) -> None:
        del error
        self.field_chat_send_button.configure(state=tk.NORMAL)
        self.field_chat_new_button.configure(state=tk.NORMAL)
        self.field_chat_status.set("Field Map 질문 처리 실패")
        messagebox.showerror(
            "Field Map AI unavailable",
            "질문 처리 중 내부 오류가 발생했습니다. 현재 Field Map 상태를 "
            "확인해 주세요.",
            parent=self.window,
        )

    def _analyze(self, kind: str) -> None:
        if not getattr(self, "explanation_llm_available", False):
            self._show_explanation_provider_unavailable(kind)
            return
        try:
            if kind == "curve":
                indices = [index for index in self._ordered_analysis_indices("curve") if index < len(self.curve_results)]
                if not indices: raise ValueError("Select at least one visible I–V curve.")
                results = [self.curve_results[index] for index in indices]; configs = [dict(self.curve_configs[index]) for index in indices]
                task = lambda: self.explanation_service.explain_curves(results, configs)
            else:
                if self.field_var.get() in FIELD_EXPLANATION_EXCLUDED: raise ValueError(f"{self.field_var.get()} is excluded from Explanation.")
                outputs = [(f"Curve {index + 1}", self.field_outputs[index]) for index in self._ordered_analysis_indices("field") if index in self.field_outputs]
                if not outputs: raise ValueError("Generate at least one selected field map first.")
                display, scale, range_mode = self.field_var.get(), self.scale_var.get(), self.range_var.get()
                task = lambda: self.explanation_service.explain_fields(outputs, display, scale, range_mode)
        except ValueError:
            messagebox.showinfo(
                "AI 해설 사용 불가",
                "먼저 분석 대상을 생성하고 선택해 주세요.",
                parent=self.window,
            ); return
        view_key = self._explanation_view_key(kind); self.explanation_buttons[kind].configure(state=tk.DISABLED); self.explanation_status[kind].set("Analyzing...")

        def worker() -> None:
            try: result = task()
            except Exception as exc: self.window.after(0, lambda error=exc: self._explanation_failed(kind, error))
            else: self.window.after(0, lambda: self._show_explanation(kind, view_key, result.display_text(), result.cached))
        threading.Thread(target=worker, daemon=True).start()

    def _show_explanation(self, kind: str, view_key: tuple, content: str, cached: bool) -> None:
        self.explanation_history[kind][view_key] = (content, cached)
        if view_key != self._explanation_view_key(kind):
            self.explanation_buttons[kind].configure(state=tk.NORMAL); self.explanation_status[kind].set("Analysis saved for another view")
            if kind == "field": self._update_field_analyze_availability()
            return
        text = self.explanation_texts[kind]; text.configure(state=tk.NORMAL); text.delete("1.0", tk.END); text.insert("1.0", content); text.configure(state=tk.DISABLED)
        self.explanation_buttons[kind].configure(state=tk.NORMAL); self.explanation_status[kind].set("Cached" if cached else "Complete")

    def _explanation_failed(self, kind: str, error: Exception) -> None:
        self.explanation_buttons[kind].configure(state=tk.NORMAL)
        if isinstance(error, ExplanationPipelineError) and error.is_local:
            status = "로컬 해설 오류"
        elif isinstance(error, ExplanationPipelineError):
            status = "AI 응답 확인 오류"
        else:
            status = "AI 서비스 오류"
        self.explanation_status[kind].set(status)
        content = self._format_explanation_provider_error(error)
        text = self.explanation_texts[kind]
        text.configure(state=tk.NORMAL)
        text.delete("1.0", tk.END)
        text.insert("1.0", content)
        text.configure(state=tk.DISABLED)
        text.see("1.0")

    def _show_explanation_provider_unavailable(self, kind: str) -> None:
        content = (
            "AI 자동 해설이 현재 연결되지 않았습니다.\n"
            "서비스 관리자에게 문의해 주세요.\n"
            "분석 결과와 그래프는 계속 확인할 수 있습니다."
        )
        text = self.explanation_texts[kind]
        text.configure(state=tk.NORMAL)
        text.delete("1.0", tk.END)
        text.insert("1.0", content)
        text.configure(state=tk.DISABLED)
        self.explanation_status[kind].set("AI 해설 미연결")

    @staticmethod
    def _format_explanation_provider_error(error: Exception) -> str:
        if isinstance(error, ExplanationPipelineError):
            return public_ai_failure_message(
                feature="분석",
                failure=(
                    "local_processing_error"
                    if error.is_local
                    else "external_validation_failed"
                ),
                diagnostic=(
                    dict(error.diagnostics[-1])
                    if error.diagnostics
                    else {}
                ),
                automatic=True,
            )
        if isinstance(error, ProviderHTTPError):
            diagnostic = error.diagnostic()
            failure = f"external_http_{error.status}"
            wait = IVChatService._retry_seconds(failure, diagnostic)
            return public_ai_failure_message(
                feature="분석",
                failure=failure,
                diagnostic=diagnostic,
                retry_after_seconds=wait,
                automatic=True,
            )
        code = str(error)
        if isinstance(error, TimeoutError) or code == "provider_timeout":
            failure = "external_timeout"
        elif code == "provider_network_error":
            failure = "external_network_error"
        elif isinstance(error, ValueError):
            failure = "external_validation_failed"
        else:
            failure = "external_request_failed"
        return public_ai_failure_message(
            feature="분석",
            failure=failure,
            automatic=True,
        )

    def _copy_explanation(self, kind: str) -> None:
        content = self.explanation_texts[kind].get("1.0", tk.END).strip()
        if content: self.window.clipboard_clear(); self.window.clipboard_append(content)

    def _generate_prompt(self, kind: str) -> None:
        try:
            if kind == "curve":
                indices = [index for index in self._ordered_analysis_indices("curve") if index < len(self.curve_results)]
                if not indices: raise ValueError("Select at least one visible I–V curve.")
                results = [self.curve_results[index] for index in indices]
                configs = [dict(self.curve_configs[index]) for index in indices]
                prompt = self.explanation_service.build_curves_prompt(results, configs)
            else:
                if self.field_var.get() in FIELD_EXPLANATION_EXCLUDED:
                    raise ValueError(f"{self.field_var.get()} is excluded from Explanation.")
                outputs = [(f"Curve {index + 1}", self.field_outputs[index]) for index in self._ordered_analysis_indices("field") if index in self.field_outputs]
                if not outputs: raise ValueError("Generate at least one selected field map first.")
                prompt = self.explanation_service.build_fields_prompt(
                    outputs, self.field_var.get(), self.scale_var.get(), self.range_var.get(),
                )
        except ValueError as exc:
            messagebox.showinfo("Prompt unavailable", str(exc), parent=self.window)
            return
        dialog = tk.Toplevel(self.window)
        dialog.title(f"{kind.title()} LLM Polish Prompt")
        dialog.geometry("950x720")
        actions = ttk.Frame(dialog, padding=(8, 8)); actions.pack(fill=tk.X)
        ttk.Label(actions, text="Full analysis context for interactive external LLM use").pack(side=tk.LEFT)
        text = ScrolledText(dialog, wrap=tk.NONE, font=("Consolas", 9))
        text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        text.insert("1.0", prompt)

        def copy_prompt() -> None:
            self.window.clipboard_clear(); self.window.clipboard_append(text.get("1.0", tk.END).rstrip())

        ttk.Button(actions, text="Copy Prompt", command=copy_prompt).pack(side=tk.RIGHT)

    def _explanation_view_key(self, kind: str) -> tuple:
        provider = "external_llm"
        if kind == "curve":
            indices = self._ordered_analysis_indices("curve")
            return provider, indices, tuple(tuple(sorted(self.curve_configs[index].items())) for index in indices)
        indices = self._ordered_analysis_indices("field"); configs = tuple(tuple(sorted(self.curve_configs[index].items())) for index in indices if index < len(self.curve_configs))
        return provider, self.field_var.get(), self.scale_var.get(), self.range_var.get(), indices, configs

    def _restore_explanation(self, kind: str) -> None:
        self._refresh_analysis_context(kind)
        saved = self.explanation_history[kind].get(self._explanation_view_key(kind)); text = self.explanation_texts[kind]
        text.configure(state=tk.NORMAL); text.delete("1.0", tk.END)
        if saved:
            content, cached = saved; text.insert("1.0", content); self.explanation_status[kind].set("Cached" if cached else "Complete")
        else:
            self.explanation_status[kind].set(
                "AI 해설 준비됨"
                if getattr(self, "explanation_llm_available", False)
                else "AI 해설 사용 불가"
            )
        text.configure(state=tk.DISABLED)
        if kind == "curve" and hasattr(self, "iv_chat_status"):
            self._update_iv_chat_view_status()
        if kind == "field" and hasattr(self, "field_chat_status"):
            self._update_field_chat_view_status()

    def _field_view_changed(self, _event=None) -> None:
        self.render_field(); self._restore_explanation("field"); self._update_field_analyze_availability()

    def _update_field_analyze_availability(self) -> None:
        if not hasattr(self, "field_var") or "field" not in self.explanation_buttons: return
        excluded = self.field_var.get() in FIELD_EXPLANATION_EXCLUDED
        self.explanation_buttons["field"].configure(state=tk.DISABLED if excluded else tk.NORMAL)
        if excluded: self.explanation_status["field"].set("Explanation not provided for this view")

    def _mark_explanation_stale(self, kind: str) -> None:
        self._refresh_analysis_context(kind)
        if kind in self.explanation_status and self.explanation_texts[kind].get("1.0", tk.END).strip():
            self.explanation_status[kind].set("Results changed — press Analyze")
        if kind == "curve" and hasattr(self, "iv_chat_status"):
            self._update_iv_chat_view_status()
        if kind == "field" and hasattr(self, "field_chat_status"):
            self._update_field_chat_view_status()
