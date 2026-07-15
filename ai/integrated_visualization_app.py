from __future__ import annotations

import argparse
import math
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.colors import hsv_to_rgb
from matplotlib.figure import Figure


# Support both `python ai/tools/visualization_models.py` and direct execution of
# this file from an IDE or an absolute path.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai.curve_model.data.current_preprocessing import EVALUATION_LOG_FLOOR_MA_PER_UM
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
from ai.field_map_model.inference.visualization_model_app import (
    FIELD_DISPLAYS,
    RANGE_MODES,
    SCALE_MODES,
    GeneratedFieldMap,
    render_model_field,
)


PARAMETERS = ("L", "T", "B", "SD", "LDD")
PARAMETER_TITLES = {
    "L": "L (nm)", "T": "T (nm)", "B": "B (cm⁻³)",
    "SD": "SD (cm⁻³)", "LDD": "LDD (cm⁻³)",
}
ELECTRICAL_PARAMETERS = (
    ("vth_low_v", "Vth (Vd=0.05 V)", "V", 1.0, ".5g"),
    ("vth_high_v", "Vth (Vd=1.5 V)", "V", 1.0, ".5g"),
    ("ion_ma_per_um", "Ion", "mA/µm", 1.0, ".5g"),
    ("ioff_ma_per_um", "Ioff", "mA/µm", 1.0, ".4e"),
    ("ss_mv_per_dec", "Subthreshold swing", "mV/dec", 1.0, ".5g"),
    ("dibl_gm_v_per_v", "DIBL", "mV/V", 1000.0, ".5g"),
    ("gm_max_ms_per_um", "gm max", "mS/µm", 1.0, ".5g"),
    ("gds_ms_per_um", "gds", "mS/µm", 1.0, ".5g"),
    ("ron_kohm_um", "Ron", "kΩ·µm", 1.0, ".5g"),
    ("lambda_per_v", "Channel-length modulation", "1/V", 1.0, ".5g"),
)


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _format_curve_axes(axes, column: int, kind: str, sweep_name: str, fixed_name: str | None) -> None:
    title = kind.upper() + (f" ({fixed_name})" if fixed_name else "")
    axes[0, column].set_title(f"{title} — linear")
    axes[1, column].set_title(f"{title} — log |Id|")
    axes[1, column].set_yscale("log")
    for row in range(2):
        axes[row, column].set_xlabel(f"{sweep_name} (V)")
        axes[row, column].set_ylabel("Id (mA/µm)")
        axes[row, column].grid(True, alpha=0.3, which="both")
        handles, _labels = axes[row, column].get_legend_handles_labels()
        axes[row, column].legend(fontsize=7, ncol=2 if len(handles) > 6 else 1)


def _curve_color(
    curve_index: int, bias_index: int, kind: str
) -> tuple[float, float, float]:
    """Encode device, curve family, and fixed voltage without random colors."""
    family_shift = 0.0 if kind == "idvd" else 0.075
    hue = (0.58 + curve_index * 0.61803398875 + family_shift) % 1.0
    base = np.asarray(hsv_to_rgb((hue, 0.78, 0.78)), dtype=float)
    if bias_index == 0:
        base = base * 0.58 + np.ones(3) * 0.42
    return tuple(float(value) for value in base)


def render_curve_figure(
    figure: Figure,
    prediction_sets: list[tuple[str, CurvePrediction, CurvePrediction]],
    combined: bool = True,
) -> None:
    figure.clear(); figure.set_facecolor("white")
    axes = figure.subplots(2, 2 if combined else 4, squeeze=False)
    floor = min(EVALUATION_LOG_FLOOR_MA_PER_UM, 1e-15)
    if combined:
        for column, kind in enumerate(("idvd", "idvg")):
            sample = prediction_sets[0][1 if kind == "idvd" else 2]
            fixed_name = "Vg" if kind == "idvd" else "Vd"
            sweep_name = "Vd" if kind == "idvd" else "Vg"
            for curve_index, (curve_label, idvd, idvg) in enumerate(prediction_sets):
                prediction = idvd if kind == "idvd" else idvg
                for bias_index, (bias, current) in enumerate(zip(prediction.fixed_biases, prediction.currents, strict=True)):
                    label = f"{curve_label} · {fixed_name}={bias:g} V"
                    color = _curve_color(curve_index, bias_index, kind); linestyle = "--" if bias_index == 0 else "-"
                    axes[0, column].plot(prediction.grid, current, color=color, ls=linestyle, lw=2.0, label=label)
                    axes[1, column].plot(prediction.grid, np.maximum(np.abs(current), floor), color=color, ls=linestyle, lw=2.0, label=label)
            _format_curve_axes(axes, column, sample.kind, sweep_name, None)
    else:
        column = 0
        for kind in ("idvd", "idvg"):
            sample = prediction_sets[0][1 if kind == "idvd" else 2]
            sweep_name = "Vd" if sample.kind == "idvd" else "Vg"
            fixed_name = "Vg" if sample.kind == "idvd" else "Vd"
            for bias_index, bias in enumerate(sample.fixed_biases):
                for curve_index, (curve_label, idvd, idvg) in enumerate(prediction_sets):
                    prediction = idvd if kind == "idvd" else idvg; current = prediction.currents[bias_index]
                    color = _curve_color(curve_index, bias_index, kind); linestyle = "--" if bias_index == 0 else "-"
                    axes[0, column].plot(prediction.grid, current, color=color, ls=linestyle, lw=2.0, label=curve_label)
                    axes[1, column].plot(prediction.grid, np.maximum(np.abs(current), floor), color=color, ls=linestyle, lw=2.0, label=curve_label)
                _format_curve_axes(axes, column, sample.kind, sweep_name, f"{fixed_name}={bias:g} V")
                column += 1
    figure.suptitle("Final PCA + XGBoost model-generated I–V curves", fontsize=13)
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.96))


