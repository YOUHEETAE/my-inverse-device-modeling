from __future__ import annotations

import numpy as np
from matplotlib.colors import hsv_to_rgb
from matplotlib.figure import Figure

from ai.curve_model.data.current_preprocessing import EVALUATION_LOG_FLOOR_MA_PER_UM
from ai.curve_model.inference import CurvePrediction


def _format_axes(axes, column: int, kind: str, sweep_name: str, fixed_name: str | None) -> None:
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


def _curve_color(curve_index: int, bias_index: int, kind: str) -> tuple[float, float, float]:
    """Encode device, curve family, and fixed voltage without random colors."""
    family_shift = 0.0 if kind == "idvd" else 0.075
    hue = (0.58 + curve_index * 0.61803398875 + family_shift) % 1.0
    base = np.asarray(hsv_to_rgb((hue, 0.78, 0.78)), dtype=float)
    if bias_index == 0:
        base = base * 0.58 + np.ones(3) * 0.42
    return tuple(float(value) for value in base)


def render_curve_figure(figure: Figure, prediction_sets: list[tuple[str, CurvePrediction, CurvePrediction]], combined: bool = True) -> None:
    figure.clear(); figure.set_facecolor("white")
    axes = figure.subplots(2, 2 if combined else 4, squeeze=False)
    floor = min(EVALUATION_LOG_FLOOR_MA_PER_UM, 1e-15)
    if combined:
        for column, kind in enumerate(("idvd", "idvg")):
            sample = prediction_sets[0][1 if kind == "idvd" else 2]
            fixed_name = "Vg" if kind == "idvd" else "Vd"; sweep_name = "Vd" if kind == "idvd" else "Vg"
            for curve_index, (curve_label, idvd, idvg) in enumerate(prediction_sets):
                prediction = idvd if kind == "idvd" else idvg
                for bias_index, (bias, current) in enumerate(zip(prediction.fixed_biases, prediction.currents, strict=True)):
                    label = f"{curve_label} · {fixed_name}={bias:g} V"
                    color = _curve_color(curve_index, bias_index, kind); linestyle = "--" if bias_index == 0 else "-"
                    axes[0, column].plot(prediction.grid, current, color=color, ls=linestyle, lw=2.0, label=label)
                    axes[1, column].plot(prediction.grid, np.maximum(np.abs(current), floor), color=color, ls=linestyle, lw=2.0, label=label)
            _format_axes(axes, column, sample.kind, sweep_name, None)
    else:
        column = 0
        for kind in ("idvd", "idvg"):
            sample = prediction_sets[0][1 if kind == "idvd" else 2]
            sweep_name = "Vd" if sample.kind == "idvd" else "Vg"; fixed_name = "Vg" if sample.kind == "idvd" else "Vd"
            for bias_index, bias in enumerate(sample.fixed_biases):
                for curve_index, (curve_label, idvd, idvg) in enumerate(prediction_sets):
                    prediction = idvd if kind == "idvd" else idvg; current = prediction.currents[bias_index]
                    color = _curve_color(curve_index, bias_index, kind); linestyle = "--" if bias_index == 0 else "-"
                    axes[0, column].plot(prediction.grid, current, color=color, ls=linestyle, lw=2.0, label=curve_label)
                    axes[1, column].plot(prediction.grid, np.maximum(np.abs(current), floor), color=color, ls=linestyle, lw=2.0, label=curve_label)
                _format_axes(axes, column, sample.kind, sweep_name, f"{fixed_name}={bias:g} V"); column += 1
    figure.suptitle("PCA + XGBoost model-generated I–V curves", fontsize=13)
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.96))
