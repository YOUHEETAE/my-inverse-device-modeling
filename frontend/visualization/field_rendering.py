from __future__ import annotations

import matplotlib.tri as mtri
import matplotlib.patheffects as path_effects
import numpy as np
from matplotlib.colors import LogNorm, Normalize, SymLogNorm, TwoSlopeNorm
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from ai.shared.field_data import (
    FIELD_DISPLAYS,
    RANGE_MODES,
    SCALE_MODES,
    GeneratedFieldMap,
    ScalarDisplay,
    finite_limits,
    geometry_markers,
    region_interpolator,
    scalar_display,
)


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
        _low, high_abs = finite_limits(plot_values, range_mode, absolute=True)
        nonzero = np.abs(plot_values[np.isfinite(plot_values) & (plot_values != 0)])
        linthresh = float(np.percentile(nonzero, 10.0)) if len(nonzero) else 1.0
        linthresh = max(linthresh, np.finfo(float).tiny)
        return plot_values, SymLogNorm(linthresh=linthresh, vmin=-high_abs, vmax=high_abs, base=10), "signed"
    low, high = finite_limits(plot_values, range_mode)
    if low < 0 < high:
        extent = max(abs(low), abs(high)); norm = TwoSlopeNorm(vmin=-extent, vcenter=0.0, vmax=extent)
    else:
        norm = Normalize(low, high)
    return plot_values, norm, "linear"


def _contrast_line(axis, orientation: str, value: float, linewidth: float, linestyle: str) -> None:
    line = axis.axhline(value, color="black", linewidth=linewidth, linestyle=linestyle, zorder=9) if orientation == "h" else axis.axvline(value, color="black", linewidth=linewidth, linestyle=linestyle, zorder=9)
    line.set_path_effects([path_effects.Stroke(linewidth=linewidth + 1.8, foreground="white"), path_effects.Normal()])


def _contact_bar(axis, x0: float, x1: float, y: float, label: str, color: str, offset: float) -> None:
    line = axis.plot([x0, x1], [y, y], color=color, linewidth=5.0, solid_capstyle="butt", zorder=12)[0]
    line.set_path_effects([path_effects.Stroke(linewidth=7.0, foreground="white"), path_effects.Normal()])
    text = axis.annotate(label, ((x0 + x1) / 2.0, y), xytext=(0, offset), textcoords="offset points", ha="center", va="center", fontsize=8, color="black", zorder=13)
    text.set_path_effects([path_effects.Stroke(linewidth=2.6, foreground="white"), path_effects.Normal()])


def _draw_structure_overlay(axis, output: GeneratedFieldMap, filled: bool = False) -> None:
    marker = geometry_markers(output)
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
    _contact_bar(axis, marker["bulk_left"], marker["bulk_right"], marker["body"], "body contact", "#2c6b2f", 10)


def _draw_material_background(axis, output: GeneratedFieldMap) -> None:
    marker = geometry_markers(output)
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


def _draw_scalar(figure: Figure, axis, colorbar_axis, output: GeneratedFieldMap, display: str, scale_mode: str, range_mode: str, shared_norm=None):
    scalar = scalar_display(output, display)
    chosen_scale = scalar.default_scale if scale_mode == "Auto" else scale_mode
    values, norm, mode_label = _normalization(scalar.values, chosen_scale, range_mode)
    if shared_norm is not None:
        norm = shared_norm
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
    if colorbar_axis is not None:
        figure.colorbar(image, cax=colorbar_axis).set_label(f"{scalar.label} [{mode_label}]")
    axis.set_title(scalar.title)
    return image, scalar, mode_label


