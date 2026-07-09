from __future__ import annotations

import argparse
import csv
import math
import re
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk

import matplotlib

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.tri as mtri
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.colors import LogNorm, SymLogNorm
from matplotlib.figure import Figure


@dataclass
class Mesh2D:
    points_cm: np.ndarray
    triangles: np.ndarray


@dataclass
class ZoneData:
    name: str
    x_nm: np.ndarray
    y_nm: np.ndarray
    triangles: np.ndarray
    net_doping: np.ndarray | None
    abs_net_doping: np.ndarray | None
    current_x_nm: np.ndarray | None
    current_y_nm: np.ndarray | None
    j_total: np.ndarray | None


@dataclass
class FieldData:
    zones: list[ZoneData]
    bulk: ZoneData | None


def _root(script_file: Path) -> Path:
    return script_file.resolve().parents[1]


def _parse_args() -> argparse.Namespace:
    root = _root(Path(__file__))
    parser = argparse.ArgumentParser(
        description="Interactive generated mesh, absolute doping, and total current density visualization"
    )
    parser.add_argument("--structure-id", type=str, default="L200T20")
    parser.add_argument("--doping-run-id", type=str, default="B1e16SD1e19")
    parser.add_argument("--geometry-config", type=Path, default=root / "config" / "test_geometry.csv")
    parser.add_argument("--doping-config", type=Path, default=root / "config" / "test_doping.csv")
    parser.add_argument("--runs-dir", type=Path, default=root / "runs")
    parser.add_argument(
        "--current-file",
        type=Path,
        default=None,
        help="Optional *_final.dat or gmsh_mos2d_dd.dat file",
    )
    return parser.parse_args()


