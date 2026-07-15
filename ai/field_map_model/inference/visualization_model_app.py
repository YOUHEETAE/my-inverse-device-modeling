from __future__ import annotations

import argparse
import csv
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk

import matplotlib.tri as mtri
import matplotlib.patheffects as path_effects
import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.colors import LogNorm, Normalize, SymLogNorm, TwoSlopeNorm
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from ai.field_map_model.inference import FieldMapPrediction, FieldMapPredictor, GeneratedMesh, generate_gmsh_mesh


FIELD_DISPLAYS = (
    "Mesh",
    "Abs net doping",
    "Net doping",
    "Potential",
    "Electric field",
    "Electron density",
    "Hole density",
    "Electron current density",
    "Hole current density",
    "Total current density",
    "SRH recombination",
    "Energy band (1D)",
)
SCALE_MODES = ("Auto", "Linear", "Log magnitude", "SymLog")
RANGE_MODES = ("Robust 1-99%", "Full range")
REGION_NAMES = ("Bulk", "Oxide", "Gate")


@dataclass(frozen=True)
class GeneratedFieldMap:
    mesh: GeneratedMesh
    prediction: FieldMapPrediction
    length_nm: float
    tox_nm: float
    bulk_doping: float
    sd_doping: float
    ldd_doping: float


@dataclass(frozen=True)
class ScalarDisplay:
    values: np.ndarray
    domain: str
    title: str
    label: str
    default_scale: str
    cmap: str


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


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
    if doping:
        return f"{value:.0e}".replace("+", "")
    return f"{value:g}"


def _scalar(output: GeneratedFieldMap, display: str) -> ScalarDisplay:
    node = output.prediction.node_fields
    element = output.prediction.element_fields
    if display == "Abs net doping":
        return ScalarDisplay(np.abs(output.prediction.net_doping), "node", display, "|NetDoping| (cm$^{-3}$)", "Log magnitude", "plasma")
    if display == "Net doping":
        return ScalarDisplay(output.prediction.net_doping, "node", display, "NetDoping (cm$^{-3}$)", "SymLog", "RdBu_r")
    if display == "Potential":
        return ScalarDisplay(node["Potential"], "node", display, "Potential (V)", "Linear", "coolwarm")
    if display == "Electric field":
        values = np.hypot(element["ElectricField_x"], element["ElectricField_y"])
        return ScalarDisplay(values, "element", "|Electric field|", "Electric field (V/cm)", "Log magnitude", "inferno")
    if display == "Electron density":
        return ScalarDisplay(node["Electrons"], "node", display, "Electrons (cm$^{-3}$)", "Log magnitude", "Blues")
    if display == "Hole density":
        return ScalarDisplay(node["Holes"], "node", display, "Holes (cm$^{-3}$)", "Log magnitude", "Reds")
    if display == "Electron current density":
        values = np.hypot(element["ElectronCurrent_x"], element["ElectronCurrent_y"])
        return ScalarDisplay(values, "element", "|Electron current density|", "|Jn| (A/cm$^2$)", "Log magnitude", "inferno")
    if display == "Hole current density":
        values = np.hypot(element["HoleCurrent_x"], element["HoleCurrent_y"])
        return ScalarDisplay(values, "element", "|Hole current density|", "|Jp| (A/cm$^2$)", "Log magnitude", "magma")
    if display == "Total current density":
        values = np.hypot(element["ElectronCurrent_x"] + element["HoleCurrent_x"], element["ElectronCurrent_y"] + element["HoleCurrent_y"])
        return ScalarDisplay(values, "element", "|Total current density|", "|Jn + Jp| (A/cm$^2$)", "Log magnitude", "inferno")
    if display == "SRH recombination":
        return ScalarDisplay(node["USRH"], "node", display, "USRH (cm$^{-3}$ s$^{-1}$)", "SymLog", "PiYG")
    raise ValueError(f"Unknown scalar display: {display}")