class IntegratedModelApp:
    def __init__(
        self,
        window: tk.Tk,
        curve_predictor: FinalCurvePredictor,
        field_predictor: FieldMapPredictor,
        geo_template: Path,
    ) -> None:
        self.window = window; self.curve_predictor = curve_predictor
        self.field_predictor = field_predictor; self.geo_template = geo_template
        self.mesh_cache: dict[tuple[float, float], GeneratedMesh] = {}
        self.curve_configs: list[dict[str, str]] = [dict(DEFAULT_PARAMETERS)]
        self.curve_results: list[tuple[str, CurvePrediction, CurvePrediction]] = []
        self.active_curve_index = 0
        self.field_output: GeneratedFieldMap | None = None; self.combined_curves = True
        window.title("Integrated AI Device Model Visualization"); window.geometry("1900x980")

        top = ttk.Frame(window, padding=(10, 8)); top.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(top, text="Common device parameters", font=("TkDefaultFont", 10, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        self.parameter_vars = {name: tk.StringVar(value=DEFAULT_PARAMETERS[name]) for name in PARAMETERS}
        for name in PARAMETERS:
            ttk.Label(top, text=PARAMETER_TITLES[name]).pack(side=tk.LEFT)
            combo = ttk.Combobox(top, textvariable=self.parameter_vars[name], values=PARAMETER_OPTIONS[name], state="normal", width=11)
            combo.pack(side=tk.LEFT, padx=(3, 8)); combo.bind("<<ComboboxSelected>>", lambda _event: self._dirty()); combo.bind("<KeyRelease>", lambda _event: self._dirty()); combo.bind("<Return>", lambda _event: self.generate_all())
        ttk.Button(top, text="Generate All", command=self.generate_all).pack(side=tk.LEFT, padx=(8, 8))
        self.status = tk.StringVar(value=""); ttk.Label(top, textvariable=self.status).pack(side=tk.LEFT, padx=(5, 0))

        self.notebook = ttk.Notebook(window); self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.curve_tab = ttk.Frame(self.notebook); self.field_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.curve_tab, text="I–V Curve"); self.notebook.add(self.field_tab, text="Structure / Field Map")
        self._build_curve_tab(); self._build_field_tab(); window.after(60, self.generate_all)

    def _build_curve_tab(self) -> None:
        controls = ttk.Frame(self.curve_tab, padding=(8, 6)); controls.pack(side=tk.TOP, fill=tk.X)
        self.curve_tree = ttk.Treeview(controls, columns=("curve", *PARAMETERS), show="headings", height=3, selectmode="browse")
        widths = {"curve": 80, "L": 70, "T": 70, "B": 95, "SD": 95, "LDD": 95}
        for name in ("curve", *PARAMETERS):
            self.curve_tree.heading(name, text="Curve" if name == "curve" else name); self.curve_tree.column(name, width=widths[name], anchor=tk.CENTER, stretch=False)
        self.curve_tree.pack(side=tk.LEFT, padx=(0, 8)); self.curve_tree.bind("<<TreeviewSelect>>", self._curve_selected)
        buttons = ttk.Frame(controls); buttons.pack(side=tk.LEFT, padx=(0, 12))
        ttk.Button(buttons, text="Add Curve", command=self.add_curve).pack(fill=tk.X, pady=1)
        ttk.Button(buttons, text="Update Selected", command=self.update_selected_curve).pack(fill=tk.X, pady=1)
        ttk.Button(buttons, text="Remove Selected", command=self.remove_selected_curve).pack(fill=tk.X, pady=1)
        self.curve_view_button = ttk.Button(controls, text="Separate Biases (8 plots)", command=self.toggle_curve_view); self.curve_view_button.pack(side=tk.LEFT)
        ttk.Label(controls, text="Hue group = device · hue tint = IdVd/IdVg · light/dashed = low voltage · dark/solid = high voltage", wraplength=500).pack(side=tk.LEFT, padx=12)
        content = ttk.Frame(self.curve_tab); content.pack(fill=tk.BOTH, expand=True)
        plot_frame = ttk.Frame(content); plot_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        panel = ttk.LabelFrame(content, text="Extracted electrical parameters", padding=(8, 8)); panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 8), pady=4)
        ttk.Label(panel, text="Parameter").grid(row=0, column=0, padx=5, pady=(0, 7)); ttk.Label(panel, text="Value").grid(row=0, column=1, padx=5, pady=(0, 7))
        self.electrical_vars: dict[str, tk.StringVar] = {}
        for row, (name, label, unit, _factor, _fmt) in enumerate(ELECTRICAL_PARAMETERS, start=1):
            ttk.Label(panel, text=f"{label}\n({unit})", justify=tk.LEFT).grid(row=row, column=0, padx=5, pady=5, sticky="w")
            variable = tk.StringVar(value="-"); self.electrical_vars[name] = variable
            ttk.Label(panel, textvariable=variable, width=15, anchor=tk.E).grid(row=row, column=1, padx=5, pady=5, sticky="e")
        self.curve_figure = Figure(figsize=(14, 8), dpi=100); self.curve_canvas = FigureCanvasTkAgg(self.curve_figure, master=plot_frame); self.curve_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        toolbar = ttk.Frame(plot_frame); toolbar.pack(side=tk.BOTTOM, fill=tk.X); NavigationToolbar2Tk(self.curve_canvas, toolbar)
        self._refresh_curve_tree()

    def _build_field_tab(self) -> None:
        controls = ttk.Frame(self.field_tab, padding=(8, 6)); controls.pack(side=tk.TOP, fill=tk.X)
        self.field_var = tk.StringVar(value="Potential"); self.scale_var = tk.StringVar(value="Auto"); self.range_var = tk.StringVar(value="Robust 1-99%")
        for label, variable, values, width in (("Field map", self.field_var, FIELD_DISPLAYS, 30), ("Scale", self.scale_var, SCALE_MODES, 14), ("Range", self.range_var, RANGE_MODES, 18)):
            ttk.Label(controls, text=label).pack(side=tk.LEFT); combo = ttk.Combobox(controls, textvariable=variable, values=values, state="readonly", width=width); combo.pack(side=tk.LEFT, padx=(4, 10)); combo.bind("<<ComboboxSelected>>", lambda _event: self.render_field())
        ttk.Label(controls, text="Fixed field-map bias: Vg=3 V, Vd=3 V").pack(side=tk.LEFT, padx=12)
        self.field_figure = Figure(figsize=(15, 8), dpi=100); self.field_canvas = FigureCanvasTkAgg(self.field_figure, master=self.field_tab); self.field_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        toolbar = ttk.Frame(self.field_tab); toolbar.pack(side=tk.BOTTOM, fill=tk.X); NavigationToolbar2Tk(self.field_canvas, toolbar)

    def _dirty(self) -> None:
        self.status.set("Parameters changed. Press Generate All.")

    def _values(self) -> dict[str, str]:
        return {name: variable.get().strip() for name, variable in self.parameter_vars.items()}

    def _refresh_curve_tree(self) -> None:
        self.curve_tree.delete(*self.curve_tree.get_children())
        for index, config in enumerate(self.curve_configs):
            self.curve_tree.insert("", tk.END, iid=str(index), values=(f"Curve {index + 1}", *(config[name] for name in PARAMETERS)))
        active = min(self.active_curve_index, len(self.curve_configs) - 1); self.active_curve_index = active
        self.curve_tree.selection_set(str(active)); self.curve_tree.focus(str(active))

    def _curve_selected(self, _event=None) -> None:
        selection = self.curve_tree.selection()
        if not selection:
            return
        self.active_curve_index = int(selection[0]); config = self.curve_configs[self.active_curve_index]
        for name in PARAMETERS: self.parameter_vars[name].set(config[name])
        self._update_electrical_panel(); self.status.set(f"Curve {self.active_curve_index + 1} selected. Press Generate All after editing parameters.")

    def add_curve(self) -> None:
        self.curve_configs.append(dict(self._values())); self.active_curve_index = len(self.curve_configs) - 1
        self.curve_results = []; self._refresh_curve_tree(); self.status.set(f"Curve {self.active_curve_index + 1} added. Edit common parameters, then press Generate All.")

    def update_selected_curve(self) -> None:
        self.curve_configs[self.active_curve_index] = dict(self._values()); self.curve_results = []
        self._refresh_curve_tree(); self.status.set(f"Curve {self.active_curve_index + 1} updated. Press Generate All.")

    def remove_selected_curve(self) -> None:
        if len(self.curve_configs) == 1:
            self.status.set("At least one curve must remain."); return
        self.curve_configs.pop(self.active_curve_index); self.active_curve_index = min(self.active_curve_index, len(self.curve_configs) - 1); self.curve_results = []
        self._refresh_curve_tree(); self._curve_selected(); self.status.set("Selected curve removed. Press Generate All.")

    def toggle_curve_view(self) -> None:
        self.combined_curves = not self.combined_curves
        self.curve_view_button.configure(text="Separate Biases (8 plots)" if self.combined_curves else "Combine Biases (4 plots)")
        self.render_curves()

    def generate_all(self) -> None:
        values = self._values(); self.curve_configs[self.active_curve_index] = dict(values); self._refresh_curve_tree()
        try:
            self.status.set("Generating I–V curves..."); self.window.update_idletasks()
            self.curve_results = []
            for index, config in enumerate(self.curve_configs):
                features = device_features(config)
                self.curve_results.append((f"Curve {index + 1}", self.curve_predictor.predict("idvd", features), self.curve_predictor.predict("idvg", features)))
            length, tox = float(values["L"]), float(values["T"]); key = (length, tox)
            mesh = self.mesh_cache.get(key)
            if mesh is None:
                self.status.set("Generating Gmsh structure..."); self.window.update_idletasks(); mesh = generate_gmsh_mesh(length, tox, self.geo_template); self.mesh_cache[key] = mesh
            self.status.set("Generating field map..."); self.window.update_idletasks()
            prediction = self.field_predictor.predict(mesh, length, tox, float(values["B"]), float(values["SD"]), float(values["LDD"]))
            self.field_output = GeneratedFieldMap(mesh, prediction, length, tox, float(values["B"]), float(values["SD"]), float(values["LDD"]))
            self.render_curves(); self.render_field()
            warnings = [f"Curve {index + 1}: {warning}" for index, config in enumerate(self.curve_configs) for warning in [range_warning(config)] if warning]
            self.status.set(" | ".join(warnings) or f"{len(self.curve_configs)} curve(s) and active field map generated — {len(mesh.node_xy_nm):,} nodes / {len(mesh.triangles):,} triangles")
        except Exception as exc:
            messagebox.showerror("Integrated model generation failed", str(exc), parent=self.window); self.status.set("Generation failed")

    def render_curves(self) -> None:
        if not self.curve_results:
            return
        render_curve_figure(self.curve_figure, self.curve_results, self.combined_curves); self.curve_canvas.draw_idle(); self._update_electrical_panel()

    def _update_electrical_panel(self) -> None:
        if not self.curve_results or self.active_curve_index >= len(self.curve_results):
            for variable in self.electrical_vars.values(): variable.set("-")
            return
        try:
            _label, idvd, idvg = self.curve_results[self.active_curve_index]
            parameters = extract_electrical_parameters(idvd, idvg)
            for name, _label, _unit, factor, fmt in ELECTRICAL_PARAMETERS:
                self.electrical_vars[name].set(format(parameters[name] * factor, fmt))
        except (ValueError, FloatingPointError):
            for variable in self.electrical_vars.values(): variable.set("-")

    def render_field(self) -> None:
        if self.field_output is None:
            return
        render_model_field(self.field_figure, self.field_output, self.field_var.get(), self.scale_var.get(), self.range_var.get()); self.field_canvas.draw_idle()


