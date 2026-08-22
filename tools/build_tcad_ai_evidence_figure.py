from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.tri import Triangulation
from matplotlib.colors import LogNorm, Normalize
from matplotlib.ticker import LogFormatterMathtext
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai.curve_model.inference import FinalCurvePredictor
from ai.field_map_model.data import parse_tecplot_field_case
from ai.field_map_model.data.tecplot import ELEMENT_FIELD_NAMES, NODE_FIELD_NAMES
from ai.field_map_model.inference import FieldMapPredictor, GeneratedMesh
from ai.field_map_model.inference.mesh_inputs import REGION_IDS


DEVICE = {
    "L": 500.0,
    "T": 27.0,
    "B": 1.0e16,
    "SD": 1.0e20,
    "LDD": 1.0e18,
}
STEM = "L500T27B1e16SD1e20LDD1e18"
FIELD_BIAS = {"gate_v": 3.0, "drain_v": 3.0}


@dataclass(frozen=True)
class CurveSeries:
    sweep: np.ndarray
    current: np.ndarray


def _read_curve(path: Path, sweep_column: str) -> dict[str, CurveSeries]:
    grouped: dict[str, list[tuple[float, float]]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            grouped.setdefault(row["curve_tag"], []).append(
                (float(row[sweep_column]), float(row["drain_current"]))
            )
    return {
        tag: CurveSeries(
            sweep=np.asarray([item[0] for item in sorted(values)], dtype=np.float64),
            current=np.asarray([item[1] for item in sorted(values)], dtype=np.float64),
        )
        for tag, values in grouped.items()
    }


def _mesh_from_tcad(
    field_path: Path,
) -> tuple[GeneratedMesh, np.ndarray, np.ndarray, list[slice], list[slice]]:
    parsed = parse_tecplot_field_case(field_path)
    node_xy: list[np.ndarray] = []
    node_region: list[np.ndarray] = []
    triangles: list[np.ndarray] = []
    element_region: list[np.ndarray] = []
    potential: list[np.ndarray] = []
    element_fields: list[np.ndarray] = []
    zone_slices: list[slice] = []
    zone_element_slices: list[slice] = []
    node_offset = 0
    element_offset = 0
    potential_column = NODE_FIELD_NAMES.index("Potential")

    for zone in parsed.zones:
        region_name = zone.name.strip().lower()
        if region_name not in REGION_IDS:
            raise ValueError(f"Unsupported TCAD region: {zone.name}")
        coordinates_nm = np.asarray(zone.coordinates_cm, dtype=np.float64) * 1.0e7
        node_xy.append(coordinates_nm.astype(np.float32))
        node_region.append(
            np.full(len(coordinates_nm), REGION_IDS[region_name], dtype=np.uint8)
        )
        triangles.append(np.asarray(zone.triangles, dtype=np.int32) + node_offset)
        element_region.append(
            np.full(len(zone.triangles), REGION_IDS[region_name], dtype=np.uint8)
        )
        potential.append(np.asarray(zone.node_fields[:, potential_column], dtype=np.float32))
        element_fields.append(np.asarray(zone.element_fields, dtype=np.float32))
        zone_slices.append(slice(node_offset, node_offset + len(coordinates_nm)))
        zone_element_slices.append(
            slice(element_offset, element_offset + len(zone.triangles))
        )
        node_offset += len(coordinates_nm)
        element_offset += len(zone.triangles)

    combined_xy = np.concatenate(node_xy)
    combined_triangles = np.concatenate(triangles)
    return (
        GeneratedMesh(
            node_xy_nm=combined_xy,
            node_region=np.concatenate(node_region),
            triangles=combined_triangles,
            element_centroid_xy_nm=combined_xy[combined_triangles].mean(axis=1).astype(np.float32),
            element_region=np.concatenate(element_region),
        ),
        np.concatenate(potential),
        np.concatenate(element_fields),
        zone_slices,
        zone_element_slices,
    )


def _rmse(reference: np.ndarray, prediction: np.ndarray) -> float:
    return float(np.sqrt(np.mean((np.asarray(prediction) - np.asarray(reference)) ** 2)))


def _nrmse(reference: np.ndarray, prediction: np.ndarray) -> float:
    scale = float(np.max(reference) - np.min(reference))
    return _rmse(reference, prediction) / scale if scale > 0.0 else float("nan")


def _r2(reference: np.ndarray, prediction: np.ndarray) -> float:
    reference = np.asarray(reference, dtype=np.float64)
    prediction = np.asarray(prediction, dtype=np.float64)
    denominator = float(np.sum((reference - np.mean(reference)) ** 2))
    if denominator == 0.0:
        return float("nan")
    return 1.0 - float(np.sum((reference - prediction) ** 2)) / denominator


def _curve_metrics(reference: np.ndarray, prediction: np.ndarray) -> dict[str, float]:
    return {
        "rmse_mA_per_um": _rmse(reference, prediction),
        "range_normalized_rmse": _nrmse(reference, prediction),
    }


def _dataset_split(stem: str) -> str:
    archive_path = REPO_ROOT / "ai" / "model_artifacts" / "curve_model" / "dataset" / "curves.npz"
    dataset_id = stem.replace("B", "|B", 1)
    with np.load(archive_path, allow_pickle=False) as archive:
        matches = np.flatnonzero(archive["device_ids"] == dataset_id)
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one dataset entry for {dataset_id}, found {len(matches)}")
        return str(archive["split_names"][archive["device_split"][int(matches[0])]])


def _metric_panel(
    axis,
    headers: tuple[str, str, str],
    rows: list[tuple[str, str, float]],
    note: str,
) -> None:
    axis.set_axis_off()
    table = axis.table(
        cellText=[[quantity, basis, f"{value:.5f}"] for quantity, basis, value in rows],
        colLabels=list(headers),
        cellLoc="center",
        colLoc="center",
        colWidths=(0.34, 0.40, 0.26),
        bbox=(0.0, 0.34, 1.0, 0.56),
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9.0)
    for (row, _column), cell in table.get_celld().items():
        cell.set_edgecolor("#555555")
        cell.set_linewidth(1.05)
        cell.get_text().set_color("black")
        if row == 0:
            cell.set_facecolor("#e8e8e8")
            cell.get_text().set_fontweight("bold")
        else:
            cell.set_facecolor("white")
    axis.text(0.0, 0.045, note, transform=axis.transAxes, fontsize=8.0,
              color="black", va="bottom", wrap=True)


def _element_to_node(triangles: np.ndarray, values: np.ndarray, node_count: int) -> np.ndarray:
    sums = np.zeros(node_count, dtype=np.float64)
    counts = np.zeros(node_count, dtype=np.float64)
    np.add.at(sums, triangles.reshape(-1), np.repeat(values, 3))
    np.add.at(counts, triangles.reshape(-1), 1.0)
    return np.divide(sums, counts, out=np.full(node_count, np.nan), where=counts > 0)


def _total_current_density(fields: np.ndarray) -> np.ndarray:
    indices = {name: index for index, name in enumerate(ELEMENT_FIELD_NAMES)}
    total_x = fields[:, indices["ElectronCurrent_x"]] + fields[:, indices["HoleCurrent_x"]]
    total_y = fields[:, indices["ElectronCurrent_y"]] + fields[:, indices["HoleCurrent_y"]]
    return np.hypot(total_x, total_y)


def build_figure(dataset_dir: Path, output_dir: Path) -> dict[str, object]:
    idvd_path = dataset_dir / f"{STEM}_IdVd.csv"
    idvg_path = dataset_dir / f"{STEM}_IdVg.csv"
    field_path = dataset_dir / "final_fields" / f"{STEM}_IdVd_Vg3p0_Vd3p0.dat"
    for required in (idvd_path, idvg_path, field_path):
        if not required.is_file():
            raise FileNotFoundError(required)
    dataset_split = _dataset_split(STEM)
    if dataset_split != "test":
        raise ValueError(f"Evidence figure requires a held-out test device, got {dataset_split!r}")

    features = np.asarray(
        [[DEVICE["L"], DEVICE["T"], np.log10(DEVICE["B"]),
          np.log10(DEVICE["SD"]), np.log10(DEVICE["LDD"])]],
        dtype=np.float32,
    )
    curve_predictor = FinalCurvePredictor(
        REPO_ROOT / "ai" / "model_artifacts" / "curve_model" / "final" / "pca_xgboost"
    )
    idvd_ai = curve_predictor.predict("idvd", features)
    idvg_ai = curve_predictor.predict("idvg", features)
    idvd_tcad = _read_curve(idvd_path, "drain_v")
    idvg_tcad = _read_curve(idvg_path, "gate_v")

    mesh, potential_tcad, tcad_element_fields, zone_slices, zone_element_slices = (
        _mesh_from_tcad(field_path)
    )
    field_predictor = FieldMapPredictor(
        REPO_ROOT / "ai" / "model_artifacts" / "field_map_model" / "final" / "coordinate_mlp_physics"
    )
    field_ai = field_predictor.predict(
        mesh, DEVICE["L"], DEVICE["T"], DEVICE["B"], DEVICE["SD"], DEVICE["LDD"]
    )
    potential_ai = np.asarray(field_ai.node_fields["Potential"], dtype=np.float64)
    ai_element_fields = np.column_stack(
        [field_ai.element_fields[name] for name in ELEMENT_FIELD_NAMES]
    )
    current_tcad = _total_current_density(tcad_element_fields)
    current_ai = _total_current_density(ai_element_fields)

    plt.rcParams.update({
        "font.size": 10,
        "axes.titlesize": 13,
        "axes.labelsize": 10,
        "legend.fontsize": 8,
    })
    output_dir.mkdir(parents=True, exist_ok=True)
    current_floor = 1.0e-10

    curve_figure = plt.figure(figsize=(14.8, 5.2))
    curve_grid = curve_figure.add_gridspec(
        1, 3, width_ratios=(1.0, 1.0, 0.65), left=0.06, right=0.985,
        bottom=0.14, top=0.90, wspace=0.34,
    )
    curve_axes = [curve_figure.add_subplot(curve_grid[0, index]) for index in range(3)]
    curve_colors = (
        ("#78add3", "#083b66"),
        ("#f1a36f", "#8c2508"),
    )
    idvd_specs = (("IDVD_VG1P5", 1.5), ("IDVD_VG3P0", 3.0))
    idvd_metrics: dict[str, dict[str, float]] = {}
    for index, (tag, bias) in enumerate(idvd_specs):
        ai_index = int(np.flatnonzero(np.isclose(idvd_ai.fixed_biases, bias))[0])
        reference = np.abs(idvd_tcad[tag].current)
        prediction = np.abs(np.asarray(idvd_ai.currents[ai_index], dtype=np.float64))
        curve_axes[0].plot(
            idvd_tcad[tag].sweep, reference, color=curve_colors[index][0], linewidth=2.7,
            label=rf"TCAD  $V_G={bias:g}$ V", zorder=2,
        )
        curve_axes[0].plot(
            idvd_ai.grid, prediction, color=curve_colors[index][1], linewidth=2.2,
            linestyle=(0, (3.0, 1.5)), label=rf"AI  $V_G={bias:g}$ V", zorder=4,
        )
        idvd_metrics[tag] = {**_curve_metrics(reference, prediction), "r2_linear": _r2(reference, prediction)}
    curve_axes[0].set_title("(a) Output characteristics")
    curve_axes[0].set_xlabel(r"Drain voltage, $V_D$ (V)")
    curve_axes[0].set_ylabel(r"Drain current, $|I_D|$ (mA/$\mu$m)")
    curve_axes[0].grid(alpha=0.22)
    curve_axes[0].legend(frameon=False)

    idvg_specs = (("IDVG_VD0P05", 0.05), ("IDVG_VD1P5", 1.5))
    idvg_metrics: dict[str, dict[str, float]] = {}
    for index, (tag, bias) in enumerate(idvg_specs):
        ai_index = int(np.flatnonzero(np.isclose(idvg_ai.fixed_biases, bias))[0])
        reference_raw = np.abs(idvg_tcad[tag].current)
        prediction_raw = np.abs(np.asarray(idvg_ai.currents[ai_index], dtype=np.float64))
        reference = np.maximum(reference_raw, current_floor)
        prediction = np.maximum(prediction_raw, current_floor)
        curve_axes[1].semilogy(
            idvg_tcad[tag].sweep, reference, color=curve_colors[index][0], linewidth=2.7,
            label=rf"TCAD  $V_D={bias:g}$ V", zorder=2,
        )
        curve_axes[1].semilogy(
            idvg_ai.grid, prediction, color=curve_colors[index][1], linewidth=2.2,
            linestyle=(0, (3.0, 1.5)), label=rf"AI  $V_D={bias:g}$ V", zorder=4,
        )
        idvg_metrics[tag] = {
            **_curve_metrics(reference_raw, prediction_raw),
            "decade_mae": float(np.mean(np.abs(np.log10(prediction) - np.log10(reference)))),
            "r2_log10_current": _r2(np.log10(reference), np.log10(prediction)),
        }
    curve_axes[1].set_title("(b) Transfer characteristics")
    curve_axes[1].set_xlabel(r"Gate voltage, $V_G$ (V)")
    curve_axes[1].set_ylabel(r"Drain current, $|I_D|$ (mA/$\mu$m)")
    curve_axes[1].set_ylim(bottom=current_floor)
    curve_axes[1].grid(alpha=0.22, which="both")
    curve_axes[1].legend(frameon=False)
    _metric_panel(
        curve_axes[2],
        ("Curve", "Bias", r"$R^2$"),
        [
            *[("Output", rf"$V_G={bias:g}$ V", idvd_metrics[tag]["r2_linear"]) for tag, bias in idvd_specs],
            *[("Transfer", rf"$V_D={bias:g}$ V", idvg_metrics[tag]["r2_log10_current"]) for tag, bias in idvg_specs],
        ],
        "Held-out test device\nTransfer R² uses log₁₀ current\nwith a 10⁻¹⁰ mA/μm floor.",
    )
    curve_png = output_dir / "tcad_vs_ai_500nm_curves.png"
    curve_pdf = output_dir / "tcad_vs_ai_500nm_curves.pdf"
    curve_figure.savefig(curve_png, dpi=240, facecolor="white", bbox_inches="tight")
    curve_figure.savefig(curve_pdf, facecolor="white", bbox_inches="tight")
    plt.close(curve_figure)

    field_figure = plt.figure(figsize=(14.8, 5.35))
    field_grid = field_figure.add_gridspec(
        1, 3, width_ratios=(1.0, 1.0, 0.62), left=0.055, right=0.985,
        bottom=0.13, top=0.90, wspace=0.40,
    )
    field_axes = [field_figure.add_subplot(field_grid[0, index]) for index in range(3)]
    reference_style = dict(colors="#4a4a4a", linewidths=1.45, linestyles="solid", zorder=4)
    prediction_style = dict(colors="#8b0000", linewidths=1.75, linestyles="dashed", zorder=6)
    field_legend = (
        Line2D([0], [0], color="#4a4a4a", linewidth=1.6, linestyle="solid", label="TCAD"),
        Line2D([0], [0], color="#8b0000", linewidth=1.8, linestyle="dashed", label="AI"),
    )

    potential_min = float(np.min(potential_tcad))
    potential_max = float(np.max(potential_tcad))
    potential_levels = np.linspace(potential_min, potential_max, 10)
    potential_image = None
    for node_slice, element_slice in zip(zone_slices, zone_element_slices, strict=True):
        triangles = mesh.triangles[element_slice] - node_slice.start
        xy = mesh.node_xy_nm[node_slice]
        triangulation = Triangulation(xy[:, 0], xy[:, 1], triangles)
        potential_image = field_axes[0].tripcolor(
            triangulation, potential_tcad[node_slice], shading="gouraud",
            cmap="viridis", norm=Normalize(potential_min, potential_max),
            rasterized=True, zorder=1,
        )
        field_axes[0].tricontour(
            triangulation, potential_tcad[node_slice], levels=potential_levels, **reference_style
        )
        field_axes[0].tricontour(
            triangulation, potential_ai[node_slice], levels=potential_levels, **prediction_style
        )
    if potential_image is not None:
        cbar = field_figure.colorbar(potential_image, ax=field_axes[0], fraction=0.045, pad=0.025)
        cbar.ax.set_title("Potential\n(V)", fontsize=8, pad=6)
    field_axes[0].set_title("(a) Potential")
    field_axes[0].legend(handles=field_legend, frameon=False, loc="lower right")

    bulk_zone = next(
        index for index, node_slice in enumerate(zone_slices)
        if int(mesh.node_region[node_slice.start]) == REGION_IDS["bulk"]
    )
    bulk_nodes = zone_slices[bulk_zone]
    bulk_elements = zone_element_slices[bulk_zone]
    bulk_triangles = mesh.triangles[bulk_elements] - bulk_nodes.start
    bulk_xy = mesh.node_xy_nm[bulk_nodes]
    bulk_triangulation = Triangulation(bulk_xy[:, 0], bulk_xy[:, 1], bulk_triangles)
    current_tcad_bulk = np.maximum(current_tcad[bulk_elements], current_floor)
    current_ai_bulk = np.maximum(current_ai[bulk_elements], current_floor)
    current_vmin, current_vmax = np.percentile(current_tcad_bulk, (1.0, 99.0))
    current_vmin = max(float(current_vmin), current_floor)
    current_vmax = max(float(current_vmax), current_vmin * 10.0)
    current_levels = np.geomspace(current_vmin, current_vmax, 8)
    current_tcad_nodes = _element_to_node(bulk_triangles, current_tcad_bulk, len(bulk_xy))
    current_ai_nodes = _element_to_node(bulk_triangles, current_ai_bulk, len(bulk_xy))
    current_image = field_axes[1].tripcolor(
        bulk_triangulation, facecolors=current_tcad_bulk, shading="flat", cmap="magma",
        norm=LogNorm(current_vmin, current_vmax), edgecolors="none", linewidth=0.0,
        antialiased=False, rasterized=True, zorder=1,
    )
    field_axes[1].tricontour(
        bulk_triangulation, current_tcad_nodes, levels=current_levels, **reference_style
    )
    field_axes[1].tricontour(
        bulk_triangulation, current_ai_nodes, levels=current_levels, **prediction_style
    )
    cbar = field_figure.colorbar(current_image, ax=field_axes[1], fraction=0.045, pad=0.025)
    min_exponent = int(np.ceil(np.log10(current_vmin)))
    max_exponent = int(np.floor(np.log10(current_vmax)))
    tick_exponents = np.unique(np.rint(np.linspace(min_exponent, max_exponent, 5)).astype(int))
    cbar.set_ticks(10.0 ** tick_exponents)
    cbar.ax.yaxis.set_major_formatter(LogFormatterMathtext())
    cbar.ax.set_title(r"$|J_n+J_p|$" + "\n" + r"(A/cm$^2$)", fontsize=8, pad=6)
    field_axes[1].set_title("(b) Total current density")
    field_axes[1].legend(handles=field_legend, frameon=False, loc="lower right")

    for axis in field_axes[:2]:
        axis.set_xlabel("x (nm)")
        axis.set_ylabel("y (nm)")
        axis.set_xlim(0.0, 1200.0)
        axis.set_ylim(600.0, -100.0)
        axis.set_aspect("equal", adjustable="box")

    potential_r2 = _r2(potential_tcad, potential_ai)
    current_log_r2 = _r2(np.log10(current_tcad_bulk), np.log10(current_ai_bulk))
    _metric_panel(
        field_axes[2],
        ("Field", "Basis", r"$R^2$"),
        [
            ("Potential", "Linear", potential_r2),
            (r"Total $|J|$", r"$\log_{10}$", current_log_r2),
        ],
        "Vg = 3 V, Vd = 3 V\nSame TCAD mesh coordinates\nCurrent density: semiconductor region,\n10⁻¹⁰ A/cm² floor.",
    )
    field_png = output_dir / "tcad_vs_ai_500nm_fields.png"
    field_pdf = output_dir / "tcad_vs_ai_500nm_fields.pdf"
    field_figure.savefig(field_png, dpi=240, facecolor="white", bbox_inches="tight")
    field_figure.savefig(field_pdf, facecolor="white", bbox_inches="tight")
    plt.close(field_figure)

    metrics: dict[str, object] = {
        "device": DEVICE,
        "dataset_split": dataset_split,
        "field_bias_v": FIELD_BIAS,
        "source_files": {"idvd": str(idvd_path), "idvg": str(idvg_path), "field": str(field_path)},
        "curve_metrics": {"idvd": idvd_metrics, "idvg": idvg_metrics},
        "field_metrics": {
            "potential": {
                "node_count": int(len(potential_tcad)),
                "rmse_v": _rmse(potential_tcad, potential_ai),
                "range_normalized_rmse": _nrmse(potential_tcad, potential_ai),
                "r2_linear": potential_r2,
            },
            "total_current_density": {
                "domain": "bulk semiconductor elements only",
                "element_count": int(len(current_tcad_bulk)),
                "display_and_r2_floor_a_per_cm2": current_floor,
                "r2_log10": current_log_r2,
                "robust_contour_range_a_per_cm2": [current_vmin, current_vmax],
            },
        },
        "plot_rules": {
            "tcad_line": "light solid",
            "ai_line": "dark dashed, drawn above TCAD",
            "field_mesh": "TCAD native mesh; AI evaluated at the same coordinates",
            "global_title_and_device_footer": "omitted",
        },
        "outputs": {
            "curve_png": str(curve_png), "curve_pdf": str(curve_pdf),
            "field_png": str(field_png), "field_pdf": str(field_pdf),
        },
    }
    (output_dir / "tcad_vs_ai_500nm_metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Build separate Curve and Field TCAD-vs-AI evidence figures.")
    parser.add_argument("--dataset-dir", type=Path, default=Path(r"D:\IDM\dataset"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "docs" / "technical_validation" / "tcad_ai_evidence",
    )
    args = parser.parse_args()
    metrics = build_figure(args.dataset_dir.resolve(), args.output_dir.resolve())
    print(json.dumps(metrics["outputs"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