def _finite_limits(values: np.ndarray, range_mode: str, absolute: bool = False) -> tuple[float, float]:
    finite = np.asarray(values, dtype=np.float64)
    finite = finite[np.isfinite(finite)]
    if absolute:
        finite = np.abs(finite)
    if not len(finite):
        return 0.0, 1.0
    if range_mode == "Robust 1-99%":
        low, high = np.percentile(finite, (1.0, 99.0))
    else:
        low, high = np.min(finite), np.max(finite)
    if high <= low:
        high = low + max(abs(low) * 0.01, 1e-12)
    return float(low), float(high)


def _normalization(values: np.ndarray, scale_mode: str, range_mode: str):
    plot_values = np.asarray(values, dtype=np.float64)
    if scale_mode == "Log magnitude":
        plot_values = np.abs(plot_values)
        positive = plot_values[plot_values > 0]
        if not len(positive):
            return plot_values, Normalize(0.0, 1.0), "|value|"
        if range_mode == "Robust 1-99%":
            low, high = np.percentile(positive, (1.0, 99.0))
        else:
            low, high = np.min(positive), np.max(positive)
        low = max(float(low), np.finfo(float).tiny); high = max(float(high), low * 1.0001)
        return plot_values, LogNorm(low, high), "|value|"
    if scale_mode == "SymLog":
        _low, high_abs = _finite_limits(plot_values, range_mode, absolute=True)
        nonzero = np.abs(plot_values[np.isfinite(plot_values) & (plot_values != 0)])
        linthresh = float(np.percentile(nonzero, 10.0)) if len(nonzero) else 1.0
        linthresh = max(linthresh, np.finfo(float).tiny)
        return plot_values, SymLogNorm(linthresh=linthresh, vmin=-high_abs, vmax=high_abs, base=10), "signed"
    low, high = _finite_limits(plot_values, range_mode)
    if low < 0 < high:
        extent = max(abs(low), abs(high)); norm = TwoSlopeNorm(vmin=-extent, vcenter=0.0, vmax=extent)
    else:
        norm = Normalize(low, high)
    return plot_values, norm, "linear"


def _geometry_markers(output: GeneratedFieldMap) -> dict[str, float]:
    x = output.mesh.node_xy_nm[:, 0]
    y = output.mesh.node_xy_nm[:, 1]
    bulk = output.mesh.node_region == 0
    gate = output.mesh.node_region == 2
    bulk_left = float(np.min(x[bulk]))
    bulk_right = float(np.max(x[bulk]))
    surface = float(np.min(y[bulk]))
    body = float(np.max(y[bulk]))
    gate_left = float(np.min(x[gate]))
    gate_right = float(np.max(x[gate]))
    gate_top = float(np.min(y[gate]))
    oxide_top = -output.tox_nm
    # gmsh_mos2d.geo uses 50 nm spacers and a 50 nm contact-to-spacer gap.
    spacer_width = 50.0
    contact_gap = 50.0
    return {
        "bulk_left": bulk_left, "bulk_right": bulk_right,
        "surface": surface, "body": body,
        "gate_left": gate_left, "gate_right": gate_right,
        "gate_top": gate_top, "oxide_top": oxide_top,
        "spacer_left": gate_left - spacer_width,
        "spacer_right": gate_right + spacer_width,
        "source_contact_right": gate_left - spacer_width - contact_gap,
        "drain_contact_left": gate_right + spacer_width + contact_gap,
        "diffusion": min(surface + 50.0, body),
    }


def _contrast_line(axis, orientation: str, value: float, linewidth: float, linestyle: str) -> None:
    line = axis.axhline(value, color="black", linewidth=linewidth, linestyle=linestyle, zorder=9) if orientation == "h" else axis.axvline(value, color="black", linewidth=linewidth, linestyle=linestyle, zorder=9)
    line.set_path_effects([path_effects.Stroke(linewidth=linewidth + 1.8, foreground="white"), path_effects.Normal()])