def _parse_args() -> argparse.Namespace:
    root = _root(); parser = argparse.ArgumentParser(description="Combined final curve and field-map model GUI")
    parser.add_argument("--curve-model-dir", type=Path, default=root / "ai/model_artifacts/curve_model/final/pca_xgboost")
    parser.add_argument("--field-model-dir", type=Path, default=root / "ai/model_artifacts/field_map_model/final/coordinate_mlp_physics")
    parser.add_argument("--geo-template", type=Path, default=root / "tcad/data_extraction/base_case/gmsh_mos2d.geo")
    parser.add_argument("--smoke-test", action="store_true"); parser.add_argument("--save-dir", type=Path)
    for name, default in (("L", 200.0), ("T", 20.0), ("B", 1e16), ("SD", 1e20), ("LDD", 1e18)):
        parser.add_argument(f"--{name.lower()}", type=float, default=default)
    return parser.parse_args()


def main() -> int:
    args = _parse_args(); curve_predictor = FinalCurvePredictor(args.curve_model_dir.resolve()); field_predictor = FieldMapPredictor(args.field_model_dir.resolve())
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
    window = tk.Tk(); IntegratedModelApp(window, curve_predictor, field_predictor, args.geo_template.resolve()); window.mainloop(); return 0


if __name__ == "__main__":
    raise SystemExit(main())