def _draw_energy_band_pair(axes, output: GeneratedFieldMap, curve_label: str | None = None) -> None:
    mesh = output.mesh; bulk = mesh.node_region == 0
    x_min, x_max = float(mesh.node_xy_nm[bulk, 0].min()), float(mesh.node_xy_nm[bulk, 0].max())
    positive_y = mesh.node_xy_nm[bulk & (mesh.node_xy_nm[:, 1] > 1e-8), 1]
    y_channel = float(positive_y.min()) if len(positive_y) else 0.0
    x_line = np.linspace(x_min, x_max, 1000)
    bulk_interp = region_interpolator(output, 0)
    potential = np.asarray(bulk_interp(x_line, np.full_like(x_line, y_channel)).filled(np.nan))
    finite = np.isfinite(potential); reference = -float(potential[np.flatnonzero(finite)[0]]) if np.any(finite) else 0.0
    ec = -potential - reference; ev = ec - 1.12
    axes[0].plot(x_line, ec, label="$E_C$", color="#0D47A1"); axes[0].plot(x_line, ev, label="$E_V$", color="#B71C1C")
    width = x_max - x_min; gate_left = x_min + 350.0; gate_right = gate_left + output.length_nm
    axes[0].axvline(gate_left, color="0.4", ls="--"); axes[0].axvline(gate_right, color="0.4", ls="--")
    prefix = f"{curve_label} · " if curve_label else ""
    axes[0].set(title=f"{prefix}Source - Gate - Drain\ny={y_channel:.3g} nm (model approximation)", xlabel="x (nm)", ylabel="Relative energy (eV)"); axes[0].grid(alpha=0.25); axes[0].legend(fontsize=8)
    x_center = x_min + width / 2.0
    styles = {0: (0.0, 1.12, "Bulk", "#1565C0", "#C62828"), 1: (3.1, 9.0, "Oxide", "#00897B", "#6A1B9A"), 2: (0.0, 1.12, "Gate", "#42A5F5", "#EF5350")}
    for region, (offset, gap, name, ec_color, ev_color) in styles.items():
        mask = mesh.node_region == region; y_min, y_max = float(mesh.node_xy_nm[mask, 1].min()), float(mesh.node_xy_nm[mask, 1].max())
        y_line = np.linspace(y_min, y_max, 400); interpolator = region_interpolator(output, region)
        region_potential = np.asarray(interpolator(np.full_like(y_line, x_center), y_line).filled(np.nan))
        region_ec = -region_potential + offset - reference
        axes[1].plot(y_line, region_ec, color=ec_color, label=f"{name} $E_C$"); axes[1].plot(y_line, region_ec-gap, color=ev_color, label=f"{name} $E_V$")
    axes[1].axvline(-output.tox_nm, color="0.4", ls="--"); axes[1].axvline(0.0, color="0.4", ls="--")
    axes[1].set(title=f"{prefix}Gate - Oxide - Bulk\n(model approximation)", xlabel="y (nm)", ylabel="Relative energy (eV)"); axes[1].grid(alpha=0.25); axes[1].legend(fontsize=7)


def _draw_energy_bands(figure: Figure, output: GeneratedFieldMap) -> None:
    axes = figure.subplots(2, 1)
    _draw_energy_band_pair(axes, output)
    figure.subplots_adjust(left=0.09, right=0.98, bottom=0.08, top=0.86, hspace=0.42)


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