def _contact_bar(axis, x0: float, x1: float, y: float, label: str, color: str, offset: float) -> None:
    line = axis.plot([x0, x1], [y, y], color=color, linewidth=5.0, solid_capstyle="butt", zorder=12)[0]
    line.set_path_effects([path_effects.Stroke(linewidth=7.0, foreground="white"), path_effects.Normal()])
    text = axis.annotate(label, ((x0 + x1) / 2.0, y), xytext=(0, offset), textcoords="offset points", ha="center", va="center", fontsize=8, color="black", zorder=13)
    text.set_path_effects([path_effects.Stroke(linewidth=2.6, foreground="white"), path_effects.Normal()])


def _draw_structure_overlay(axis, output: GeneratedFieldMap, filled: bool = False) -> None:
    marker = _geometry_markers(output)
    gate_left, gate_right = marker["gate_left"], marker["gate_right"]
    gate_top, oxide_top, surface = marker["gate_top"], marker["oxide_top"], marker["surface"]
    spacer_left, spacer_right = marker["spacer_left"], marker["spacer_right"]
    patches = (
        Rectangle((gate_left, gate_top), gate_right-gate_left, oxide_top-gate_top, facecolor="#d9d9d9" if filled else "none", edgecolor="black", alpha=.7 if filled else 1, linewidth=1.4, zorder=8),
        Rectangle((gate_left, oxide_top), gate_right-gate_left, surface-oxide_top, facecolor="#9bd7ff" if filled else "none", edgecolor="black", alpha=.45 if filled else 1, linewidth=1.1, linestyle="--", zorder=8),
        Rectangle((spacer_left, gate_top), gate_left-spacer_left, surface-gate_top, facecolor="#9bd7ff" if filled else "none", edgecolor="black", alpha=.32 if filled else 1, linewidth=.9, linestyle=":", zorder=8),
        Rectangle((gate_right, gate_top), spacer_right-gate_right, surface-gate_top, facecolor="#9bd7ff" if filled else "none", edgecolor="black", alpha=.32 if filled else 1, linewidth=.9, linestyle=":", zorder=8),
    )
    for patch in patches:
        axis.add_patch(patch)
    _contrast_line(axis, "h", surface, 1.0, "-")
    _contrast_line(axis, "h", marker["diffusion"], 1.0, ":")
    _contrast_line(axis, "v", gate_left, 1.0, "--")
    _contrast_line(axis, "v", gate_right, 1.0, "--")
    _contrast_line(axis, "v", spacer_left, .8, ":")
    _contrast_line(axis, "v", spacer_right, .8, ":")
    _contact_bar(axis, marker["bulk_left"], marker["source_contact_right"], surface, "source contact", "#265d9b", -12)
    _contact_bar(axis, marker["drain_contact_left"], marker["bulk_right"], surface, "drain contact", "#265d9b", -12)
    _contact_bar(axis, gate_left, gate_right, gate_top, "gate contact", "#7a4a19", -12)
    _contact_bar(axis, marker["bulk_left"], marker["bulk_right"], marker["body"], "body contact", "#2c6b2f", -14)


def _draw_material_background(axis, output: GeneratedFieldMap) -> None:
    marker = _geometry_markers(output)
    axis.add_patch(Rectangle((marker["bulk_left"], marker["surface"]), marker["bulk_right"]-marker["bulk_left"], marker["body"]-marker["surface"], facecolor="#cfe8d3", edgecolor="none", alpha=.32, zorder=-20))
    axis.add_patch(Rectangle((marker["spacer_left"], marker["gate_top"]), marker["spacer_right"]-marker["spacer_left"], marker["surface"]-marker["gate_top"], facecolor="#ccecff", edgecolor="none", alpha=.36, zorder=-19))
    axis.add_patch(Rectangle((marker["gate_left"], marker["gate_top"]), marker["gate_right"]-marker["gate_left"], marker["oxide_top"]-marker["gate_top"], facecolor="#d8d8d8", edgecolor="none", alpha=.34, zorder=-18))


