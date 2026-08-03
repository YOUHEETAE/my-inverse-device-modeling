from __future__ import annotations

import argparse
import csv
import logging
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from ai.field_map_model.inference import FieldMapPredictor, GeneratedMesh, generate_gmsh_mesh
from ai.shared.field_data import FIELD_DISPLAYS, RANGE_MODES, SCALE_MODES, GeneratedFieldMap
from frontend.visualization.field_rendering import render_model_field


LOGGER = logging.getLogger(__name__)


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_parameter_values(geometry_config: Path, doping_config: Path) -> dict[str, list[float]]:
    with geometry_config.open(encoding="utf-8", newline="") as handle:
        geometry = list(csv.DictReader(handle))
    with doping_config.open(encoding="utf-8", newline="") as handle:
        doping = list(csv.DictReader(handle))
    return {
        "L": sorted({float(row["gate_width"]) * 1e7 for row in geometry}),
        "Tox": sorted({float(row["oxide_thickness"]) * 1e7 for row in geometry}),
        "B": sorted({float(row["bulk_doping"]) for row in doping}),
        "SD": sorted({float(row["source_doping"]) for row in doping}),
        "LDD": sorted({float(row["LDD_doping"]) for row in doping}),
    }


def _format_parameter(value: float, doping: bool = False) -> str:
    return f"{value:.0e}".replace("+", "") if doping else f"{value:g}"


