from __future__ import annotations

import tkinter as tk

# This must happen before importing other modules on this Windows conda setup;
# otherwise a different Tcl DLL can be loaded first.
_BOOTSTRAP_ROOT = tk.Tk()

import argparse
import csv
import math
import os
import re
import subprocess
import sys
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk

from run_comparison import CASES, DEFAULT_OUTPUT_DIR, STRUCTURE_ID


CASE_COLORS = {"ldd0": "#2563eb", "ldd1e18": "#dc2626"}
CASE_LINESTYLES = {"ldd0": "--", "ldd1e18": "-"}
FIELD_CHOICES = (
    "Potential",
    "Electric field magnitude",
    "Electron density",
    "Absolute net doping",
    "Energy band (surface)",
)

PARAMETER_FIELDS = (
    ("Vth @ VD=0.05 V", "vth_low_v", "V", 1.0),
    ("Vth @ VD=1.5 V", "vth_high_v", "V", 1.0),
    ("Ion", "ion_ma_per_um", "mA/μm", 1.0),
    ("Ioff", "ioff_ma_per_um", "mA/μm", 1.0),
    ("SS", "ss_mv_per_dec", "mV/dec", 1.0),
    ("DIBL", "dibl_gm_v_per_v", "mV/V", 1000.0),
    ("gm,max", "gm_max_ms_per_um", "mS/μm", 1.0),
    ("gds", "gds_ms_per_um", "mS/μm", 1.0),
    ("Ron", "ron_kohm_um", "kΩ·μm", 1.0),
    ("λ", "lambda_per_v", "1/V", 1.0),
)


def _load_plotting_stack() -> None:
    # On this Windows conda environment, importing NumPy before Tk initializes
    # can cause a different Tcl DLL to be loaded. Initialize Tk first in main(),
    # then populate these plotting globals.
    global np, mtri, FigureCanvasTkAgg, NavigationToolbar2Tk, LogNorm, Normalize, Figure
    global Rectangle, extract_parameters
    import matplotlib.tri as mtri_module
    import numpy as numpy_module
    from matplotlib.backends.backend_tkagg import (
        FigureCanvasTkAgg as figure_canvas_class,
        NavigationToolbar2Tk as navigation_toolbar_class,
    )
    from matplotlib.colors import LogNorm as log_norm_class, Normalize as normalize_class
    from matplotlib.figure import Figure as figure_class
    from matplotlib.patches import Rectangle as rectangle_class

    data_extraction_dir = Path(__file__).resolve().parents[4] / "data_extraction"
    if str(data_extraction_dir) not in sys.path:
        sys.path.insert(0, str(data_extraction_dir))
    from parameter_extraction_core import extract_parameters as extraction_function

    np = numpy_module
    mtri = mtri_module
    FigureCanvasTkAgg = figure_canvas_class
    NavigationToolbar2Tk = navigation_toolbar_class
    LogNorm = log_norm_class
    Normalize = normalize_class
    Figure = figure_class
    Rectangle = rectangle_class
    extract_parameters = extraction_function


@dataclass
class Zone:
    name: str
    x_nm: np.ndarray
    y_nm: np.ndarray
    triangles: np.ndarray
    fields: dict[str, np.ndarray]


def _case_stem(case) -> str:
    return f"{STRUCTURE_ID}{case.run_id}"