def _draw_mesh(axis, output: GeneratedFieldMap) -> None:
    mesh = output.mesh
    _draw_material_background(axis, output)
    triangulation = mtri.Triangulation(mesh.node_xy_nm[:, 0], mesh.node_xy_nm[:, 1], mesh.triangles)
    axis.triplot(triangulation, color="black", linewidth=0.25, alpha=0.88)
    _draw_structure_overlay(axis, output, filled=False)
    axis.set_title("Generated Gmsh mesh")


def _element_to_node(mesh: GeneratedMesh, values: np.ndarray) -> np.ndarray:
    sums = np.zeros(len(mesh.node_xy_nm), dtype=float)
    counts = np.zeros(len(mesh.node_xy_nm), dtype=float)
    repeated = np.repeat(np.asarray(values, dtype=float), 3)
    indices = mesh.triangles.reshape(-1)
    np.add.at(sums, indices, repeated)
    np.add.at(counts, indices, 1.0)
    return np.divide(sums, counts, out=np.full_like(sums, np.nan), where=counts > 0)


def _contour_levels(norm) -> np.ndarray:
    if isinstance(norm, LogNorm):
        return np.geomspace(norm.vmin, norm.vmax, 10)
    return np.linspace(norm.vmin, norm.vmax, 11)


def _draw_scalar(figure: Figure, axis, colorbar_axis, output: GeneratedFieldMap, display: str, scale_mode: str, range_mode: str) -> None:
    scalar = _scalar(output, display)
    chosen_scale = scalar.default_scale if scale_mode == "Auto" else scale_mode
    values, norm, mode_label = _normalization(scalar.values, chosen_scale, range_mode)
    x, y, triangles = output.mesh.node_xy_nm[:, 0], output.mesh.node_xy_nm[:, 1], output.mesh.triangles
    if scalar.domain == "node":
        image = axis.tripcolor(x, y, triangles, values, shading="gouraud", cmap=scalar.cmap, norm=norm, rasterized=True)
        contour_values = values
    else:
        image = axis.tripcolor(x, y, triangles, facecolors=values, shading="flat", cmap=scalar.cmap, norm=norm, rasterized=True)
        contour_values = _element_to_node(output.mesh, values)
    try:
        triangulation = mtri.Triangulation(x, y, triangles)
        axis.tricontour(triangulation, contour_values, levels=_contour_levels(norm), colors="black", linewidths=.35, alpha=.28)
    except (ValueError, RuntimeError):
        pass
    _draw_structure_overlay(axis, output, filled=False)
    figure.colorbar(image, cax=colorbar_axis).set_label(f"{scalar.label} [{mode_label}]")
    axis.set_title(scalar.title)


def _region_interpolator(output: GeneratedFieldMap, region: int):
    triangles = output.mesh.triangles[output.mesh.element_region == region]
    triangulation = mtri.Triangulation(output.mesh.node_xy_nm[:, 0], output.mesh.node_xy_nm[:, 1], triangles)
    return mtri.LinearTriInterpolator(triangulation, output.prediction.node_fields["Potential"])