class ModelFieldMapApp:
    def __init__(self, window: tk.Tk, predictor: FieldMapPredictor, template_geo: Path, parameters: dict[str, list[float]]) -> None:
        self.window, self.predictor, self.template_geo, self.parameters = window, predictor, template_geo, parameters
        self.mesh_cache: dict[tuple[float, float], GeneratedMesh] = {}; self.output: GeneratedFieldMap | None = None
        window.title("Final field-map model visualization"); window.geometry("1500x900")
        controls = ttk.Frame(window, padding=(10, 8)); controls.pack(side=tk.TOP, fill=tk.X)
        self.vars = {name: tk.StringVar() for name in ("L", "Tox", "B", "SD", "LDD")}
        for name in self.vars:
            ttk.Label(controls, text="T" if name == "Tox" else name).pack(side=tk.LEFT)
            doping = name in {"B", "SD", "LDD"}; values = [_format_parameter(value, doping) for value in parameters[name]]
            combo = ttk.Combobox(controls, textvariable=self.vars[name], values=values, state="normal", width=9 if doping else 7)
            combo.pack(side=tk.LEFT, padx=(3, 7)); combo.bind("<<ComboboxSelected>>", lambda _event: self._dirty()); combo.bind("<KeyRelease>", lambda _event: self._dirty())
            self.vars[name].set(values[len(values) // 2])
        self.field_var = tk.StringVar(value="Potential"); self.scale_var = tk.StringVar(value="Auto"); self.range_var = tk.StringVar(value="Robust 1-99%")
        for label, variable, values, width in (("Field map", self.field_var, FIELD_DISPLAYS, 30), ("Scale", self.scale_var, SCALE_MODES, 14), ("Range", self.range_var, RANGE_MODES, 18)):
            ttk.Label(controls, text=label).pack(side=tk.LEFT, padx=(5, 0)); combo = ttk.Combobox(controls, textvariable=variable, values=values, state="readonly", width=width); combo.pack(side=tk.LEFT, padx=(3, 7)); combo.bind("<<ComboboxSelected>>", lambda _event: self.plot())
        ttk.Button(controls, text="Generate", command=self.generate).pack(side=tk.LEFT, padx=5)
        self.status = tk.StringVar(value=""); ttk.Label(window, textvariable=self.status, padding=(10, 2)).pack(side=tk.TOP, fill=tk.X)
        self.figure = Figure(figsize=(14.8, 8.0), dpi=100); self.canvas = FigureCanvasTkAgg(self.figure, master=window); self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        toolbar = ttk.Frame(window); toolbar.pack(side=tk.BOTTOM, fill=tk.X); NavigationToolbar2Tk(self.canvas, toolbar)
        window.after(50, self.generate)

    def _value(self, name: str) -> float:
        value = float(self.vars[name].get())
        if not np.isfinite(value) or value <= 0.0:
            raise ValueError(f"{'T' if name == 'Tox' else name} must be a positive finite number")
        return value

    def _extrapolation_parameters(self) -> list[str]:
        return [("T" if name == "Tox" else name) for name in self.vars if self._value(name) < min(self.parameters[name]) or self._value(name) > max(self.parameters[name])]

    def _dirty(self) -> None:
        self.status.set("Parameters changed. Press Generate to run the final model.")

    def generate(self) -> None:
        try:
            length, tox = self._value("L"), self._value("Tox"); key = (length, tox); mesh = self.mesh_cache.get(key)
            if mesh is None:
                self.status.set("Generating Gmsh mesh..."); self.window.update_idletasks(); mesh = generate_gmsh_mesh(length, tox, self.template_geo); self.mesh_cache[key] = mesh
            self.status.set("Running final field-map model..."); self.window.update_idletasks()
            prediction = self.predictor.predict(mesh, length, tox, self._value("B"), self._value("SD"), self._value("LDD"))
            self.output = GeneratedFieldMap(mesh, prediction, length, tox, self._value("B"), self._value("SD"), self._value("LDD")); self.plot()
            outside = self._extrapolation_parameters(); warning = f" Extrapolation warning: {', '.join(outside)} outside training range." if outside else " Within training parameter ranges."
            self.status.set(f"Generated {len(mesh.node_xy_nm):,} nodes / {len(mesh.triangles):,} triangles. Fixed bias: Vg=3 V, Vd=3 V.{warning}")
        except Exception as exc:
            LOGGER.exception("Field-map model generation failed", exc_info=exc)
            messagebox.showerror(
                "Field Map 생성 실패",
                "Field Map을 생성하지 못했습니다. 입력 조건을 확인하고 다시 시도해 주세요.",
            ); self.status.set("Generation failed")

    def plot(self) -> None:
        if self.output is None: return
        try:
            render_model_field(self.figure, self.output, self.field_var.get(), self.scale_var.get(), self.range_var.get()); self.canvas.draw_idle()
        except Exception as exc:
            LOGGER.exception("Field-map rendering failed", exc_info=exc)
            messagebox.showerror(
                "Field Map 표시 실패",
                "Field Map을 표시하지 못했습니다. 다시 생성해 주세요.",
            )


def _parse_args() -> argparse.Namespace:
    root = _root(); parser = argparse.ArgumentParser(description="Visualize fields generated only by the final field-map model")
    parser.add_argument("--model-dir", type=Path, default=root / "ai/model_artifacts/field_map_model/final/coordinate_mlp_physics")
    parser.add_argument("--geo-template", type=Path, default=root / "tcad/data_extraction/base_case/gmsh_mos2d.geo")
    parser.add_argument("--geometry-config", type=Path, default=root / "tcad/data_extraction/config/sweep_geometry.csv"); parser.add_argument("--doping-config", type=Path, default=root / "tcad/data_extraction/config/sweep_doping.csv")
    parser.add_argument("--length", type=float, default=1000.0); parser.add_argument("--tox", type=float, default=10.0); parser.add_argument("--bulk", type=float, default=1e16); parser.add_argument("--sd", type=float, default=5e20); parser.add_argument("--ldd", type=float, default=1e18)
    parser.add_argument("--field", choices=FIELD_DISPLAYS, default="Potential"); parser.add_argument("--scale", choices=SCALE_MODES, default="Auto"); parser.add_argument("--range", dest="range_mode", choices=RANGE_MODES, default="Robust 1-99%")
    parser.add_argument("--save", type=Path, help="Save one model-only field image instead of opening the GUI")
    return parser.parse_args()


def main() -> int:
    args = _parse_args(); predictor = FieldMapPredictor(args.model_dir.resolve())
    if args.save:
        mesh = generate_gmsh_mesh(args.length, args.tox, args.geo_template.resolve()); prediction = predictor.predict(mesh, args.length, args.tox, args.bulk, args.sd, args.ldd)
        output = GeneratedFieldMap(mesh, prediction, args.length, args.tox, args.bulk, args.sd, args.ldd)
        figure = Figure(figsize=(14, 7.5), dpi=120); FigureCanvasAgg(figure); render_model_field(figure, output, args.field, args.scale, args.range_mode)
        args.save.parent.mkdir(parents=True, exist_ok=True); figure.savefig(args.save, dpi=150, facecolor="white"); print(args.save.resolve()); return 0
    parameters = _read_parameter_values(args.geometry_config.resolve(), args.doping_config.resolve())
    window = tk.Tk(); ModelFieldMapApp(window, predictor, args.geo_template.resolve(), parameters); window.mainloop(); return 0


if __name__ == "__main__":
    raise SystemExit(main())
