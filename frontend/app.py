from __future__ import annotations

import tkinter as tk

# Initialize Tcl before numerical/GUI backends load native DLLs.  This avoids
# the Windows Conda runtime resolving an incompatible Tcl library first.
_TCL_BOOTSTRAP = tk.Tcl() if __name__ == "__main__" else None

import argparse
from dataclasses import replace
import logging
import sys
import math
import queue
import threading
from pathlib import Path
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure


LOGGER = logging.getLogger(__name__)


# Support both `python ai/tools/visualization_models.py` and direct execution of
# this file from an IDE or an absolute path.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai.curve_model.inference import (
    DEFAULT_PARAMETERS,
    PARAMETER_OPTIONS,
    CurvePrediction,
    FinalCurvePredictor,
    device_features,
    extract_electrical_parameters,
    range_warning,
)
from ai.field_map_model.inference import FieldMapPredictor, GeneratedMesh, generate_gmsh_mesh
from ai.shared.field_data import (
    FIELD_DISPLAYS,
    RANGE_MODES,
    SCALE_MODES,
    GeneratedFieldMap,
)
from frontend.visualization.field_rendering import (
    render_model_field,
    render_model_field_comparison,
)
from backend.explanation import ExplanationService, MockExplanationProvider
from backend.explanation.iv_chat import IVChatService
from backend.explanation.field_chat import FieldChatService
from backend.explanation.comparison_planner import build_comparison_plan
from backend.explanation.providers import ProviderSettings, create_explanation_provider
from backend.learning.experiment_runner import LearningExperimentRunner
from backend.learning.schemas import LearningStep
from backend.learning.session_repository import InMemorySessionRepository, JsonSessionRepository
from frontend.visualization.case_study import CaseStudyPanel
from frontend.visualization.curve_rendering import render_curve_figure
from frontend.visualization.explanation_panel import ExplanationPanelMixin
from frontend.visualization.guide_panel import build_guide_panel
from frontend.visualization.guide_content import GUIDE_CHAPTERS, THEORY_CHAPTERS


PARAMETERS = ("L", "T", "B", "SD", "LDD")
MAX_FIELD_SELECTIONS = 2
PARAMETER_TITLES = {
    "L": "L (nm)", "T": "T (nm)", "B": "B (cm⁻³)",
    "SD": "SD (cm⁻³)", "LDD": "LDD (cm⁻³)",
}
ELECTRICAL_PARAMETERS = (
    ("vth_low_v", "Vth (Vd=0.05 V)", "V", 1.0, ".5g"),
    ("vth_high_v", "Vth (Vd=1.5 V)", "V", 1.0, ".5g"),
    ("ion_ma_per_um", "Ion", "mA/µm", 1.0, ".5g"),
    ("ioff_ma_per_um", "Ioff", "mA/µm", 1.0, ".4e"),
    ("ion_ioff_ratio", "Ion/Ioff", "", 1.0, ".4e"),
    ("ss_mv_per_dec", "SS", "mV/dec", 1.0, ".5g"),
    ("dibl_gm_v_per_v", "DIBL", "mV/V", 1000.0, ".5g"),
    ("gm_max_ms_per_um", "gm max", "mS/µm", 1.0, ".5g"),
    ("gds_ms_per_um", "gds", "mS/µm", 1.0, ".5g"),
    ("ron_kohm_um", "Ron", "kΩ·µm", 1.0, ".5g"),
    ("lambda_per_v", "λ (CLM)", "1/V", 1.0, ".5g"),
)


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _create_tk_window() -> tk.Tk:
    """Create Tk, repairing Conda's missing tk8.6 auto_path when necessary."""
    window = tk.Tk(useTk=False)
    try:
        tk_library = Path(sys.prefix) / "Library" / "lib" / "tk8.6"
        if (tk_library / "pkgIndex.tcl").is_file():
            window.tk.call("lappend", "auto_path", tk_library.as_posix())
        window.loadtk()
        return window
    except tk.TclError:
        try:
            window.destroy()
        except tk.TclError:
            pass
        raise


def create_case_study_provider():
    """Create the application's dedicated strict Groq provider."""
    try:
        settings = replace(
            ProviderSettings.from_environment("external_llm"),
            allow_mock_fallback=False,
            allow_safe_fallback=False,
        )
        return create_explanation_provider(
            settings
        )
    except RuntimeError:
        return None