def _draw_energy_bands(figure: Figure, output: GeneratedFieldMap) -> None:
    axes = figure.subplots(1, 2)
    mesh = output.mesh; bulk = mesh.node_region == 0
    x_min, x_max = float(mesh.node_xy_nm[bulk, 0].min()), float(mesh.node_xy_nm[bulk, 0].max())
    positive_y = mesh.node_xy_nm[bulk & (mesh.node_xy_nm[:, 1] > 1e-8), 1]
    y_channel = float(positive_y.min()) if len(positive_y) else 0.0
    x_line = np.linspace(x_min, x_max, 1000)
    bulk_interp = _region_interpolator(output, 0)
    potential = np.asarray(bulk_interp(x_line, np.full_like(x_line, y_channel)).filled(np.nan))
    finite = np.isfinite(potential); reference = -float(potential[np.flatnonzero(finite)[0]]) if np.any(finite) else 0.0
    ec = -potential - reference; ev = ec - 1.12
    axes[0].plot(x_line, ec, label="$E_C$", color="#0D47A1"); axes[0].plot(x_line, ev, label="$E_V$", color="#B71C1C")
    width = x_max - x_min; gate_left = x_min + 350.0; gate_right = gate_left + output.length_nm
    axes[0].axvline(gate_left, color="0.4", ls="--"); axes[0].axvline(gate_right, color="0.4", ls="--")
    axes[0].set(title=f"Source - Gate - Drain band cut\ny={y_channel:.3g} nm (model approximation)", xlabel="x (nm)", ylabel="Relative energy (eV)"); axes[0].grid(alpha=0.25); axes[0].legend()
    x_center = x_min + width / 2.0
    styles = {0: (0.0, 1.12, "Bulk", "#1565C0", "#C62828"), 1: (3.1, 9.0, "Oxide", "#00897B", "#6A1B9A"), 2: (0.0, 1.12, "Gate", "#42A5F5", "#EF5350")}
    for region, (offset, gap, name, ec_color, ev_color) in styles.items():
        mask = mesh.node_region == region; y_min, y_max = float(mesh.node_xy_nm[mask, 1].min()), float(mesh.node_xy_nm[mask, 1].max())
        y_line = np.linspace(y_min, y_max, 400); interpolator = _region_interpolator(output, region)
        region_potential = np.asarray(interpolator(np.full_like(y_line, x_center), y_line).filled(np.nan))
        region_ec = -region_potential + offset - reference
        axes[1].plot(y_line, region_ec, color=ec_color, label=f"{name} $E_C$"); axes[1].plot(y_line, region_ec-gap, color=ev_color, label=f"{name} $E_V$")
    axes[1].axvline(-output.tox_nm, color="0.4", ls="--"); axes[1].axvline(0.0, color="0.4", ls="--")
    axes[1].set(title="Gate - Oxide - Bulk band cut\n(model approximation)", xlabel="y (nm)", ylabel="Relative energy (eV)"); axes[1].grid(alpha=0.25); axes[1].legend(fontsize=8)
    figure.subplots_adjust(left=0.07, right=0.98, bottom=0.11, top=0.82, wspace=0.25)


def render_model_field(figure: Figure, output: GeneratedFieldMap, display: str, scale_mode: str = "Auto", range_mode: str = "Robust 1-99%") -> None:
    figure.clear(); figure.set_facecolor("white")
    if display == "Energy band (1D)":
        _draw_energy_bands(figure, output)
    else:
        grid = figure.add_gridspec(1, 2, width_ratios=(1.0, 0.035), left=0.07, right=0.92, bottom=0.09, top=0.82, wspace=0.08)
        axis, colorbar_axis = figure.add_subplot(grid[0, 0]), figure.add_subplot(grid[0, 1])
        if display == "Mesh":
            colorbar_axis.set_axis_off(); _draw_mesh(axis, output)
        else:
            _draw_scalar(figure, axis, colorbar_axis, output, display, scale_mode, range_mode)
        axis.set_xlabel("x (nm)"); axis.set_ylabel("y (nm)"); axis.set_aspect("equal", adjustable="box")
        # Device convention: gate above the channel, source left, drain right.
        # The TCAD mesh stores bulk at positive y and gate at negative y, so only
        # the display y-axis is inverted; model coordinates remain unchanged.
        axis.invert_yaxis()
    figure.suptitle(f"Final field-map model  |  Vg=3 V, Vd=3 V\nL={output.length_nm:g} nm, Tox={output.tox_nm:g} nm, B={output.bulk_doping:.2g}, SD={output.sd_doping:.2g}, LDD={output.ldd_doping:.2g}", fontsize=11)


