from __future__ import annotations

import numpy as np
from matplotlib.colors import hsv_to_rgb
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from ai.curve_model.data.current_preprocessing import EVALUATION_LOG_FLOOR_MA_PER_UM
from ai.curve_model.inference import CurvePrediction


def _format_axes(
    axes,
    column: int,
    kind: str,
    sweep_name: str,
    fixed_name: str | None,
    legend_handles: list[Line2D],
) -> None:
    title = kind.upper() + (f" ({fixed_name})" if fixed_name else "")
    axes[0, column].set_title(f"{title} — linear")
    axes[1, column].set_title(f"{title} — log |Id|")
    axes[1, column].set_yscale("log")
    for row in range(2):
        axes[row, column].set_xlabel(f"{sweep_name} (V)")
        axes[row, column].set_ylabel("Id (mA/µm)")
        axes[row, column].grid(True, alpha=0.3, which="both")
        axes[row, column].legend(
            handles=legend_handles,
            fontsize=7,
            ncol=2 if len(legend_handles) > 4 else 1,
            framealpha=0.92,
        )


def _curve_color(curve_index: int) -> tuple[float, float, float]:
    """Keep one stable color per device condition across every subplot."""
    hue = (0.58 + curve_index * 0.61803398875) % 1.0
    base = np.asarray(hsv_to_rgb((hue, 0.78, 0.78)), dtype=float)
    return tuple(float(value) for value in base)


def _condition_legend_handles(
    prediction_sets: list[tuple[str, CurvePrediction, CurvePrediction]],
) -> list[Line2D]:
    return [
        Line2D(
            [0],
            [0],
            color=_curve_color(curve_index),
            lw=2.6,
            label=f"Condition: {curve_label}",
        )
        for curve_index, (curve_label, _idvd, _idvg) in enumerate(
            prediction_sets
        )
    ]


def _bias_legend_handles(
    fixed_name: str,
    fixed_biases: np.ndarray,
) -> list[Line2D]:
    return [
        Line2D(
            [0],
            [0],
            color="#374151",
            lw=2.2,
            ls="--" if bias_index == 0 else "-",
            label=f"Bias: {fixed_name}={bias:g} V",
        )
        for bias_index, bias in enumerate(fixed_biases)
    ]


def render_curve_figure(figure: Figure, prediction_sets: list[tuple[str, CurvePrediction, CurvePrediction]], combined: bool = True) -> None:
    figure.clear(); figure.set_facecolor("white")
    axes = figure.subplots(2, 2 if combined else 4, squeeze=False)
    floor = min(EVALUATION_LOG_FLOOR_MA_PER_UM, 1e-15)
    condition_handles = _condition_legend_handles(prediction_sets)
    if combined:
        for column, kind in enumerate(("idvd", "idvg")):
            sample = prediction_sets[0][1 if kind == "idvd" else 2]
            fixed_name = "Vg" if kind == "idvd" else "Vd"; sweep_name = "Vd" if kind == "idvd" else "Vg"
            for curve_index, (curve_label, idvd, idvg) in enumerate(prediction_sets):
                prediction = idvd if kind == "idvd" else idvg
                for bias_index, (bias, current) in enumerate(zip(prediction.fixed_biases, prediction.currents, strict=True)):
                    color = _curve_color(curve_index); linestyle = "--" if bias_index == 0 else "-"
                    axes[0, column].plot(prediction.grid, current, color=color, ls=linestyle, lw=2.2)
                    axes[1, column].plot(prediction.grid, np.maximum(np.abs(current), floor), color=color, ls=linestyle, lw=2.2)
            _format_axes(
                axes,
                column,
                sample.kind,
                sweep_name,
                None,
                [
                    *condition_handles,
                    *_bias_legend_handles(fixed_name, sample.fixed_biases),
                ],
            )
    else:
        column = 0
        for kind in ("idvd", "idvg"):
            sample = prediction_sets[0][1 if kind == "idvd" else 2]
            sweep_name = "Vd" if sample.kind == "idvd" else "Vg"; fixed_name = "Vg" if sample.kind == "idvd" else "Vd"
            for bias_index, bias in enumerate(sample.fixed_biases):
                for curve_index, (curve_label, idvd, idvg) in enumerate(prediction_sets):
                    prediction = idvd if kind == "idvd" else idvg; current = prediction.currents[bias_index]
                    color = _curve_color(curve_index)
                    axes[0, column].plot(prediction.grid, current, color=color, lw=2.2)
                    axes[1, column].plot(prediction.grid, np.maximum(np.abs(current), floor), color=color, lw=2.2)
                _format_axes(
                    axes,
                    column,
                    sample.kind,
                    sweep_name,
                    f"{fixed_name}={bias:g} V",
                    condition_handles,
                ); column += 1
    figure.suptitle("PCA + XGBoost model-generated I–V curves", fontsize=13)
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.96))