class IntegratedModelApp(ExplanationPanelMixin):
    def __init__(
        self,
        window: tk.Tk,
        curve_predictor: FinalCurvePredictor,
        field_predictor: FieldMapPredictor,
        geo_template: Path,
        *,
        enable_learning_persistence: bool = True,
        auto_generate: bool = True,
    ) -> None:
        self.window = window; self.curve_predictor = curve_predictor
        self.field_predictor = field_predictor; self.geo_template = geo_template
        self.mesh_cache: dict[tuple[float, float], GeneratedMesh] = {}
        self.curve_configs: list[dict[str, str]] = [dict(DEFAULT_PARAMETERS)]
        self.visible_curve_indices: set[int] = {0}
        self.curve_results: list[tuple[str, CurvePrediction, CurvePrediction]] = []
        self.active_curve_index = 0
        self.field_outputs: dict[int, GeneratedFieldMap] = {}
        self.field_selected_indices: set[int] = {0}
        self.analysis_baseline_indices: dict[str, int | None] = {
            "curve": 0, "field": 0,
        }
        self.analysis_baseline_vars: dict[str, tk.StringVar] = {}
        self.analysis_baseline_widgets: dict[str, ttk.Combobox] = {}
        self.analysis_context_vars: dict[str, tk.StringVar] = {}
        self.combined_curves = True
        interactive_provider = create_case_study_provider()
        self.explanation_llm_available = interactive_provider is not None
        # Mock remains the deterministic analysis authority. Provider details
        # stay internal while the UI reports only whether AI help is available.
        service_provider = interactive_provider or MockExplanationProvider()
        self.explanation_service = ExplanationService(service_provider)
        self.explanation_provider_help_var = tk.StringVar(
            value=(
                "I-V / Field AI 해설: 사용 가능"
                if self.explanation_llm_available
                else "I-V / Field AI 해설: 현재 사용 불가"
            )
        )
        self.explanation_texts: dict[str, ScrolledText] = {}
        self.explanation_buttons: dict[str, ttk.Button] = {}
        self.explanation_status: dict[str, tk.StringVar] = {}
        self.explanation_history: dict[str, dict[tuple, tuple[str, bool]]] = {"curve": {}, "field": {}}
        self.iv_chat_service = IVChatService(interactive_provider)
        self.field_chat_service = FieldChatService(interactive_provider)
        self.side_panel_width = 360
        window.title("Integrated AI Device Model Visualization")
        screen_width, screen_height = window.winfo_screenwidth(), window.winfo_screenheight()
        width = min(1600, max(1000, int(screen_width * 0.9)))
        height = min(900, max(650, int(screen_height * 0.85)))
        window.geometry(f"{width}x{height}")

        top = ttk.Frame(window, padding=(10, 8)); top.pack(side=tk.TOP, fill=tk.X)
        provider_row = ttk.Frame(window, padding=(10, 0, 10, 8)); provider_row.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(provider_row, textvariable=self.explanation_provider_help_var, foreground="#4b5563").pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(top, text="Common device parameters", font=("TkDefaultFont", 10, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        self.parameter_vars = {name: tk.StringVar(value=DEFAULT_PARAMETERS[name]) for name in PARAMETERS}
        for name in PARAMETERS:
            ttk.Label(top, text=PARAMETER_TITLES[name]).pack(side=tk.LEFT)
            combo = ttk.Combobox(top, textvariable=self.parameter_vars[name], values=PARAMETER_OPTIONS[name], state="normal", width=11)
            combo.pack(side=tk.LEFT, padx=(3, 8)); combo.bind("<<ComboboxSelected>>", lambda _event: self._dirty()); combo.bind("<KeyRelease>", lambda _event: self._dirty()); combo.bind("<Return>", self._parameters_enter)
        self.status = tk.StringVar(value="")
        self.status_label = ttk.Label(top, textvariable=self.status)
        self.status_label.pack(side=tk.LEFT, padx=(5, 0))

        style = ttk.Style(window)
        style.configure("Main.TNotebook", borderwidth=2, relief="solid")
        style.configure("Main.TNotebook.Tab", padding=(18, 8), font=("TkDefaultFont", 10, "bold"))
        style.map("Main.TNotebook.Tab", background=[("selected", "#d7e8ff"), ("active", "#edf5ff")])
        self.notebook = ttk.Notebook(window, style="Main.TNotebook"); self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.curve_tab = ttk.Frame(self.notebook); self.field_tab = ttk.Frame(self.notebook)
        self.guide_tab = ttk.Frame(self.notebook); self.theory_tab = ttk.Frame(self.notebook)
        self.case_study_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.guide_tab, text="1. Guide")
        self.notebook.add(self.theory_tab, text="2. Theory")
        self.notebook.add(self.case_study_tab, text="3. Case Study")
        self.notebook.add(self.curve_tab, text="I–V Curve"); self.notebook.add(self.field_tab, text="Structure / Field Map")
        self._build_curve_tab(); self._build_field_tab(); self._build_guide_tabs()
        learning_repository = (
            JsonSessionRepository(REPO_ROOT / "runtime" / "learning_sessions")
            if enable_learning_persistence
            else InMemorySessionRepository()
        )
        learning_runner = LearningExperimentRunner(
            curve_predictor=self.curve_predictor,
            field_predictor=self.field_predictor,
            geo_template=self.geo_template,
        )
        self.case_study_panel = CaseStudyPanel(
            self.case_study_tab,
            window=self.window,
            runner=learning_runner,
            repository=learning_repository,
            provider=interactive_provider,
            on_open_theory=lambda: self.notebook.select(self.theory_tab),
        )
        self.case_study_panel.pack(fill=tk.BOTH, expand=True)
        if auto_generate:
            window.after(60, self.generate_all)

    def _build_curve_tab(self) -> None:
        panel = ttk.LabelFrame(self.curve_tab, text="I–V curve settings", padding=(10, 8), width=self.side_panel_width)
        panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 8), pady=4); panel.pack_propagate(False)
        tree_frame = ttk.Frame(panel); tree_frame.pack(fill=tk.X)
        self.curve_tree = ttk.Treeview(tree_frame, columns=("curve", *PARAMETERS), show="headings", height=3, selectmode="browse")
        widths = {"curve": 68, "L": 34, "T": 34, "B": 56, "SD": 56, "LDD": 56}
        for name in ("curve", *PARAMETERS):
            self.curve_tree.heading(name, text="Curve" if name == "curve" else name); self.curve_tree.column(name, width=widths[name], anchor=tk.CENTER, stretch=False)
        self.curve_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.curve_tree.yview)
        self.curve_tree.configure(yscrollcommand=self.curve_scrollbar.set)
        self.curve_tree.grid(row=0, column=0, sticky="nsew")
        self.curve_scrollbar.grid(row=0, column=1, sticky="ns")
        self.more_curves_label = ttk.Label(tree_frame, text="More curves below ↓")
        self.more_curves_label.grid(row=1, column=0, sticky="e", pady=(2, 0))
        self.curve_tree.bind("<<TreeviewSelect>>", self._curve_selected)
        self.curve_tree.bind("<Button-1>", self._curve_tree_clicked, add="+")
        buttons = ttk.Frame(panel); buttons.pack(fill=tk.X, pady=(6, 3))
        ttk.Button(buttons, text="Add Curve", command=self.add_curve).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        ttk.Button(buttons, text="Update Selected", command=self.update_selected_curve).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(buttons, text="Remove Selected", command=self.remove_selected_curve).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))
        self.curve_view_button = ttk.Button(panel, text="Separate Biases (8 plots)", command=self.toggle_curve_view); self.curve_view_button.pack(fill=tk.X, pady=(2, 8))
        ttk.Separator(panel).pack(fill=tk.X, pady=(0, 7))
        ttk.Label(panel, text="Extracted electrical parameters", font=("TkDefaultFont", 9, "bold")).pack(anchor="w", pady=(0, 4))
        electrical_container = ttk.Frame(panel); electrical_container.pack(fill=tk.X)
        self.electrical_canvas = tk.Canvas(electrical_container, height=315, highlightthickness=0)
        self.electrical_hscroll = ttk.Scrollbar(electrical_container, orient=tk.HORIZONTAL, command=self.electrical_canvas.xview)
        self.electrical_canvas.configure(xscrollcommand=self.electrical_hscroll.set)
        self.electrical_canvas.pack(fill=tk.X, expand=True)
        self.electrical_hscroll.pack(fill=tk.X)
        self.electrical_panel = ttk.Frame(self.electrical_canvas)
        self.electrical_canvas_window = self.electrical_canvas.create_window((0, 0), window=self.electrical_panel, anchor="nw")
        self.electrical_panel.bind("<Configure>", lambda _event: self.electrical_canvas.configure(scrollregion=self.electrical_canvas.bbox("all")))
        self.electrical_value_widgets: list[tk.Widget] = []
        ttk.Label(self.electrical_panel, text="Parameter").grid(row=0, column=0, padx=5, pady=(0, 7), sticky="w")
        for row, (name, label, unit, _factor, _fmt) in enumerate(ELECTRICAL_PARAMETERS, start=1):
            text = f"{label} ({unit})" if unit else label
            ttk.Label(self.electrical_panel, text=text, justify=tk.LEFT).grid(row=row, column=0, padx=5, pady=2, sticky="w")
        ttk.Separator(panel).pack(fill=tk.X, pady=(7, 7))
        explanation = ttk.LabelFrame(panel, text="Explanation", padding=(8, 8)); explanation.pack(fill=tk.BOTH, expand=True)
        self._build_explanation_panel(explanation, "curve")
        plot_frame = ttk.Frame(self.curve_tab); plot_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.curve_figure = Figure(figsize=(8.5, 6), dpi=100); self.curve_canvas = FigureCanvasTkAgg(self.curve_figure, master=plot_frame); self.curve_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        toolbar = ttk.Frame(plot_frame); toolbar.pack(side=tk.BOTTOM, fill=tk.X); NavigationToolbar2Tk(self.curve_canvas, toolbar)
        self._refresh_curve_tree()

    def _build_field_tab(self) -> None:
        panel = ttk.LabelFrame(self.field_tab, text="Field comparison", padding=(10, 8), width=self.side_panel_width)
        panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 8), pady=4); panel.pack_propagate(False)
        self.field_var = tk.StringVar(value="Potential"); self.scale_var = tk.StringVar(value="Auto"); self.range_var = tk.StringVar(value="Robust 1-99%")
        for label, variable, values, width in (("Field map", self.field_var, FIELD_DISPLAYS, 30), ("Scale", self.scale_var, SCALE_MODES, 14), ("Range", self.range_var, RANGE_MODES, 18)):
            row = ttk.Frame(panel); row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=label, width=10, anchor="w").pack(side=tk.LEFT)
            combo = ttk.Combobox(row, textvariable=variable, values=values, state="readonly", width=width)
            combo.pack(side=tk.RIGHT, fill=tk.X, expand=True)
            combo.bind("<<ComboboxSelected>>", self._field_view_changed)
        ttk.Separator(panel).pack(fill=tk.X, pady=8)
        ttk.Label(panel, text="Fixed bias: Vg=3 V, Vd=3 V").pack(anchor="w", pady=(0, 7))
        selection_header = ttk.Frame(panel); selection_header.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(
            selection_header,
            text="Select up to 2 curves",
            font=("TkDefaultFont", 9, "bold"),
        ).pack(side=tk.LEFT)
        ttk.Button(selection_header, text="Generate All", command=self.generate_all).pack(side=tk.RIGHT, padx=(6, 0))
        self.field_curve_frame = ttk.Frame(panel); self.field_curve_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(panel, text="Parameters", font=("TkDefaultFont", 9, "bold")).pack(anchor="w")
        self.field_parameter_frame = ttk.Frame(panel); self.field_parameter_frame.pack(fill=tk.X, pady=(3, 8))
        ttk.Separator(panel).pack(fill=tk.X, pady=(4, 8))
        explanation = ttk.LabelFrame(panel, text="Explanation", padding=(8, 8)); explanation.pack(fill=tk.BOTH, expand=True)
        self._build_explanation_panel(explanation, "field")
        plot_frame = ttk.Frame(self.field_tab); plot_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.field_figure = Figure(figsize=(8.5, 6), dpi=100); self.field_canvas = FigureCanvasTkAgg(self.field_figure, master=plot_frame); self.field_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        toolbar = ttk.Frame(plot_frame); toolbar.pack(side=tk.BOTTOM, fill=tk.X); NavigationToolbar2Tk(self.field_canvas, toolbar)
        self._refresh_field_curve_controls()

    def _build_guide_tabs(self) -> None:
        build_guide_panel(self.guide_tab, GUIDE_CHAPTERS)
        build_guide_panel(self.theory_tab, THEORY_CHAPTERS)

    def _dirty(self) -> None:
        action = "Update Selected" if self.notebook.select() == str(self.curve_tab) else "Generate All"
        self.status.set(f"Parameters changed. Press {action}.")

    def _parameters_enter(self, _event=None) -> None:
        if self.notebook.select() == str(self.curve_tab):
            self.update_selected_curve()
        else:
            self.generate_all()

    def _values(self) -> dict[str, str]:
        return {name: variable.get().strip() for name, variable in self.parameter_vars.items()}

    def _refresh_curve_tree(self) -> None:
        self.curve_tree.delete(*self.curve_tree.get_children())
        for index, config in enumerate(self.curve_configs):
            checked = "☑" if index in self.visible_curve_indices else "☐"
            self.curve_tree.insert("", tk.END, iid=str(index), values=(f"{checked} Curve {index + 1}", *(config[name] for name in PARAMETERS)))
        active = min(self.active_curve_index, len(self.curve_configs) - 1); self.active_curve_index = active
        self.curve_tree.selection_set(str(active)); self.curve_tree.focus(str(active))
        if len(self.curve_configs) > 3:
            self.curve_scrollbar.grid(); self.more_curves_label.grid()
            self.curve_tree.see(str(active))
        else:
            self.curve_scrollbar.grid_remove(); self.more_curves_label.grid_remove()
        if hasattr(self, "field_curve_frame"):
            self._refresh_field_curve_controls()
        if hasattr(self, "analysis_context_vars"):
            self._refresh_analysis_context("curve")
            self._refresh_analysis_context("field")

    def _refresh_field_curve_controls(self) -> None:
        for frame in (self.field_curve_frame, self.field_parameter_frame):
            for widget in frame.winfo_children():
                widget.destroy()
        self.field_curve_vars: dict[int, tk.BooleanVar] = {}
        for index in range(len(self.curve_configs)):
            variable = tk.BooleanVar(value=index in self.field_selected_indices)
            self.field_curve_vars[index] = variable
            ttk.Checkbutton(
                self.field_curve_frame,
                text=f"Curve {index + 1}",
                variable=variable,
                command=lambda i=index: self._field_curve_toggled(i),
            ).grid(row=index // 3, column=index % 3, padx=3, pady=1, sticky="w")
        selected = sorted(self.field_selected_indices)
        ttk.Label(self.field_parameter_frame, text="Curve").grid(row=0, column=0, padx=(0, 7), pady=2, sticky="w")
        for column, name in enumerate(PARAMETERS, start=1):
            ttk.Label(self.field_parameter_frame, text=name).grid(row=0, column=column, padx=4, pady=2)
        for row, index in enumerate(selected, start=1):
            ttk.Label(self.field_parameter_frame, text=f"Curve {index + 1}").grid(row=row, column=0, padx=(0, 7), pady=2, sticky="w")
            for column, name in enumerate(PARAMETERS, start=1):
                ttk.Label(self.field_parameter_frame, text=self.curve_configs[index][name], anchor="e").grid(row=row, column=column, padx=4, pady=2, sticky="e")

    def _field_curve_toggled(self, index: int) -> None:
        if self.field_curve_vars[index].get():
            if (
                index not in self.field_selected_indices
                and len(self.field_selected_indices) >= MAX_FIELD_SELECTIONS
            ):
                self.field_curve_vars[index].set(False)
                self.status.set(
                    "Field Map은 최대 2개 Curve만 선택할 수 있습니다."
                )
                return
            self.field_selected_indices.add(index)
        else:
            self.field_selected_indices.discard(index)
        self._refresh_field_curve_controls(); self.render_field()
        self._restore_explanation("field")
        self.status.set("Field comparison selection changed. Press Generate All to generate the selected map(s).")

    def _curve_tree_clicked(self, event: tk.Event) -> None:
        if self.curve_tree.identify_region(event.x, event.y) != "cell" or self.curve_tree.identify_column(event.x) != "#1":
            return
        item = self.curve_tree.identify_row(event.y)
        if not item:
            return
        index = int(item)
        if index in self.visible_curve_indices:
            self.visible_curve_indices.remove(index)
        else:
            self.visible_curve_indices.add(index)
        self._refresh_curve_tree(); self.render_curves(); self._restore_explanation("curve")

    def _curve_selected(self, _event=None) -> None:
        selection = self.curve_tree.selection()
        if not selection:
            return
        self.active_curve_index = int(selection[0]); config = self.curve_configs[self.active_curve_index]
        for name in PARAMETERS: self.parameter_vars[name].set(config[name])
        self._update_electrical_panel(); self.status.set(f"Curve {self.active_curve_index + 1} selected. Press Update Selected after editing parameters.")

    def add_curve(self) -> None:
        self.curve_configs.append(dict(self._values())); self.active_curve_index = len(self.curve_configs) - 1
        self.visible_curve_indices.add(self.active_curve_index)
        try:
            self._generate_curve(self.active_curve_index)
            self._refresh_curve_tree(); self.render_curves(); self._restore_explanation("curve")
            self.status.set(f"Curve {self.active_curve_index + 1} added and generated.")
        except Exception as exc:
            LOGGER.exception("Curve generation failed", exc_info=exc)
            failed_index = self.active_curve_index
            self.curve_configs.pop()
            self.visible_curve_indices.discard(failed_index)
            self.active_curve_index = len(self.curve_configs) - 1
            self._refresh_curve_tree()
            messagebox.showerror(
                "Curve 생성 실패",
                "Curve를 생성하지 못했습니다. 입력 조건을 확인하고 다시 시도해 주세요.",
                parent=self.window,
            ); self.status.set("Curve generation failed")

    def update_selected_curve(self) -> None:
        self.curve_configs[self.active_curve_index] = dict(self._values())
        try:
            self._generate_curve(self.active_curve_index)
            self._refresh_curve_tree(); self.render_curves(); self._restore_explanation("curve")
            self.status.set(f"Curve {self.active_curve_index + 1} updated and generated.")
        except Exception as exc:
            LOGGER.exception("Curve update failed", exc_info=exc)
            messagebox.showerror(
                "Curve 생성 실패",
                "Curve를 갱신하지 못했습니다. 입력 조건을 확인하고 다시 시도해 주세요.",
                parent=self.window,
            ); self.status.set("Curve generation failed")

    def remove_selected_curve(self) -> None:
        if len(self.curve_configs) == 1:
            self.status.set("At least one curve must remain."); return
        removed = self.active_curve_index
        self.curve_configs.pop(removed)
        self.visible_curve_indices = {index - 1 if index > removed else index for index in self.visible_curve_indices if index != removed}
        self.field_selected_indices = {index - 1 if index > removed else index for index in self.field_selected_indices if index != removed}
        self.field_outputs = {index - 1 if index > removed else index: output for index, output in self.field_outputs.items() if index != removed}
        for kind, baseline in tuple(self.analysis_baseline_indices.items()):
            if baseline is None:
                continue
            self.analysis_baseline_indices[kind] = (
                None if baseline == removed
                else baseline - 1 if baseline > removed
                else baseline
            )
        if removed < len(self.curve_results):
            self.curve_results.pop(removed)
        self.active_curve_index = min(removed, len(self.curve_configs) - 1)
        self._refresh_curve_tree(); self._curve_selected(); self.render_curves()
        self._restore_explanation("curve"); self._restore_explanation("field"); self.status.set("Selected curve removed.")

    def toggle_curve_view(self) -> None:
        self.combined_curves = not self.combined_curves
        self.curve_view_button.configure(text="Separate Biases (8 plots)" if self.combined_curves else "Combine Biases (4 plots)")
        self.render_curves()

    def generate_all(self) -> None:
        values = self._values(); self.curve_configs[self.active_curve_index] = dict(values); self._refresh_curve_tree()
        try:
            self.status.set("Generating selected I–V curve..."); self.window.update_idletasks()
            self._generate_curve(self.active_curve_index)
            if not self.field_selected_indices:
                raise ValueError("Select at least one curve in the Field comparison panel.")
            if len(self.field_selected_indices) > MAX_FIELD_SELECTIONS:
                raise ValueError(
                    "Field Map supports at most two selected curves."
                )
            self.field_outputs = {}
            for index in sorted(self.field_selected_indices):
                config = self.curve_configs[index]
                length, tox = float(config["L"]), float(config["T"]); key = (length, tox)
                mesh = self.mesh_cache.get(key)
                if mesh is None:
                    self.status.set(f"Generating Curve {index + 1} Gmsh structure..."); self.window.update_idletasks(); mesh = generate_gmsh_mesh(length, tox, self.geo_template); self.mesh_cache[key] = mesh
                self.status.set(f"Generating Curve {index + 1} field map..."); self.window.update_idletasks()
                prediction = self.field_predictor.predict(mesh, length, tox, float(config["B"]), float(config["SD"]), float(config["LDD"]))
                self.field_outputs[index] = GeneratedFieldMap(mesh, prediction, length, tox, float(config["B"]), float(config["SD"]), float(config["LDD"]))
            self.render_curves(); self.render_field()
            self._mark_explanation_stale("curve"); self._mark_explanation_stale("field")
            warnings = [f"Curve {index + 1}: {warning}" for index, config in enumerate(self.curve_configs) for warning in [range_warning(config)] if warning]
            count = len(self.field_outputs)
            status = f"{count} field map(s) analyzed with a shared scale"
            self.status.set(" | ".join(warnings) or status)
        except Exception as exc:
            LOGGER.exception("Integrated field generation failed", exc_info=exc)
            messagebox.showerror(
                "Field Map 생성 실패",
                "Field Map을 생성하지 못했습니다. 조건을 확인하고 다시 시도해 주세요.",
                parent=self.window,
            ); self.status.set("Generation failed")

    def _generate_curve(self, index: int) -> None:
        config = self.curve_configs[index]
        features = device_features(config)
        result = (f"Curve {index + 1}", self.curve_predictor.predict("idvd", features), self.curve_predictor.predict("idvg", features))
        if index < len(self.curve_results):
            self.curve_results[index] = result
        else:
            self.curve_results.append(result)

    def render_curves(self) -> None:
        if not self.curve_results:
            self._update_electrical_panel()
            return
        visible_results = [result for index, result in enumerate(self.curve_results) if index in self.visible_curve_indices]
        self.curve_figure.clear()
        if visible_results:
            render_curve_figure(self.curve_figure, visible_results, self.combined_curves)
        else:
            self.curve_figure.text(0.5, 0.5, "No curves selected", ha="center", va="center", fontsize=14)
        self.curve_canvas.draw_idle(); self._update_electrical_panel()

    def _update_electrical_panel(self) -> None:
        for widget in self.electrical_value_widgets:
            widget.destroy()
        self.electrical_value_widgets.clear()
        for column, (curve_label, idvd, idvg) in enumerate(self.curve_results, start=1):
            header = ttk.Label(self.electrical_panel, text=curve_label, anchor=tk.E)
            header.grid(row=0, column=column, padx=5, pady=(0, 7), sticky="e")
            self.electrical_value_widgets.append(header)
            try:
                values = extract_electrical_parameters(idvd, idvg)
                ioff = values.get("ioff_ma_per_um", 0.0)
                values["ion_ioff_ratio"] = values.get("ion_ma_per_um", 0.0) / ioff if ioff != 0 else math.inf
            except (ValueError, FloatingPointError):
                values = {}
            for row, (name, _label, _unit, factor, fmt) in enumerate(ELECTRICAL_PARAMETERS, start=1):
                text = format(values[name] * factor, fmt) if name in values else "-"
                value = ttk.Label(self.electrical_panel, text=text, width=11, anchor=tk.E)
                value.grid(row=row, column=column, padx=5, pady=3, sticky="e")
                self.electrical_value_widgets.append(value)

    def render_field(self) -> None:
        ordered_indices = self._ordered_analysis_indices("field")
        outputs = [(f"Curve {index + 1}", self.field_outputs[index]) for index in ordered_indices if index in self.field_outputs]
        if not outputs:
            return
        representative = outputs
        if len(outputs) > 2:
            selected_indices = [
                index for index in ordered_indices
                if index in self.field_outputs
            ]
            subjects = []
            for position, index in enumerate(selected_indices, start=1):
                config = self.curve_configs[index]
                subjects.append({
                    "subject_id": f"curve_{position}",
                    "display_name": f"Curve {index + 1}",
                    "device_parameters": {
                        "channel_length_nm": float(config["L"]),
                        "oxide_thickness_nm": float(config["T"]),
                        "bulk_doping_cm3": float(config["B"]),
                        "source_drain_doping_cm3": float(config["SD"]),
                        "ldd_doping_cm3": float(config["LDD"]),
                    },
                })
            plan = build_comparison_plan(subjects)
            positions = {
                f"curve_{position}": position - 1
                for position in range(1, len(outputs) + 1)
            }
            representative = [
                outputs[positions[subject_id]]
                for subject_id in plan.representative_subject_ids
            ]
        render_model_field_comparison(
            self.field_figure,
            representative,
            self.field_var.get(),
            self.scale_var.get(),
            self.range_var.get(),
            normalization_outputs=outputs,
        )
        self.field_canvas.draw_idle()


def _parse_args() -> argparse.Namespace:
    root = _root(); parser = argparse.ArgumentParser(description="Combined final curve and field-map model GUI")
    parser.add_argument("--curve-model-dir", type=Path, default=root / "ai/model_artifacts/curve_model/final/pca_xgboost")
    parser.add_argument("--field-model-dir", type=Path, default=root / "ai/model_artifacts/field_map_model/final/coordinate_mlp_physics")
    parser.add_argument("--geo-template", type=Path, default=root / "tcad/data_extraction/base_case/gmsh_mos2d.geo")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--ui-smoke-test", action="store_true", help="Construct hidden Tk widgets and verify critical controls without entering mainloop")
    parser.add_argument("--save-dir", type=Path)
    for name, default in (("L", 200.0), ("T", 20.0), ("B", 1e16), ("SD", 1e20), ("LDD", 1e18)):
        parser.add_argument(f"--{name.lower()}", type=float, default=default)
    return parser.parse_args()


def _load_runtime_models(args):
    return (
        FinalCurvePredictor(args.curve_model_dir.resolve()),
        FieldMapPredictor(args.field_model_dir.resolve()),
    )


def _load_runtime_models_async(args) -> queue.Queue:
    results: queue.Queue = queue.Queue()

    def load() -> None:
        try:
            results.put(("status", "I–V 모델을 불러오는 중입니다..."))
            curve_predictor = FinalCurvePredictor(
                args.curve_model_dir.resolve()
            )
            results.put(("status", "Field Map 모델을 불러오는 중입니다..."))
            field_predictor = FieldMapPredictor(
                args.field_model_dir.resolve()
            )
            results.put(("ready", (curve_predictor, field_predictor)))
        except Exception as exc:
            results.put(("error", exc))

    threading.Thread(
        target=load,
        name="runtime-model-loader",
        daemon=True,
    ).start()
    return results


def _start_interactive_app(args) -> int:
    window = _create_tk_window()
    window.title("Integrated AI Device Model Visualization")
    window.geometry("560x180")
    window.resizable(False, False)
    loading = ttk.Frame(window, padding=24)
    loading.pack(fill=tk.BOTH, expand=True)
    ttk.Label(
        loading,
        text="Device Model Visualization",
        font=("TkDefaultFont", 15, "bold"),
    ).pack(anchor="w")
    status_var = tk.StringVar(value="실행에 필요한 모델을 준비하고 있습니다...")
    ttk.Label(
        loading,
        textvariable=status_var,
        foreground="#4b5563",
    ).pack(anchor="w", pady=(10, 12))
    progress = ttk.Progressbar(loading, mode="indeterminate")
    progress.pack(fill=tk.X)
    progress.start(12)
    window.update_idletasks()

    results = _load_runtime_models_async(args)

    def poll_models() -> None:
        try:
            event, payload = results.get_nowait()
        except queue.Empty:
            window.after(50, poll_models)
            return
        if event == "status":
            status_var.set(str(payload))
            window.after(10, poll_models)
            return
        progress.stop()
        if event == "error":
            LOGGER.error(
                "Runtime model loading failed",
                exc_info=(type(payload), payload, payload.__traceback__),
            )
            status_var.set("모델을 불러오지 못했습니다. 설치 파일을 확인해 주세요.")
            ttk.Button(loading, text="닫기", command=window.destroy).pack(
                anchor="e", pady=(14, 0)
            )
            return
        curve_predictor, field_predictor = payload
        loading.destroy()
        window.resizable(True, True)
        IntegratedModelApp(
            window,
            curve_predictor,
            field_predictor,
            args.geo_template.resolve(),
        )

    window.after(20, poll_models)
    window.mainloop()
    return 0


def main() -> int:
    args = _parse_args()
    if not (args.ui_smoke_test or args.smoke_test or args.save_dir):
        return _start_interactive_app(args)
    curve_predictor, field_predictor = _load_runtime_models(args)
    if args.ui_smoke_test:
        window = _create_tk_window(); window.withdraw()

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        app = IntegratedModelApp(
            window,
            curve_predictor,
            field_predictor,
            args.geo_template.resolve(),
            enable_learning_persistence=False,
            auto_generate=False,
        )
        window.update_idletasks()
        original_session_id = app.case_study_panel.session.session_id
        app.case_study_panel._new_session()
        new_session_id = app.case_study_panel.session.session_id
        original_label = next(
            label
            for label, session_id in app.case_study_panel._session_choice_ids.items()
            if session_id == original_session_id
        )
        app.case_study_panel.session_choice_var.set(original_label)
        app.case_study_panel._resume_selected_session()
        session_switch_ok = (
            new_session_id != original_session_id
            and app.case_study_panel.session.session_id == original_session_id
            and len(app.case_study_panel.session_choice_box.cget("values")) == 2
        )
        app.case_study_panel.session.current_step = LearningStep.RESULT_READY
        app.case_study_panel.render()
        window.update_idletasks()
        result_notebook = next(
            (
                widget
                for widget in descendants(app.case_study_panel.body)
                if isinstance(widget, ttk.Notebook)
                and tuple(
                    widget.tab(tab_id, "text") for tab_id in widget.tabs()
                ) == ("I–V Curve", "Field Map", "AI 자유 질문")
            ),
            None,
        )
        fixed_parameters = any(
            isinstance(widget, ttk.LabelFrame)
            and str(widget.cget("text")).startswith("전기적 파라미터")
            for widget in descendants(app.case_study_panel.body)
        )
        if result_notebook is not None:
            result_notebook.select(result_notebook.tabs()[-1])
            window.update()
        app.case_study_panel.render()
        window.update_idletasks()
        restored_result_notebook = next(
            (
                widget
                for widget in descendants(app.case_study_panel.body)
                if isinstance(widget, ttk.Notebook)
                and tuple(
                    widget.tab(tab_id, "text") for tab_id in widget.tabs()
                ) == ("I–V Curve", "Field Map", "AI 자유 질문")
            ),
            None,
        )
        result_tab_preserved = (
            restored_result_notebook is not None
            and restored_result_notebook.tab(
                restored_result_notebook.select(),
                "text",
            ) == "AI 자유 질문"
        )
        app.case_study_panel.session.current_step = LearningStep.SESSION_COMPLETE
        app.case_study_panel.render()
        window.update_idletasks()
        completion_notebook = next(
            (
                widget
                for widget in app.case_study_panel.body.winfo_children()
                if isinstance(widget, ttk.Notebook)
            ),
            None,
        )
        completion_tabs = (
            tuple(
                completion_notebook.tab(tab_id, "text")
                for tab_id in completion_notebook.tabs()
            )
            if completion_notebook is not None
            else ()
        )
        result_tab_persisted = (
            app.case_study_panel.session.ui_state.get("result_view_tab")
            == "AI 자유 질문"
        )
        oxide_label = app.case_study_panel._topic_label(
            "oxide_gate_control"
        )
        app.case_study_panel.topic_choice_var.set(oxide_label)
        app.case_study_panel._switch_topic()
        multi_case_switch_ok = (
            app.case_study_panel.topic.topic_id == "oxide_gate_control"
            and app.case_study_panel.session.topic_id == "oxide_gate_control"
            and app.case_study_panel.topic.baseline_conditions["T"] == 20.0
            and app.case_study_panel.topic.comparison_conditions["T"] == 10.0
        )
        sce_label = app.case_study_panel._topic_label("sce_channel_length")
        app.case_study_panel.topic_choice_var.set(sce_label)
        app.case_study_panel._switch_topic()
        app.case_study_panel._show_cover()
        window.update_idletasks()
        checks = {
            "provider_selector_removed": not hasattr(app, "provider_box"),
            "automatic_llm_fixed": (
                not hasattr(app, "explanation_provider_var")
                and "AI 해설" in app.explanation_provider_help_var.get()
            ),
            "curve_horizontal_scroll": app.electrical_hscroll.winfo_manager() == "pack",
            "curve_prompt_hidden": not any(widget.cget("text") == "Preview LLM Prompt" for widget in app.explanation_buttons["curve"].master.winfo_children()),
            "field_prompt_hidden": not any(widget.cget("text") == "Preview LLM Prompt" for widget in app.explanation_buttons["field"].master.winfo_children()),
            "case_study_tab": "3. Case Study" in tuple(app.notebook.tab(tab_id, "text") for tab_id in app.notebook.tabs()),
            "case_study_panel": app.case_study_panel.winfo_reqwidth() > 0,
            "case_study_topic": app.case_study_panel.topic.topic_id == "sce_channel_length",
            "case_study_conditions": (
                app.case_study_panel.topic.baseline_conditions["L"] == 700.0
                and app.case_study_panel.topic.comparison_conditions["L"] == 300.0
            ),
            "case_study_session_selector": app.case_study_panel.session_choice_box.winfo_reqwidth() > 0,
            "case_study_tutor_mode": (
                "Case Study" in app.case_study_panel.tutor_mode_var.get()
                and (
                    "AI 튜터 사용 가능" in app.case_study_panel.tutor_mode_var.get()
                    or "로컬 보조 해설" in app.case_study_panel.tutor_mode_var.get()
                )
            ),
            "case_study_session_switch": session_switch_ok,
            "case_study_multi_case_switch": multi_case_switch_ok,
            "case_study_portfolio": (
                app.case_study_panel.show_cover
                and "전체 Case" in app.case_study_panel.portfolio_var.get()
                and not hasattr(app.case_study_panel, "portfolio_button")
            ),
            "case_study_fixed_parameters": fixed_parameters,
            "case_study_result_tab_preserved": result_tab_preserved,
            "case_study_result_tab_persisted": result_tab_persisted,
            "case_study_session_delete": app.case_study_panel.delete_session_button.winfo_reqwidth() > 0,
            "case_study_session_rename": app.case_study_panel.rename_session_button.winfo_reqwidth() > 0,
            "case_study_session_clone": app.case_study_panel.clone_session_button.winfo_reqwidth() > 0,
            "curve_chat_retry": app.iv_chat_retry_button.winfo_reqwidth() > 0,
            "field_chat_retry": app.field_chat_retry_button.winfo_reqwidth() > 0,
            "curve_analysis_context": (
                "SINGLE" in app.analysis_context_vars["curve"].get()
                and app.analysis_baseline_vars["curve"].get() == "Curve 1"
            ),
            "field_analysis_context": (
                "SINGLE" in app.analysis_context_vars["field"].get()
                and app.analysis_baseline_vars["field"].get() == "Curve 1"
            ),
            "case_study_completion_tabs": completion_tabs == (
                "학습 요약",
                "결과 다시 보기",
                "AI 자유 질문",
            ),
        }
        window.destroy()
        print(", ".join(f"{name}={value}" for name, value in checks.items()))
        return 0 if all(checks.values()) else 1
    if args.smoke_test or args.save_dir:
        values = {name: str(getattr(args, name.lower())) for name in PARAMETERS}; features = device_features(values)
        idvd, idvg = curve_predictor.predict("idvd", features), curve_predictor.predict("idvg", features)
        mesh = generate_gmsh_mesh(args.l, args.t, args.geo_template.resolve()); prediction = field_predictor.predict(mesh, args.l, args.t, args.b, args.sd, args.ldd)
        output = GeneratedFieldMap(mesh, prediction, args.l, args.t, args.b, args.sd, args.ldd)
        if args.save_dir:
            args.save_dir.mkdir(parents=True, exist_ok=True)
            curve_figure = Figure(figsize=(14, 8), dpi=120); FigureCanvasAgg(curve_figure); render_curve_figure(curve_figure, [("Curve 1", idvd, idvg)]); curve_figure.savefig(args.save_dir / "integrated_curve.png", dpi=150, facecolor="white")
            field_figure = Figure(figsize=(14, 8), dpi=120); FigureCanvasAgg(field_figure); render_model_field(field_figure, output, "Potential"); field_figure.savefig(args.save_dir / "integrated_fieldmap.png", dpi=150, facecolor="white")
        print(f"curve_finite={bool(np.isfinite(idvd.currents).all() and np.isfinite(idvg.currents).all())}")
        print(f"field_nodes={len(mesh.node_xy_nm)}, field_elements={len(mesh.triangles)}, field_finite={all(np.isfinite(v).all() for v in [*prediction.node_fields.values(), *prediction.element_fields.values()])}")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
