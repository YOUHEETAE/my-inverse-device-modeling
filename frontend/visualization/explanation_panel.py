from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText


FIELD_EXPLANATION_EXCLUDED = {"Mesh", "Abs net doping", "Net doping"}
EXPLANATION_PROVIDERS = ("mock", "external_llm")


class ExplanationPanelMixin:
    """Reusable explanation widgets, background execution, and view history."""

    def _build_explanation_panel(self, parent: ttk.LabelFrame, kind: str) -> None:
        controls = ttk.Frame(parent); controls.pack(fill=tk.X, pady=(0, 3))
        button = ttk.Button(controls, text="Analyze", command=lambda: self._analyze(kind)); button.pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(controls, text="Copy", command=lambda: self._copy_explanation(kind)).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)
        ttk.Button(controls, text="Preview LLM Prompt", command=lambda: self._generate_prompt(kind)).pack(side=tk.LEFT, expand=True, fill=tk.X)
        provider_name = getattr(getattr(self, "explanation_service", None), "provider", None)
        status = tk.StringVar(value=f"Ready ({getattr(provider_name, 'name', 'mock')})")
        ttk.Label(parent, textvariable=status, anchor="w").pack(fill=tk.X, pady=(0, 4))
        # Keep the side panel compact so the plots receive most of the window.
        text = ScrolledText(parent, width=34, height=6, wrap=tk.WORD, font=("TkDefaultFont", 9)); text.pack(fill=tk.BOTH, expand=True); text.configure(state=tk.DISABLED)
        self.explanation_buttons[kind] = button; self.explanation_status[kind] = status; self.explanation_texts[kind] = text

    def _analyze(self, kind: str) -> None:
        try:
            if kind == "curve":
                indices = [index for index in range(len(self.curve_results)) if index in self.visible_curve_indices]
                if not indices: raise ValueError("Select at least one visible I–V curve.")
                results = [self.curve_results[index] for index in indices]; configs = [dict(self.curve_configs[index]) for index in indices]
                task = lambda: self.explanation_service.explain_curves(results, configs)
            else:
                if self.field_var.get() in FIELD_EXPLANATION_EXCLUDED: raise ValueError(f"{self.field_var.get()} is excluded from Explanation.")
                outputs = [(f"Curve {index + 1}", self.field_outputs[index]) for index in sorted(self.field_selected_indices) if index in self.field_outputs]
                if not outputs: raise ValueError("Generate at least one selected field map first.")
                display, scale, range_mode = self.field_var.get(), self.scale_var.get(), self.range_var.get()
                task = lambda: self.explanation_service.explain_fields(outputs, display, scale, range_mode)
        except ValueError as exc:
            messagebox.showinfo("Explanation unavailable", str(exc), parent=self.window); return
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
        del error  # Internal exception details and paths must not reach the user.
        self.explanation_buttons[kind].configure(state=tk.NORMAL); self.explanation_status[kind].set("Failed")
        messagebox.showerror("Explanation unavailable", "설명을 생성하지 못했습니다. 입력 데이터와 분석 조건을 확인해 주세요.", parent=self.window)

    def _copy_explanation(self, kind: str) -> None:
        content = self.explanation_texts[kind].get("1.0", tk.END).strip()
        if content: self.window.clipboard_clear(); self.window.clipboard_append(content)

    def _generate_prompt(self, kind: str) -> None:
        try:
            if kind == "curve":
                indices = [index for index in range(len(self.curve_results)) if index in self.visible_curve_indices]
                if not indices: raise ValueError("Select at least one visible I–V curve.")
                results = [self.curve_results[index] for index in indices]
                configs = [dict(self.curve_configs[index]) for index in indices]
                prompt = self.explanation_service.build_curves_prompt(results, configs)
            else:
                if self.field_var.get() in FIELD_EXPLANATION_EXCLUDED:
                    raise ValueError(f"{self.field_var.get()} is excluded from Explanation.")
                outputs = [(f"Curve {index + 1}", self.field_outputs[index]) for index in sorted(self.field_selected_indices) if index in self.field_outputs]
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
        provider = getattr(getattr(self, "explanation_provider_var", None), "get", lambda: "mock")()
        if kind == "curve":
            indices = tuple(index for index in range(len(self.curve_configs)) if index in self.visible_curve_indices)
            return provider, indices, tuple(tuple(sorted(self.curve_configs[index].items())) for index in indices)
        indices = tuple(sorted(self.field_selected_indices)); configs = tuple(tuple(sorted(self.curve_configs[index].items())) for index in indices if index < len(self.curve_configs))
        return provider, self.field_var.get(), self.scale_var.get(), self.range_var.get(), indices, configs

    def _restore_explanation(self, kind: str) -> None:
        saved = self.explanation_history[kind].get(self._explanation_view_key(kind)); text = self.explanation_texts[kind]
        text.configure(state=tk.NORMAL); text.delete("1.0", tk.END)
        if saved:
            content, cached = saved; text.insert("1.0", content); self.explanation_status[kind].set("Cached" if cached else "Complete")
        else: self.explanation_status[kind].set(f"Ready ({self.explanation_service.provider.name})")
        text.configure(state=tk.DISABLED)

    def _field_view_changed(self, _event=None) -> None:
        self.render_field(); self._restore_explanation("field"); self._update_field_analyze_availability()

    def _update_field_analyze_availability(self) -> None:
        if not hasattr(self, "field_var") or "field" not in self.explanation_buttons: return
        excluded = self.field_var.get() in FIELD_EXPLANATION_EXCLUDED
        self.explanation_buttons["field"].configure(state=tk.DISABLED if excluded else tk.NORMAL)
        if excluded: self.explanation_status["field"].set("Explanation not provided for this view")

    def _mark_explanation_stale(self, kind: str) -> None:
        if kind in self.explanation_status and self.explanation_texts[kind].get("1.0", tk.END).strip():
            self.explanation_status[kind].set("Results changed — press Analyze")