def render_model_field_comparison(
    figure: Figure,
    outputs: list[tuple[str, GeneratedFieldMap]],
    display: str,
    scale_mode: str = "Auto",
    range_mode: str = "Robust 1-99%",
    *,
    normalization_outputs: list[tuple[str, GeneratedFieldMap]] | None = None,
) -> None:
    """Render representative maps with a shared comparison normalization."""
    if not outputs:
        figure.clear(); return
    if len(outputs) == 1:
        render_model_field(figure, outputs[0][1], display, scale_mode, range_mode)
        return
    figure.clear(); figure.set_facecolor("white")
    # Use one vertical coordinate range while retaining each device's own
    # horizontal domain. Equal aspect makes the common y span set the physical
    # scale, so a shorter structure occupies less horizontal space naturally.
    all_y = np.concatenate([output.mesh.node_xy_nm[:, 1] for _label, output in outputs])
    y_min, y_max = float(np.min(all_y)), float(np.max(all_y))
    y_pad = max((y_max - y_min) * 0.02, 1.0)
    panel_widths = [
        max(float(np.ptp(output.mesh.node_xy_nm[:, 0])), 1.0)
        for _label, output in outputs
    ]

    def apply_comparison_coordinates(axis, output: GeneratedFieldMap) -> None:
        x = output.mesh.node_xy_nm[:, 0]
        x_min, x_max = float(np.min(x)), float(np.max(x))
        x_pad = max((x_max - x_min) * 0.02, 1.0)
        axis.set_xlim(x_min - x_pad, x_max + x_pad)
        axis.set_ylim(y_max + y_pad, y_min - y_pad)
        axis.set_aspect("equal", adjustable="box")

    if display == "Energy band (1D)":
        axes = figure.subplots(2, len(outputs), squeeze=False)
        for column, (label, output) in enumerate(outputs):
            _draw_energy_band_pair(axes[:, column], output, label)
            for axis in axes[:, column]:
                axis.tick_params(axis="both", labelsize=8)
                axis.xaxis.label.set_size(8); axis.yaxis.label.set_size(8)
                if column > 0:
                    axis.set_ylabel("")
        figure.subplots_adjust(left=.07, right=.98, bottom=.08, top=.88, hspace=.42, wspace=.25)
    elif display == "Mesh":
        grid = figure.add_gridspec(
            1, len(outputs), width_ratios=panel_widths,
            left=.06, right=.98, bottom=.1, top=.86, wspace=.12,
        )
        axes = [figure.add_subplot(grid[0, column]) for column in range(len(outputs))]
        for column, (axis, (label, output)) in enumerate(zip(axes, outputs, strict=True)):
            _draw_mesh(axis, output); axis.set_title(f"{label} · Generated Gmsh mesh")
            axis.set_xlabel("x (nm)"); axis.set_ylabel("y (nm)" if column == 0 else "")
            axis.tick_params(axis="both", labelsize=8); axis.xaxis.label.set_size(8); axis.yaxis.label.set_size(8)
            apply_comparison_coordinates(axis, output)
    else:
        scalars = [scalar_display(output, display) for _label, output in outputs]
        scale_sources = normalization_outputs or outputs
        scale_scalars = [
            scalar_display(output, display)
            for _label, output in scale_sources
        ]
        chosen_scale = scalars[0].default_scale if scale_mode == "Auto" else scale_mode
        combined = np.concatenate([
            np.asarray(scalar.values).reshape(-1)
            for scalar in scale_scalars
        ])
        _values, shared_norm, mode_label = _normalization(combined, chosen_scale, range_mode)
        # Reserve a fixed area for the colorbar and its label first. The two
        # device panels receive only the remaining plotting width.
        grid = figure.add_gridspec(
            1, len(outputs), width_ratios=panel_widths,
            left=.055, right=.82, bottom=.1, top=.84, wspace=.12,
        )
        image = None
        for column, (label, output) in enumerate(outputs):
            axis = figure.add_subplot(grid[0, column])
            image, scalar, _mode = _draw_scalar(figure, axis, None, output, display, scale_mode, range_mode, shared_norm)
            axis.set_title(f"{label} · {scalar.title}", fontsize=9); axis.set_xlabel("x (nm)"); axis.set_ylabel("y (nm)" if column == 0 else "")
            axis.tick_params(axis="both", labelsize=8); axis.xaxis.label.set_size(8); axis.yaxis.label.set_size(8)
            apply_comparison_coordinates(axis, output)
        colorbar_axis = figure.add_axes((.865, .14, .022, .64))
        colorbar = figure.colorbar(image, cax=colorbar_axis)
        colorbar.set_label(f"{scalars[0].label} [{mode_label}]", fontsize=8, labelpad=7)
        colorbar.ax.tick_params(labelsize=8, pad=2)
        colorbar.ax.yaxis.get_offset_text().set_fontsize(8)
    scale_note = "" if display == "Energy band (1D)" else "  |  shared y scale" if display == "Mesh" else "  |  shared y and color scales"
    figure.suptitle(f"Field-map comparison{scale_note}  |  Vg=3 V, Vd=3 V", fontsize=11)