def _first_matching_row(path: Path, key: str, value: str) -> dict[str, str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        first: dict[str, str] | None = None
        for row in reader:
            if first is None:
                first = row
            if (row.get(key) or "").strip() == value:
                return row
    if first is not None:
        return first
    raise ValueError(f"No rows found in {path}")


def _config_run_ids(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [
            (row.get("run_id") or "").strip()
            for row in csv.DictReader(handle)
            if (row.get("run_id") or "").strip()
        ]


def _discover_structure_ids(runs_dir: Path) -> list[str]:
    if not runs_dir.exists():
        return []
    return sorted(
        path.name
        for path in runs_dir.iterdir()
        if path.is_dir() and (path / "gmsh_mos2d.msh").exists()
    )


def _read_msh2(path: Path) -> Mesh2D:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    points: dict[int, tuple[float, float]] = {}
    triangles: list[list[int]] = []

    index = 0
    while index < len(lines):
        token = lines[index].strip()
        if token == "$Nodes":
            count = int(lines[index + 1].strip())
            for offset in range(count):
                parts = lines[index + 2 + offset].split()
                node_id = int(parts[0])
                points[node_id] = (float(parts[1]), float(parts[2]))
            index += count + 2
        elif token == "$Elements":
            count = int(lines[index + 1].strip())
            for offset in range(count):
                parts = lines[index + 2 + offset].split()
                element_type = int(parts[1])
                tag_count = int(parts[2])
                node_ids = [int(value) for value in parts[3 + tag_count :]]
                if element_type == 2 and len(node_ids) == 3:
                    triangles.append(node_ids)
            index += count + 2
        else:
            index += 1

    if not points or not triangles:
        raise ValueError(f"Could not parse 2D triangles from {path}")

    ordered_ids = sorted(points)
    id_to_index = {node_id: idx for idx, node_id in enumerate(ordered_ids)}
    point_array = np.array([points[node_id] for node_id in ordered_ids], dtype=float)
    tri_array = np.array(
        [[id_to_index[node_id] for node_id in tri] for tri in triangles],
        dtype=int,
    )
    return Mesh2D(points_cm=point_array, triangles=tri_array)


def _erfc(values: np.ndarray) -> np.ndarray:
    return np.vectorize(math.erfc, otypes=[float])(values)


def _net_doping_profile(
    geometry: dict[str, str],
    doping: dict[str, str],
    x_nm: np.ndarray,
    y_nm: np.ndarray,
) -> np.ndarray:
    device_width = 1.0e-4
    gate_width = float(geometry["gate_width"])
    diffusion_thickness = 5e-6
    device_thickness = 1e-4
    x_diffusion_decay = 2e-7
    y_diffusion_decay = 5e-7
    body_doping = 1e19

    bulk_doping = float(doping["bulk_doping"])
    source_doping = float(doping["source_doping"])
    drain_doping = float(doping["drain_doping"])

    x_cm = x_nm * 1e-7
    y_cm = y_nm * 1e-7
    x_grid, y_grid = np.meshgrid(x_cm, y_cm)

    x_center = 0.5 * device_width
    x_gate_left = x_center - 0.5 * gate_width
    x_gate_right = x_center + 0.5 * gate_width
    y_bulk_top = 0.0
    y_bulk_bottom = y_bulk_top + device_thickness
    y_diffusion = y_bulk_top + diffusion_thickness

    drain = (
        0.25
        * drain_doping
        * _erfc((x_grid - x_gate_left) / x_diffusion_decay)
        * _erfc((y_grid - y_diffusion) / y_diffusion_decay)
    )
    source = (
        0.25
        * source_doping
        * _erfc(-(x_grid - x_gate_right) / x_diffusion_decay)
        * _erfc((y_grid - y_diffusion) / y_diffusion_decay)
    )
    body = 0.5 * body_doping * _erfc(-(y_grid - y_bulk_bottom) / y_diffusion_decay)

    donors = drain + source + 1.0
    acceptors = bulk_doping + body
    return donors - acceptors


def _geometry_markers_nm(geometry: dict[str, str]) -> dict[str, float]:
    device_width = 1.0e-4
    gate_width = float(geometry["gate_width"])
    oxide_thickness = float(geometry["oxide_thickness"])
    gate_thickness = 1e-5
    diffusion_thickness = 5e-6

    x_center = 0.5 * device_width
    x_gate_left = x_center - 0.5 * gate_width
    x_gate_right = x_center + 0.5 * gate_width

    return {
        "gate_left_nm": x_gate_left * 1e7,
        "gate_right_nm": x_gate_right * 1e7,
        "oxide_top_nm": -oxide_thickness * 1e7,
        "surface_nm": 0.0,
        "gate_top_nm": -(oxide_thickness + gate_thickness) * 1e7,
        "diffusion_nm": diffusion_thickness * 1e7,
    }


def _draw_structure_overlay(
    axis,
    geometry: dict[str, str],
    text_color: str = "black",
    filled: bool = False,
) -> None:
    markers = _geometry_markers_nm(geometry)
    gate_left = markers["gate_left_nm"]
    gate_right = markers["gate_right_nm"]
    gate_width = gate_right - gate_left
    gate_top = markers["gate_top_nm"]
    oxide_top = markers["oxide_top_nm"]
    surface = markers["surface_nm"]
    diffusion = markers["diffusion_nm"]

    gate = plt.Rectangle(
        (gate_left, gate_top),
        gate_width,
        oxide_top - gate_top,
        facecolor="#d9d9d9" if filled else "none",
        edgecolor="black",
        alpha=0.7 if filled else 1.0,
        linewidth=1.4,
        zorder=8,
    )
    oxide = plt.Rectangle(
        (gate_left, oxide_top),
        gate_width,
        surface - oxide_top,
        facecolor="#9bd7ff" if filled else "none",
        edgecolor="black",
        alpha=0.45 if filled else 1.0,
        linewidth=1.1,
        linestyle="--",
        zorder=8,
    )
    axis.add_patch(gate)
    axis.add_patch(oxide)
    axis.axhline(surface, color=text_color, linewidth=1.0, linestyle="-", zorder=9)
    axis.axhline(diffusion, color=text_color, linewidth=1.0, linestyle=":", zorder=9)
    axis.axvline(gate_left, color=text_color, linewidth=1.0, linestyle="--", zorder=9)
    axis.axvline(gate_right, color=text_color, linewidth=1.0, linestyle="--", zorder=9)
    axis.text(
        0.5 * (gate_left + gate_right),
        0.5 * (gate_top + oxide_top),
        "gate",
        color=text_color,
        ha="center",
        va="center",
        fontsize=8,
        zorder=10,
    )


def _draw_material_background(axis, mesh: Mesh2D, geometry: dict[str, str]) -> None:
    xmin, xmax, _ymin, ymax = _mesh_limits_nm(mesh)
    markers = _geometry_markers_nm(geometry)
    gate_left = markers["gate_left_nm"]
    gate_right = markers["gate_right_nm"]
    gate_width = gate_right - gate_left
    gate_top = markers["gate_top_nm"]
    oxide_top = markers["oxide_top_nm"]
    surface = markers["surface_nm"]

    bulk = plt.Rectangle(
        (xmin, surface),
        xmax - xmin,
        ymax - surface,
        facecolor="#cfe8d3",
        edgecolor="none",
        alpha=0.32,
        zorder=-20,
    )
    oxide = plt.Rectangle(
        (gate_left, oxide_top),
        gate_width,
        surface - oxide_top,
        facecolor="#ccecff",
        edgecolor="none",
        alpha=0.36,
        zorder=-19,
    )
    gate = plt.Rectangle(
        (gate_left, gate_top),
        gate_width,
        oxide_top - gate_top,
        facecolor="#d8d8d8",
        edgecolor="none",
        alpha=0.34,
        zorder=-18,
    )
    axis.add_patch(bulk)
    axis.add_patch(oxide)
    axis.add_patch(gate)


def _mesh_limits_nm(mesh: Mesh2D) -> tuple[float, float, float, float]:
    points_nm = mesh.points_cm * 1e7
    return (
        float(points_nm[:, 0].min()),
        float(points_nm[:, 0].max()),
        float(points_nm[:, 1].min()),
        float(points_nm[:, 1].max()),
    )


def _apply_mesh_limits(axis, mesh: Mesh2D) -> None:
    xmin, xmax, ymin, ymax = _mesh_limits_nm(mesh)
    axis.set_xlim(xmin, xmax)
    axis.set_ylim(ymax, ymin)
    axis.set_aspect("equal", adjustable="box")


def _add_side_colorbar(fig: Figure, cbar_axis, image, label: str) -> None:
    colorbar = fig.colorbar(image, cax=cbar_axis)
    colorbar.set_label(label)


def _find_current_file(root: Path, structure_id: str, doping_run_id: str) -> Path | None:
    final_fields = root / "dataset" / "final_fields"
    if final_fields.exists():
        matches = sorted(final_fields.glob(f"{structure_id}*_final.dat"))
        if matches:
            return matches[0]

    candidates = [
        root / "dataset" / "final_fields" / f"{structure_id}_final.dat",
        root / "runs" / "_tmp_work" / structure_id / doping_run_id / "gmsh_mos2d_dd.dat",
        root / "runs" / structure_id / "gmsh_mos2d_dd.dat",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    matches = sorted((root / "runs").glob(f"**/{structure_id}/{doping_run_id}/gmsh_mos2d_dd.dat"))
    return matches[0] if matches else None


def _parse_varlocation(zone_line: str) -> set[int]:
    match = re.search(r"VARLOCATION\s*=\s*\(\s*\[([^\]]+)\]\s*=\s*CELLCENTERED", zone_line, re.IGNORECASE)
    if not match:
        return set()

    out: set[int] = set()
    for part in match.group(1).split(","):
        text = part.strip()
        if "-" in text:
            start, end = [int(value.strip()) for value in text.split("-", 1)]
            out.update(range(start - 1, end))
        else:
            out.add(int(text) - 1)
    return out


def _parse_tecplot_fields(path: Path) -> FieldData | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    var_match = re.search(r"VARIABLES\s*=\s*(.*?)(?:\n\s*ZONE|\Z)", text, re.IGNORECASE | re.DOTALL)
    if not var_match:
        return None

    variables = re.findall(r'"([^"]+)"', var_match.group(1))
    if not variables:
        return None

    lower_vars = [name.lower() for name in variables]

    def find_index(*needles: str) -> int | None:
        if len(needles) == 1:
            exact = needles[0].lower()
            for idx, name in enumerate(lower_vars):
                if name == exact:
                    return idx
        for idx, name in enumerate(lower_vars):
            if all(needle in name for needle in needles):
                return idx
        return None

    x_idx = find_index("x")
    y_idx = find_index("y")
    if x_idx is None or y_idx is None:
        return None

    net_doping_idx = find_index("netdoping")
    electron_current_x_idx = find_index("electroncurrent_x")
    electron_current_y_idx = find_index("electroncurrent_y")
    hole_current_x_idx = find_index("holecurrent_x")
    hole_current_y_idx = find_index("holecurrent_y")

    zones: list[ZoneData] = []
    zone_matches = list(
        re.finditer(
            r"ZONE[^\n]*T\s*=\s*\"([^\"]+)\"[^\n]*NODES\s*=\s*(\d+)[^\n]*ELEMENTS\s*=\s*(\d+)[^\n]*",
            text,
            re.IGNORECASE,
        )
    )
    for index, zone_match in enumerate(zone_matches):
        zone_name = zone_match.group(1)
        nodes = int(zone_match.group(2))
        elements = int(zone_match.group(3))
        zone_line = zone_match.group(0)
        cell_centered = _parse_varlocation(zone_line)
        zone_data_end = zone_matches[index + 1].start() if index + 1 < len(zone_matches) else len(text)
        zone_data = text[zone_match.end() : zone_data_end]
        tokens = zone_data.split()

        blocks: list[np.ndarray] = []
        cursor = 0
        failed = False
        for var_index in range(len(variables)):
            count = elements if var_index in cell_centered else nodes
            if cursor + count > len(tokens):
                failed = True
                break
            try:
                values = np.array([float(value) for value in tokens[cursor : cursor + count]], dtype=float)
            except ValueError:
                failed = True
                break
            blocks.append(values)
            cursor += count
        if failed or cursor + elements * 3 > len(tokens):
            continue

        try:
            triangles = np.array(
                [int(value) - 1 for value in tokens[cursor : cursor + elements * 3]],
                dtype=int,
            ).reshape(elements, 3)
        except ValueError:
            continue

        x_nm = blocks[x_idx] * 1e7
        y_nm = blocks[y_idx] * 1e7
        net_doping = blocks[net_doping_idx] if net_doping_idx is not None else None
        abs_net_doping = np.abs(net_doping) if net_doping is not None else None

        current_indices = [
            electron_current_x_idx,
            electron_current_y_idx,
            hole_current_x_idx,
            hole_current_y_idx,
        ]
        if all(current_index is not None for current_index in current_indices):
            ex = blocks[electron_current_x_idx]  # type: ignore[index]
            ey = blocks[electron_current_y_idx]  # type: ignore[index]
            hx = blocks[hole_current_x_idx]  # type: ignore[index]
            hy = blocks[hole_current_y_idx]  # type: ignore[index]
            j_total = np.sqrt((ex + hx) ** 2 + (ey + hy) ** 2)
            centroids_x = x_nm[triangles].mean(axis=1)
            centroids_y = y_nm[triangles].mean(axis=1)
        else:
            j_total = None
            centroids_x = None
            centroids_y = None

        zones.append(
            ZoneData(
                name=zone_name,
                x_nm=x_nm,
                y_nm=y_nm,
                triangles=triangles,
                net_doping=net_doping,
                abs_net_doping=abs_net_doping,
                current_x_nm=centroids_x,
                current_y_nm=centroids_y,
                j_total=j_total,
            )
        )

    if not zones:
        return None
    bulk = next((zone for zone in zones if zone.name.lower() == "bulk"), None)
    return FieldData(zones=zones, bulk=bulk)


def _plot_mesh(axis, mesh: Mesh2D, geometry: dict[str, str]) -> None:
    points_nm = mesh.points_cm * 1e7
    triangulation = mtri.Triangulation(points_nm[:, 0], points_nm[:, 1], mesh.triangles)
    _draw_material_background(axis, mesh, geometry)
    axis.triplot(triangulation, color="black", linewidth=0.25, alpha=0.88)
    _draw_structure_overlay(axis, geometry, text_color="black", filled=False)
    axis.set_title("Generated mesh")
    axis.set_xlabel("x (nm)")
    axis.set_ylabel("y (nm)")
    _apply_mesh_limits(axis, mesh)


def _plot_doping(
    fig: Figure,
    axis,
    cbar_axis,
    geometry: dict[str, str],
    doping: dict[str, str],
    mesh: Mesh2D,
    fields: FieldData | None,
    doping_display: str,
) -> None:
    show_abs = doping_display == "Abs net doping"
    field_name = "abs_net_doping" if show_abs else "net_doping"
    if fields is not None and any(getattr(zone, field_name) is not None for zone in fields.zones):
        image = None
        for zone in fields.zones:
            zone_values = getattr(zone, field_name)
            if zone_values is None:
                continue
            triangulation = mtri.Triangulation(zone.x_nm, zone.y_nm, zone.triangles)
            if show_abs:
                values = np.maximum(zone_values, 1e14)
                cmap = "viridis"
                norm = LogNorm(vmin=1e14, vmax=1e20)
            else:
                values = zone_values
                cmap = "seismic"
                norm = SymLogNorm(linthresh=1e14, vmin=-1e20, vmax=1e20)
            image = axis.tripcolor(
                triangulation,
                values,
                shading="flat",
                cmap=cmap,
                norm=norm,
            )
    else:
        x_nm = np.linspace(0, 1000, 700)
        y_nm = np.linspace(0, 1000, 500)
        net_doping = _net_doping_profile(geometry, doping, x_nm, y_nm)
        if show_abs:
            values = np.maximum(np.abs(net_doping), 1e14)
            cmap = "viridis"
            norm = LogNorm(vmin=1e14, vmax=1e20)
        else:
            values = net_doping
            cmap = "seismic"
            norm = SymLogNorm(linthresh=1e14, vmin=-1e20, vmax=1e20)
        image = axis.imshow(
            values,
            extent=[0, 1000, 1000, 0],
            aspect="auto",
            cmap=cmap,
            norm=norm,
        )

    _draw_structure_overlay(axis, geometry, text_color="black", filled=False)
    axis.set_title("|Net doping|" if show_abs else "Net doping")
    axis.set_xlabel("x (nm)")
    axis.set_ylabel("y (nm)")
    _apply_mesh_limits(axis, mesh)
    if image is not None:
        _add_side_colorbar(fig, cbar_axis, image, "cm^-3")
    else:
        cbar_axis.set_axis_off()


def _plot_current(
    fig: Figure,
    axis,
    cbar_axis,
    fields: FieldData | None,
    current_file: Path | None,
    mesh: Mesh2D,
    geometry: dict[str, str],
) -> None:
    bulk = fields.bulk if fields is not None else None
    if bulk is None or bulk.j_total is None:
        axis.set_axis_off()
        cbar_axis.set_axis_off()
        message = (
            "Total current density data not found or could not be parsed.\n\n"
            "Expected file:\n"
            "dataset/final_fields/<parameter_set>_final.dat"
        )
        if current_file is not None:
            message += f"\n\nFound but could not parse:\n{current_file}"
        axis.text(0.5, 0.5, message, ha="center", va="center", transform=axis.transAxes)
        return

    values = np.maximum(bulk.j_total, 1e-30)
    image = axis.tricontourf(bulk.current_x_nm, bulk.current_y_nm, values, levels=60, norm=LogNorm(), cmap="inferno")
    _draw_structure_overlay(axis, geometry, text_color="white", filled=False)
    axis.set_title("Total current density |Jn + Jp|")
    axis.set_xlabel("x (nm)")
    axis.set_ylabel("y (nm)")
    _apply_mesh_limits(axis, mesh)
    _add_side_colorbar(fig, cbar_axis, image, "DEVSIM export")


def _plot_structure_figure(
    fig: Figure,
    root: Path,
    runs_dir: Path,
    geometry_config: Path,
    doping_config: Path,
    structure_id: str,
    doping_run_id: str,
    doping_display: str,
    current_file_arg: Path | None,
) -> Path | None:
    fig.clear()
    structure_dir = runs_dir / structure_id
    mesh_path = structure_dir / "gmsh_mos2d.msh"
    mesh = _read_msh2(mesh_path)

    geometry = _first_matching_row(geometry_config, "run_id", structure_id)
    doping = _first_matching_row(doping_config, "run_id", doping_run_id)

    current_file = current_file_arg
    if current_file is None:
        current_file = _find_current_file(root, structure_id, doping_run_id)
    fields = _parse_tecplot_fields(current_file) if current_file and current_file.exists() else None

    grid = fig.add_gridspec(
        2,
        5,
        width_ratios=[1.15, 0.04, 1.35, 1.35, 0.04],
        height_ratios=[1, 1],
    )
    mesh_axis = fig.add_subplot(grid[0, 0])
    mesh_cbar_axis = fig.add_subplot(grid[0, 1])
    doping_axis = fig.add_subplot(grid[1, 0])
    doping_cbar_axis = fig.add_subplot(grid[1, 1])
    current_axis = fig.add_subplot(grid[:, 2:4])
    current_cbar_axis = fig.add_subplot(grid[:, 4])
    mesh_cbar_axis.set_axis_off()

    _plot_mesh(mesh_axis, mesh, geometry)
    _plot_doping(fig, doping_axis, doping_cbar_axis, geometry, doping, mesh, fields, doping_display)
    _plot_current(fig, current_axis, current_cbar_axis, fields, current_file, mesh, geometry)

    title = (
        f"{structure_id}/{doping_run_id}  "
        f"B={doping['bulk_doping']} S={doping['source_doping']} D={doping['drain_doping']}"
    )
    fig.suptitle(title)
    fig.subplots_adjust(left=0.055, right=0.975, bottom=0.07, top=0.91, wspace=0.06, hspace=0.34)
    return current_file


class StructureVisualizationApp:
    def __init__(
        self,
        root_window: tk.Tk,
        root: Path,
        runs_dir: Path,
        geometry_config: Path,
        doping_config: Path,
        initial_structure_id: str,
        initial_doping_run_id: str,
        current_file: Path | None,
    ) -> None:
        self.root_window = root_window
        self.root = root
        self.runs_dir = runs_dir
        self.geometry_config = geometry_config
        self.doping_config = doping_config
        self.current_file = current_file

        root_window.title("Structure Visualization")
        root_window.geometry("1500x900")

        self.selected_structure_id = tk.StringVar(value=initial_structure_id)
        self.selected_doping_run_id = tk.StringVar(value=initial_doping_run_id)
        self.selected_doping_display = tk.StringVar(value="Abs net doping")
        self.status_text = tk.StringVar()

        controls = ttk.Frame(root_window, padding=(10, 8))
        controls.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(controls, text="Structure").pack(side=tk.LEFT)
        self.structure_combo = ttk.Combobox(
            controls,
            textvariable=self.selected_structure_id,
            state="readonly",
            width=24,
        )
        self.structure_combo.pack(side=tk.LEFT, padx=(8, 12))
        self.structure_combo.bind("<<ComboboxSelected>>", lambda _event: self.plot_selected())

        ttk.Label(controls, text="Doping").pack(side=tk.LEFT)
        self.doping_combo = ttk.Combobox(
            controls,
            textvariable=self.selected_doping_run_id,
            state="readonly",
            width=24,
        )
        self.doping_combo.pack(side=tk.LEFT, padx=(8, 12))
        self.doping_combo.bind("<<ComboboxSelected>>", lambda _event: self.plot_selected())

        ttk.Label(controls, text="Doping map").pack(side=tk.LEFT)
        self.doping_display_combo = ttk.Combobox(
            controls,
            textvariable=self.selected_doping_display,
            state="readonly",
            values=["Abs net doping", "Net doping"],
            width=16,
        )
        self.doping_display_combo.pack(side=tk.LEFT, padx=(8, 12))
        self.doping_display_combo.bind("<<ComboboxSelected>>", lambda _event: self.plot_selected())

        ttk.Button(controls, text="Refresh", command=self.refresh).pack(side=tk.LEFT)
        ttk.Label(controls, textvariable=self.status_text).pack(side=tk.LEFT, padx=(12, 0))

        self.figure = Figure(figsize=(15, 8), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, master=root_window)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        toolbar_frame = ttk.Frame(root_window)
        toolbar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        NavigationToolbar2Tk(self.canvas, toolbar_frame)

        self.refresh()

    def refresh(self) -> None:
        structure_ids = _discover_structure_ids(self.runs_dir)
        doping_run_ids = _config_run_ids(self.doping_config)
        self.structure_combo["values"] = structure_ids
        self.doping_combo["values"] = doping_run_ids

        if self.selected_structure_id.get() not in structure_ids:
            self.selected_structure_id.set(structure_ids[0] if structure_ids else "")
        if self.selected_doping_run_id.get() not in doping_run_ids:
            self.selected_doping_run_id.set(doping_run_ids[0] if doping_run_ids else "")

        self.plot_selected()

    def plot_selected(self) -> None:
        structure_id = self.selected_structure_id.get()
        doping_run_id = self.selected_doping_run_id.get()
        doping_display = self.selected_doping_display.get()
        self.figure.clear()

        if not structure_id or not doping_run_id:
            axis = self.figure.add_subplot(111)
            axis.set_axis_off()
            axis.text(
                0.5,
                0.5,
                "No structure mesh or doping config rows found",
                ha="center",
                va="center",
                transform=axis.transAxes,
            )
            self.status_text.set("No selectable data")
            self.canvas.draw()
            return

        try:
            current_file = _plot_structure_figure(
                self.figure,
                self.root,
                self.runs_dir,
                self.geometry_config,
                self.doping_config,
                structure_id,
                doping_run_id,
                doping_display,
                self.current_file,
            )
        except Exception as exc:
            axis = self.figure.add_subplot(111)
            axis.set_axis_off()
            axis.text(0.5, 0.5, str(exc), ha="center", va="center", transform=axis.transAxes)
            self.status_text.set("Plot failed")
        else:
            if current_file is None:
                current_status = "current field: not found"
            else:
                current_status = f"current field: {current_file}"
            self.status_text.set(current_status)

        self.canvas.draw()


def main() -> None:
    args = _parse_args()
    root = _root(Path(__file__))
    window = tk.Tk()
    StructureVisualizationApp(
        root_window=window,
        root=root,
        runs_dir=args.runs_dir.resolve(),
        geometry_config=args.geometry_config.resolve(),
        doping_config=args.doping_config.resolve(),
        initial_structure_id=args.structure_id,
        initial_doping_run_id=args.doping_run_id,
        current_file=args.current_file.resolve() if args.current_file is not None else None,
    )
    window.mainloop()


if __name__ == "__main__":
    main()