class ModelFieldMapApp:
    def __init__(self, window: tk.Tk, predictor: FieldMapPredictor, template_geo: Path, parameters: dict[str, list[float]]) -> None:
        self.window, self.predictor, self.template_geo, self.parameters = window, predictor, template_geo, parameters
        self.mesh_cache: dict[tuple[float, float], GeneratedMesh] = {}; self.output: GeneratedFieldMap | None = None
        window.title("Final field-map model visualization"); window.geometry("1500x900")
        controls = ttk.Frame(window, padding=(10, 8)); controls.pack(side=tk.TOP, fill=tk.X)
        self.vars = {name: tk.StringVar() for name in ("L", "Tox", "B", "SD", "LDD")}
        for name in ("L", "Tox", "B", "SD", "LDD"):
            ttk.Label(controls, text="T" if name == "Tox" else name).pack(side=tk.LEFT)
            doping = name in {"B", "SD", "LDD"}; values = [_format_parameter(value, doping) for value in parameters[name]]
            # The sweep values remain as suggestions, but users may enter any
            # positive continuous value supported by Gmsh/model inference.
            combo = ttk.Combobox(controls, textvariable=self.vars[name], values=values, state="normal", width=9 if doping else 7)
            combo.pack(side=tk.LEFT, padx=(3, 7)); combo.bind("<<ComboboxSelected>>", lambda _event: self._dirty())
            combo.bind("<KeyRelease>", lambda _event: self._dirty())
            self.vars[name].set(values[len(values)//2])
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
            label = "T" if name == "Tox" else name
            raise ValueError(f"{label} must be a positive finite number")
        return value

    def _extrapolation_parameters(self) -> list[str]:
        outside: list[str] = []
        for name in ("L", "Tox", "B", "SD", "LDD"):
            value = self._value(name)
            if value < min(self.parameters[name]) or value > max(self.parameters[name]):
                outside.append("T" if name == "Tox" else name)
        return outside

    def _dirty(self) -> None:
        self.status.set("Parameters changed. Press Generate to run the final model.")

    def generate(self) -> None:
        try:
            length, tox = self._value("L"), self._value("Tox")
            key = (length, tox); mesh = self.mesh_cache.get(key)
            if mesh is None:
                self.status.set("Generating Gmsh mesh..."); self.window.update_idletasks(); mesh = generate_gmsh_mesh(length, tox, self.template_geo); self.mesh_cache[key] = mesh
            self.status.set("Running final field-map model..."); self.window.update_idletasks()
            prediction = self.predictor.predict(mesh, length, tox, self._value("B"), self._value("SD"), self._value("LDD"))
            self.output = GeneratedFieldMap(mesh, prediction, length, tox, self._value("B"), self._value("SD"), self._value("LDD")); self.plot()
            outside = self._extrapolation_parameters()
            warning = f" Extrapolation warning: {', '.join(outside)} outside training range." if outside else " Within training parameter ranges."
            self.status.set(f"Generated {len(mesh.node_xy_nm):,} nodes / {len(mesh.triangles):,} triangles. Fixed bias: Vg=3 V, Vd=3 V.{warning}")
        except Exception as exc:
            messagebox.showerror("Field-map model error", str(exc)); self.status.set("Generation failed")

    def plot(self) -> None:
        if self.output is None:
            return
        try:
            render_model_field(self.figure, self.output, self.field_var.get(), self.scale_var.get(), self.range_var.get()); self.canvas.draw_idle()
        except Exception as exc:
            messagebox.showerror("Field-map plot error", str(exc))


def _parse_args() -> argparse.Namespace:
    root = _root(); parser = argparse.ArgumentParser(description="Visualize fields generated only by the final field-map model")
    parser.add_argument("--model-dir", type=Path, default=root / "ai/model_artifacts/field_map_model/final/coordinate_mlp_physics")
    parser.add_argument("--geo-template", type=Path, default=root / "tcad/data_extraction/base_case/gmsh_mos2d.geo")
    parser.add_argument("--geometry-config", type=Path, default=root / "tcad/data_extraction/config/sweep_geometry.csv")
    parser.add_argument("--doping-config", type=Path, default=root / "tcad/data_extraction/config/sweep_doping.csv")
    parser.add_argument("--length", type=float, default=1000.0); parser.add_argument("--tox", type=float, default=10.0)
    parser.add_argument("--bulk", type=float, default=1e16); parser.add_argument("--sd", type=float, default=5e20); parser.add_argument("--ldd", type=float, default=1e18)
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