def _dataset_paths(output_dir: Path, case) -> tuple[Path, Path, Path]:
    stem = _case_stem(case)
    dataset = output_dir / "dataset"
    return (
        dataset / f"{stem}_IdVd.csv",
        dataset / f"{stem}_IdVg.csv",
        dataset / "final_fields" / f"{stem}_Vg3p0_Vd3p0.dat",
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _group_curves(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row["curve_tag"], []).append(row)
    return grouped


def _extraction_groups(
    rows: list[dict[str, str]], x_key: str
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    groups: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for tag, group in _group_curves(rows).items():
        ordered = sorted(group, key=lambda row: float(row[x_key]))
        x = np.asarray([float(row[x_key]) for row in ordered], dtype=float)
        # DEVSIM output is A/cm. Multiplication by 0.1 converts it to mA/μm.
        current = np.asarray(
            [float(row["drain_current_a_per_cm"]) * 0.1 for row in ordered],
            dtype=float,
        )
        groups[tag] = (x, current)
    return groups


def _cell_centered_variables(zone_line: str) -> set[int]:
    match = re.search(r"VARLOCATION\s*=\s*\((.*?)\)", zone_line, re.IGNORECASE)
    if not match:
        return set()
    indices: set[int] = set()
    for bracket in re.findall(r"\[([^\]]+)\]\s*=\s*CELLCENTERED", match.group(1), re.IGNORECASE):
        for item in bracket.split(","):
            item = item.strip()
            range_match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", item)
            if range_match:
                start, end = map(int, range_match.groups())
                indices.update(range(start - 1, end))
            elif item.isdigit():
                indices.add(int(item) - 1)
    return indices


def parse_tecplot(path: Path) -> list[Zone]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    variable_match = re.search(
        r"VARIABLES\s*=\s*(.*?)(?:\n\s*ZONE|\Z)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not variable_match:
        return []
    variables = re.findall(r'"([^"]+)"', variable_match.group(1))
    lowered = [name.lower() for name in variables]
    try:
        x_index = lowered.index("x")
        y_index = lowered.index("y")
    except ValueError:
        return []

    zone_matches = list(
        re.finditer(
            r"ZONE[^\n]*T\s*=\s*\"([^\"]+)\"[^\n]*"
            r"NODES\s*=\s*(\d+)[^\n]*ELEMENTS\s*=\s*(\d+)[^\n]*",
            text,
            re.IGNORECASE,
        )
    )
    zones: list[Zone] = []
    for zone_number, match in enumerate(zone_matches):
        node_count = int(match.group(2))
        element_count = int(match.group(3))
        centered = _cell_centered_variables(match.group(0))
        end = zone_matches[zone_number + 1].start() if zone_number + 1 < len(zone_matches) else len(text)
        tokens = text[match.end() : end].split()
        blocks: list[np.ndarray] = []
        cursor = 0
        try:
            for variable_index in range(len(variables)):
                count = element_count if variable_index in centered else node_count
                blocks.append(np.asarray(tokens[cursor : cursor + count], dtype=float))
                cursor += count
            triangles = (
                np.asarray(tokens[cursor : cursor + element_count * 3], dtype=int)
                .reshape(element_count, 3)
                - 1
            )
        except (ValueError, IndexError):
            continue
        if any(len(block) == 0 for block in blocks):
            continue
        zones.append(
            Zone(
                name=match.group(1),
                x_nm=blocks[x_index] * 1e7,
                y_nm=blocks[y_index] * 1e7,
                triangles=triangles,
                fields={name: blocks[index] for index, name in enumerate(variables)},
            )
        )
    return zones


def _field_values(zone: Zone, display: str) -> np.ndarray | None:
    lowered = {name.lower(): values for name, values in zone.fields.items()}
    if display == "Potential":
        return lowered.get("potential")
    if display == "Electron density":
        return lowered.get("electrons")
    if display == "Absolute net doping":
        values = lowered.get("netdoping")
        return np.abs(values) if values is not None else None
    if display == "Electric field magnitude":
        direct = lowered.get("electricfield_mag")
        if direct is not None:
            return np.abs(direct)
        x_values = lowered.get("electricfield_x")
        y_values = lowered.get("electricfield_y")
        if x_values is not None and y_values is not None:
            return np.sqrt(x_values**2 + y_values**2)
    return None


def _field_norm(all_values: list[np.ndarray], display: str):
    finite = np.concatenate(
        [values[np.isfinite(values)] for values in all_values if np.isfinite(values).any()]
    )
    if display != "Potential":
        positive = finite[finite > 0]
        if positive.size:
            low = max(float(np.percentile(positive, 5)), 1e-30)
            high = max(float(np.percentile(positive, 99.5)), low * 10)
            return LogNorm(low, high)
    low, high = np.percentile(finite, (1, 99))
    if math.isclose(float(low), float(high)):
        high = float(low) + 1.0
    return Normalize(float(low), float(high))


def _node_values(zone: Zone, values: np.ndarray) -> np.ndarray:
    if len(values) == len(zone.x_nm):
        return np.asarray(values, dtype=float)
    if len(values) != len(zone.triangles):
        return np.full(len(zone.x_nm), np.nan)
    sums = np.zeros(len(zone.x_nm), dtype=float)
    counts = np.zeros(len(zone.x_nm), dtype=float)
    for corner in range(3):
        indices = zone.triangles[:, corner]
        np.add.at(sums, indices, values)
        np.add.at(counts, indices, 1.0)
    return np.divide(sums, counts, out=np.full_like(sums, np.nan), where=counts > 0)


def _draw_device_structure(axis) -> None:
    axis.axhspan(-20, 0, color="#dbeafe", alpha=0.9, zorder=0)
    axis.add_patch(
        Rectangle(
            (350, -120),
            300,
            100,
            facecolor="#94a3b8",
            edgecolor="#334155",
            linewidth=1.1,
            alpha=0.9,
            zorder=1,
        )
    )
    axis.axhline(0, color="#0f172a", linewidth=1.0, zorder=5)
    axis.axvline(350, color="#334155", linewidth=0.8, linestyle="--", zorder=5)
    axis.axvline(650, color="#334155", linewidth=0.8, linestyle="--", zorder=5)
    axis.text(500, -70, "Gate", ha="center", va="center", fontsize=8, zorder=6)
    axis.text(55, -10, "Oxide", ha="left", va="center", fontsize=7, zorder=6)


class LDDComparisonApp:
    def __init__(self, root: tk.Tk, output_dir: Path) -> None:
        self.root = root
        self.output_dir = output_dir.resolve()
        self.field_display = tk.StringVar(value="Electric field magnitude")
        self.status = tk.StringVar(value="Ready")
        self.running = False
        self.iv_data: dict[str, tuple[list[dict[str, str]], list[dict[str, str]]]] = {}
        self.field_data: dict[str, list[Zone]] = {}
        self.extracted_parameters: dict[str, dict[str, float]] = {}
        self.parameter_vars: dict[str, tuple[tk.StringVar, tk.StringVar, tk.StringVar]] = {}

        root.title("Chapter 4 — DEVSIM LDD Comparison")
        width = min(1600, max(1100, int(root.winfo_screenwidth() * 0.9)))
        height = min(950, max(700, int(root.winfo_screenheight() * 0.86)))
        root.geometry(f"{width}x{height}")

        top = ttk.Frame(root, padding=(10, 8))
        top.pack(fill=tk.X)
        ttk.Label(
            top,
            text="L=300 nm  |  Tox=20 nm  |  B=1e16 cm⁻³  |  S/D=1e20 cm⁻³",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(side=tk.LEFT)
        self.run_button = ttk.Button(top, text="Run / rerun DEVSIM", command=self.run_simulation)
        self.run_button.pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(top, text="Reload results", command=self.reload).pack(side=tk.RIGHT)
        ttk.Label(top, textvariable=self.status).pack(side=tk.RIGHT, padx=12)

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.guide_tab = ttk.Frame(self.notebook)
        self.iv_tab = ttk.Frame(self.notebook)
        self.field_tab = ttk.Frame(self.notebook)
        self.linecut_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.guide_tab, text="1. Guide")
        self.notebook.add(self.iv_tab, text="2. I–V Curves")
        self.notebook.add(self.field_tab, text="3. Field Maps")
        self.notebook.add(self.linecut_tab, text="4. Drain-side Field")

        self._build_guide()
        self._build_iv_tab()
        self._build_field_tab()
        self.linecut_figure, self.linecut_canvas = self._figure_tab(self.linecut_tab)
        self.reload()

    def _figure_tab(self, parent) -> tuple[Figure, FigureCanvasTkAgg]:
        figure = Figure(figsize=(12, 7), dpi=100)
        canvas = FigureCanvasTkAgg(figure, master=parent)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        toolbar = ttk.Frame(parent)
        toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        NavigationToolbar2Tk(canvas, toolbar)
        return figure, canvas

    def _build_guide(self) -> None:
        container = ttk.Frame(self.guide_tab, padding=24)
        container.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            container,
            text="LDD comparison experiment",
            font=("TkDefaultFont", 18, "bold"),
        ).pack(anchor="w", pady=(0, 14))
        guide = (
            "두 소자는 mesh, gate length, oxide thickness, bulk doping, source/drain doping, "
            "그리고 bias sweep가 모두 같습니다.\n\n"
            "파란 점선: LDD = 0 cm⁻³ (abrupt extension)\n"
            "빨간 실선: LDD = 1×10¹⁸ cm⁻³\n\n"
            "확인 순서\n"
            "1. I–V Curves에서 LDD 도입 전후의 전류 차이를 확인합니다.\n"
            "2. Field Maps에서 Vg=3 V, Vd=3 V의 전위와 전기장 분포를 비교합니다.\n"
            "3. Drain-side Field에서 실리콘 표면 부근의 전기장 peak가 완화되는지 확인합니다.\n\n"
            "주의: 이 비교는 기존 drift–diffusion 모델의 범위 안에서 LDD의 전기장 완화와 "
            "직렬저항 trade-off를 관찰하기 위한 것입니다."
        )
        ttk.Label(container, text=guide, justify=tk.LEFT, wraplength=950).pack(anchor="w")

    def _build_iv_tab(self) -> None:
        parameter_panel = ttk.LabelFrame(
            self.iv_tab, text="Extracted parameters", padding=(8, 8), width=430
        )
        parameter_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 8), pady=4)
        parameter_panel.pack_propagate(False)
        headers = ("Parameter", "LDD=0", "LDD=1e18", "With − Without")
        for column, header in enumerate(headers):
            ttk.Label(
                parameter_panel,
                text=header,
                font=("TkDefaultFont", 9, "bold"),
                anchor="center",
            ).grid(row=0, column=column, padx=4, pady=(2, 8), sticky="ew")
        for row, (label, key, unit, _factor) in enumerate(PARAMETER_FIELDS, start=1):
            ttk.Label(parameter_panel, text=f"{label}\n({unit})").grid(
                row=row, column=0, padx=4, pady=5, sticky="w"
            )
            variables = (tk.StringVar(value="—"), tk.StringVar(value="—"), tk.StringVar(value="—"))
            self.parameter_vars[key] = variables
            for column, variable in enumerate(variables, start=1):
                ttk.Label(parameter_panel, textvariable=variable, anchor="e", width=12).grid(
                    row=row, column=column, padx=3, pady=5, sticky="e"
                )
        ttk.Label(
            parameter_panel,
            text="Currents are converted from A/cm to mA/μm before extraction.",
            foreground="#475569",
            wraplength=390,
            justify=tk.LEFT,
        ).grid(row=len(PARAMETER_FIELDS) + 1, column=0, columnspan=4, padx=4, pady=(12, 2), sticky="w")
        for column in range(4):
            parameter_panel.columnconfigure(column, weight=1)

        plot_frame = ttk.Frame(self.iv_tab)
        plot_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.iv_figure, self.iv_canvas = self._figure_tab(plot_frame)

    def _build_field_tab(self) -> None:
        controls = ttk.Frame(self.field_tab, padding=(10, 6))
        controls.pack(fill=tk.X)
        ttk.Label(controls, text="Field").pack(side=tk.LEFT)
        combo = ttk.Combobox(
            controls,
            textvariable=self.field_display,
            values=FIELD_CHOICES,
            state="readonly",
            width=28,
        )
        combo.pack(side=tk.LEFT, padx=6)
        combo.bind("<<ComboboxSelected>>", lambda _event: self.render_fields())
        ttk.Label(controls, text="Shared color scale  |  Vg=3 V, Vd=3 V").pack(side=tk.LEFT, padx=10)
        self.field_figure, self.field_canvas = self._figure_tab(self.field_tab)

    def reload(self) -> None:
        self.iv_data.clear()
        self.field_data.clear()
        self.extracted_parameters.clear()
        complete = 0
        for case in CASES:
            idvd_path, idvg_path, field_path = _dataset_paths(self.output_dir, case)
            idvd_rows, idvg_rows = _read_csv(idvd_path), _read_csv(idvg_path)
            zones = parse_tecplot(field_path)
            self.iv_data[case.key] = (idvd_rows, idvg_rows)
            self.field_data[case.key] = zones
            if idvd_rows and idvg_rows:
                try:
                    self.extracted_parameters[case.key] = extract_parameters(
                        _extraction_groups(idvd_rows, "drain_v"),
                        _extraction_groups(idvg_rows, "gate_v"),
                    )
                except ValueError:
                    self.extracted_parameters[case.key] = {}
            if idvd_rows and idvg_rows and zones:
                complete += 1
        self.status.set(f"{complete}/2 result sets loaded")
        self.render_iv()
        self.render_parameter_table()
        self.render_fields()
        self.render_linecut()

    def _plot_curve_groups(self, axis, rows, x_key: str, case, log: bool) -> None:
        for index, (tag, group) in enumerate(sorted(_group_curves(rows).items())):
            group = sorted(group, key=lambda row: float(row[x_key]))
            xs = np.asarray([float(row[x_key]) for row in group])
            ys = np.asarray([abs(float(row["drain_current_a_per_cm"])) for row in group])
            if log:
                ys = np.maximum(ys, 1e-30)
                axis.set_yscale("log")
            axis.plot(
                xs,
                ys,
                color=CASE_COLORS[case.key],
                linestyle=CASE_LINESTYLES[case.key],
                linewidth=1.8,
                marker=("o" if index == 0 else None),
                markersize=2.5,
                label=f"{case.label}, {tag}",
            )

    def render_iv(self) -> None:
        self.iv_figure.clear()
        axes = self.iv_figure.subplots(2, 2)
        for case in CASES:
            idvd_rows, idvg_rows = self.iv_data.get(case.key, ([], []))
            self._plot_curve_groups(axes[0, 0], idvd_rows, "drain_v", case, False)
            self._plot_curve_groups(axes[1, 0], idvd_rows, "drain_v", case, True)
            self._plot_curve_groups(axes[0, 1], idvg_rows, "gate_v", case, False)
            self._plot_curve_groups(axes[1, 1], idvg_rows, "gate_v", case, True)
        titles = ("ID–VD (linear)", "ID–VG (linear)", "ID–VD (log)", "ID–VG (log)")
        for axis, title in zip(axes.ravel(), titles):
            axis.set_title(title)
            axis.set_xlabel("VD (V)" if "VD" in title else "VG (V)")
            axis.set_ylabel("|Drain current| (A/cm)")
            axis.grid(True, alpha=0.28)
            handles, labels = axis.get_legend_handles_labels()
            if handles:
                axis.legend(fontsize=7)
        if not any(self.iv_data.get(case.key, ([], []))[0] for case in CASES):
            axes[0, 0].text(
                0.5, 0.5, "No results yet.\nPress Run / rerun DEVSIM.",
                ha="center", va="center", transform=axes[0, 0].transAxes
            )
        self.iv_figure.tight_layout()
        self.iv_canvas.draw_idle()

    def render_parameter_table(self) -> None:
        without = self.extracted_parameters.get("ldd0", {})
        with_ldd = self.extracted_parameters.get("ldd1e18", {})
        for _label, key, _unit, factor in PARAMETER_FIELDS:
            value0 = without.get(key)
            value1 = with_ldd.get(key)
            variables = self.parameter_vars[key]
            variables[0].set("—" if value0 is None else f"{value0 * factor:.5g}")
            variables[1].set("—" if value1 is None else f"{value1 * factor:.5g}")
            variables[2].set(
                "—"
                if value0 is None or value1 is None
                else f"{(value1 - value0) * factor:+.5g}"
            )

    def render_fields(self) -> None:
        self.field_figure.clear()
        axes = self.field_figure.subplots(1, 2)
        display = self.field_display.get()
        if display == "Energy band (surface)":
            self._render_energy_bands(axes)
            return
        collected: list[np.ndarray] = []
        for case in CASES:
            for zone in self.field_data.get(case.key, []):
                if display == "Electric field magnitude" and zone.name.lower() != "bulk":
                    continue
                values = _field_values(zone, display)
                if values is not None:
                    collected.append(_node_values(zone, values))
        norm = _field_norm(collected, display) if collected else None
        last_image = None
        for axis, case in zip(axes, CASES):
            zones = self.field_data.get(case.key, [])
            for zone in zones:
                if display == "Electric field magnitude" and zone.name.lower() != "bulk":
                    continue
                values = _field_values(zone, display)
                if values is None or norm is None:
                    continue
                triangulation = mtri.Triangulation(zone.x_nm, zone.y_nm, zone.triangles)
                node_values = _node_values(zone, values)
                plot_values = (
                    np.maximum(node_values, norm.vmin)
                    if isinstance(norm, LogNorm)
                    else node_values
                )
                cmap = "turbo" if display == "Electric field magnitude" else "viridis"
                last_image = axis.tripcolor(
                    triangulation,
                    plot_values,
                    shading="gouraud",
                    cmap=cmap,
                    norm=norm,
                    zorder=2,
                )
                try:
                    levels = (
                        np.geomspace(norm.vmin, norm.vmax, 9)
                        if isinstance(norm, LogNorm)
                        else np.linspace(norm.vmin, norm.vmax, 11)
                    )
                    contours = axis.tricontour(
                        triangulation,
                        plot_values,
                        levels=levels,
                        colors="white",
                        linewidths=0.55,
                        alpha=0.72,
                        zorder=4,
                    )
                    if display == "Potential":
                        axis.clabel(contours, inline=True, fontsize=6, fmt="%.2g")
                except (ValueError, RuntimeError):
                    pass
            _draw_device_structure(axis)
            axis.set_title(case.label)
            axis.set_xlabel("x (nm)")
            axis.set_ylabel("y (nm)")
            axis.set_xlim(0, 1000)
            axis.set_ylim(350, -130)
            if not zones:
                axis.text(
                    0.5, 0.5, "Field result not found",
                    ha="center", va="center", transform=axis.transAxes
                )
        self.field_figure.suptitle(f"{display} comparison (shared scale)")
        self.field_figure.subplots_adjust(left=0.07, right=0.91, bottom=0.1, top=0.88, wspace=0.18)
        if last_image is not None:
            self.field_figure.colorbar(
                last_image,
                ax=axes.ravel().tolist(),
                shrink=0.82,
                fraction=0.035,
                pad=0.025,
                label=display,
            )
        self.field_canvas.draw_idle()

    def _render_energy_bands(self, axes) -> None:
        for axis, case in zip(axes, CASES):
            bulk = next(
                (zone for zone in self.field_data.get(case.key, []) if zone.name.lower() == "bulk"),
                None,
            )
            if bulk is None:
                axis.text(0.5, 0.5, "Bulk field result not found", ha="center", va="center")
                continue
            potential = _field_values(bulk, "Potential")
            if potential is None:
                continue
            triangulation = mtri.Triangulation(bulk.x_nm, bulk.y_nm, bulk.triangles)
            interpolator = mtri.LinearTriInterpolator(triangulation, potential)
            x = np.linspace(0, 1000, 1001)
            sampled = np.ma.filled(interpolator(x, np.full_like(x, 1.0)), np.nan)
            finite = np.isfinite(sampled)
            x = x[finite]
            ec = -sampled[finite]
            if not len(x):
                continue
            ev = ec - 1.12
            axis.plot(x, ec, color="#2563eb", linewidth=1.8, label="Ec")
            axis.plot(x, ev, color="#dc2626", linewidth=1.8, label="Ev")
            axis.fill_between(x, ev, ec, color="#94a3b8", alpha=0.25, label="Si bandgap = 1.12 eV")
            axis.axvspan(350, 650, color="#f59e0b", alpha=0.10, label="Gate region")
            axis.set_title(case.label)
            axis.set_xlim(0, 1000)
            axis.set_xlabel("x (nm)")
            axis.set_ylabel("Relative energy (eV)")
            axis.grid(True, alpha=0.25)
            axis.legend(fontsize=8)
        self.field_figure.suptitle(
            "Near-surface silicon energy band diagram (Vg=3 V, Vd=3 V)"
        )
        self.field_figure.tight_layout(rect=(0, 0, 1, 0.94))
        self.field_canvas.draw_idle()

    def render_linecut(self) -> None:
        self.linecut_figure.clear()
        axis = self.linecut_figure.subplots()
        peak_lines: list[str] = []
        for case in CASES:
            bulk = next(
                (zone for zone in self.field_data.get(case.key, []) if zone.name.lower() == "bulk"),
                None,
            )
            if bulk is None:
                continue
            values = _field_values(bulk, "Electric field magnitude")
            if values is None:
                continue
            if len(values) == len(bulk.x_nm):
                xs, ys = bulk.x_nm, bulk.y_nm
            else:
                xs = bulk.x_nm[bulk.triangles].mean(axis=1)
                ys = bulk.y_nm[bulk.triangles].mean(axis=1)
            surface = np.isfinite(values) & (ys >= 0) & (ys <= 30)
            drain_side = surface & (xs >= 600) & (xs <= 850)
            if not surface.any():
                continue
            order = np.argsort(xs[surface])
            axis.plot(
                xs[surface][order],
                values[surface][order],
                color=CASE_COLORS[case.key],
                linestyle=CASE_LINESTYLES[case.key],
                linewidth=1.5,
                label=case.label,
            )
            if drain_side.any():
                peak = float(np.nanmax(values[drain_side]))
                peak_lines.append(f"{case.label}: {peak:.3e} V/cm")
        axis.axvspan(650, 850, color="#f59e0b", alpha=0.12, label="drain-side window")
        axis.set_title("Near-surface electric field (0–30 nm into silicon)")
        axis.set_xlabel("x (nm)")
        axis.set_ylabel("|E| (V/cm)")
        axis.set_xlim(250, 900)
        axis.grid(True, alpha=0.28)
        if peak_lines:
            axis.text(
                0.02, 0.98, "Drain-side peak\n" + "\n".join(peak_lines),
                transform=axis.transAxes, va="top",
                bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "#9ca3af"},
            )
        axis.legend(fontsize=8)
        self.linecut_figure.tight_layout()
        self.linecut_canvas.draw_idle()

    def run_simulation(self) -> None:
        if self.running:
            return
        if any(
            all(path.exists() for path in _dataset_paths(self.output_dir, case))
            for case in CASES
        ):
            if not messagebox.askyesno(
                "Rerun DEVSIM",
                "Existing results will be replaced. Run both cases again?",
                parent=self.root,
            ):
                return
        self.running = True
        self.run_button.configure(state=tk.DISABLED)
        self.status.set("Running DEVSIM…")

        def worker() -> None:
            command = [
                sys.executable,
                str(Path(__file__).with_name("run_comparison.py")),
                "--output-dir",
                str(self.output_dir),
                "--force",
            ]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            self.root.after(0, lambda: self._simulation_finished(completed))

        threading.Thread(target=worker, daemon=True).start()

    def _simulation_finished(self, completed: subprocess.CompletedProcess[str]) -> None:
        self.running = False
        self.run_button.configure(state=tk.NORMAL)
        if completed.returncode != 0:
            self.status.set("Simulation failed")
            messagebox.showerror(
                "DEVSIM failed",
                completed.stderr[-4000:] or completed.stdout[-4000:],
                parent=self.root,
            )
            return
        self.status.set("Simulation complete")
        self.reload()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chapter 4 LDD comparison GUI")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--ui-smoke-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    root = _BOOTSTRAP_ROOT
    _load_plotting_stack()
    if args.ui_smoke_test:
        root.withdraw()
        app = LDDComparisonApp(root, args.output_dir)
        for display in FIELD_CHOICES:
            app.field_display.set(display)
            app.render_fields()
        root.update_idletasks()
        vth_values = app.parameter_vars["vth_low_v"]
        ok = (
            len(app.notebook.tabs()) == 4
            and app.field_display.get() in FIELD_CHOICES
            and all(variable.get() != "—" for variable in vth_values)
        )
        root.destroy()
        print(f"ui_smoke_test={ok}")
        return 0 if ok else 1
    LDDComparisonApp(root, args.output_dir)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
