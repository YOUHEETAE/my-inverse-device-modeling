from __future__ import annotations

import argparse
import json
import math
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk

import matplotlib
import numpy as np

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from ai.curve_model.data.current_preprocessing import (
    EVALUATION_LOG_FLOOR_MA_PER_UM,
    constrain_current_predictions,
)
from ai.curve_model.models.pca_xgboost import (
    BiasSeparatedPCAXGBoostRegressor,
    load_curve_regressor,
)
from ai.curve_model.training.target_transforms import TargetTransformer
from tcad.data_extraction.parameter_extraction_core import extract_parameters
from tcad.data_extraction.visualization.common import configure_window


PARAMETER_OPTIONS = {
    "L": ("100", "120", "150", "170", "200", "250", "300", "400", "500", "700", "1000", "1300", "1600"),
    "T": ("5", "7", "10", "12", "15", "20", "27", "35", "50"),
    "B": ("5e15", "1e16", "5e16"),
    "SD": ("1e19", "5e19", "1e20", "5e20"),
    "LDD": ("1e17", "5e17", "1e18", "5e18"),
}
DEFAULT_PARAMETERS = {"L": "200", "T": "20", "B": "1e16", "SD": "1e20", "LDD": "1e18"}
SECOND_DEFAULT_PARAMETERS = {"L": "400", "T": "20", "B": "1e16", "SD": "1e20", "LDD": "1e18"}
PARAMETER_LABELS = {
    "L": "Gate length L (nm)",
    "T": "Oxide thickness T (nm)",
    "B": "Bulk doping B (cm⁻³)",
    "SD": "Source/Drain doping SD (cm⁻³)",
    "LDD": "LDD doping (cm⁻³)",
}
IDVG_FIXED_BIASES = (0.05, 1.5)
ELECTRICAL_PARAMETER_DISPLAYS = (
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


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class CurvePrediction:
    kind: str
    grid: np.ndarray
    fixed_biases: np.ndarray
    currents: np.ndarray


class FinalCurvePredictor:
    def __init__(self, model_dir: Path) -> None:
        self.model_dir = model_dir
        self.models = {}
        self.transforms: dict[str, TargetTransformer | None] = {}
        self.metadata: dict[str, dict[str, object]] = {}

        for kind in ("idvd", "idvg"):
            kind_dir = model_dir / kind
            model_path = kind_dir / "model.pkl"
            transform_path = kind_dir / "target_transform.json"
            metadata_path = kind_dir / "inference_metadata.json"
            for required in (model_path, transform_path, metadata_path):
                if not required.exists():
                    raise FileNotFoundError(f"Final inference file not found: {required}")

            self.models[kind] = load_curve_regressor(model_path)
            transform_state = json.loads(transform_path.read_text(encoding="utf-8"))
            self.transforms[kind] = (
                None
                if transform_state.get("mode") == "bias_separated"
                else TargetTransformer.from_state_dict(transform_state)
            )
            self.metadata[kind] = json.loads(metadata_path.read_text(encoding="utf-8"))

    def fixed_biases(self, kind: str) -> np.ndarray:
        model = self.models[kind]
        if isinstance(model, BiasSeparatedPCAXGBoostRegressor):
            return np.asarray(sorted(model.models_), dtype=np.float32)
        if kind == "idvg":
            return np.asarray(IDVG_FIXED_BIASES, dtype=np.float32)
        raise RuntimeError(f"Cannot determine fixed biases for {kind}")

    def predict(self, kind: str, device_features: np.ndarray) -> CurvePrediction:
        fixed_biases = self.fixed_biases(kind)
        base = np.asarray(device_features, dtype=np.float32).reshape(1, 5)
        features = np.repeat(base, len(fixed_biases), axis=0)
        features = np.column_stack((features, fixed_biases)).astype(np.float32)
        model = self.models[kind]

        if isinstance(model, BiasSeparatedPCAXGBoostRegressor):
            currents = model.predict_current(features)
        else:
            transformer = self.transforms[kind]
            if transformer is None:
                raise RuntimeError(f"Missing target transformer for {kind}")
            currents = transformer.inverse_transform(model.predict(features))

        grid = np.asarray(self.metadata[kind]["sweep_grid"], dtype=np.float32)
        currents = constrain_current_predictions(kind, currents, grid)
        return CurvePrediction(kind, grid, fixed_biases, currents)


def _device_features(values: dict[str, str]) -> np.ndarray:
    parsed = {name: float(text) for name, text in values.items()}
    if any(not math.isfinite(value) or value <= 0.0 for value in parsed.values()):
        raise ValueError("All structure and doping parameters must be positive finite numbers.")
    return np.asarray(
        [
            parsed["L"],
            parsed["T"],
            math.log10(parsed["B"]),
            math.log10(parsed["SD"]),
            math.log10(parsed["LDD"]),
        ],
        dtype=np.float32,
    )


def _range_warning(values: dict[str, str]) -> str:
    warnings = []
    for name, options in PARAMETER_OPTIONS.items():
        value = float(values[name])
        supported = np.asarray([float(option) for option in options])
        if value < float(supported.min()) or value > float(supported.max()):
            warnings.append(name)
    if not warnings:
        return ""
    return "Extrapolation warning: " + ", ".join(warnings) + " is outside the training range."


def _curve_at_bias(
    prediction: CurvePrediction, target_bias: float
) -> tuple[np.ndarray, np.ndarray]:
    matches = np.flatnonzero(
        np.isclose(prediction.fixed_biases, target_bias, rtol=0.0, atol=1e-6)
    )
    if not len(matches):
        raise ValueError(f"Missing {prediction.kind} curve at fixed bias {target_bias:g} V")
    return prediction.grid, prediction.currents[int(matches[0])]


def _extract_electrical_parameters(
    idvd: CurvePrediction, idvg: CurvePrediction
) -> dict[str, float]:
    return extract_parameters(
        {
            "IDVD_VG1P5": _curve_at_bias(idvd, 1.5),
            "IDVD_VG3P0": _curve_at_bias(idvd, 3.0),
        },
        {
            "IDVG_VD0P05": _curve_at_bias(idvg, 0.05),
            "IDVG_VD1P5": _curve_at_bias(idvg, 1.5),
        },
    )


class CurveModelVisualizationApp:
    def __init__(self, root: tk.Tk, predictor: FinalCurvePredictor) -> None:
        self.root = root
        self.predictor = predictor
        self.curve1_vars = {
            name: tk.StringVar(value=DEFAULT_PARAMETERS[name]) for name in PARAMETER_OPTIONS
        }
        self.curve2_vars = {
            name: tk.StringVar(value=SECOND_DEFAULT_PARAMETERS[name]) for name in PARAMETER_OPTIONS
        }
        self.show_curve2 = False
        self.combined_view = True
        self.status_var = tk.StringVar()
        self.parameter_value_vars: dict[str, dict[str, tk.StringVar]] = {}

        configure_window(root, "Final Curve Model Visualization", "1900x900")
        controls = ttk.Frame(root, padding=(10, 8))
        controls.pack(side=tk.TOP, fill=tk.X)
        curve1_row = ttk.Frame(controls)
        curve1_row.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))
        curve2_row = ttk.Frame(controls)
        curve2_row.pack(side=tk.TOP, fill=tk.X)

        self._build_curve_controls(curve1_row, "Curve 1", self.curve1_vars)
        self.view_button = ttk.Button(
            curve1_row, text="Separate Biases (8 plots)", command=self.toggle_view
        )
        self.view_button.pack(side=tk.LEFT, padx=(8, 8))
        ttk.Button(curve1_row, text="Generate curves", command=self.generate).pack(
            side=tk.LEFT, padx=(0, 8)
        )

        self._build_curve_controls(curve2_row, "Curve 2", self.curve2_vars)
        self.curve2_button = ttk.Button(
            curve2_row, text="Show Curve 2", command=self.toggle_curve2
        )
        self.curve2_button.pack(side=tk.LEFT, padx=(8, 8))
        ttk.Label(curve2_row, textvariable=self.status_var).pack(side=tk.LEFT, padx=(4, 0))

        content = ttk.Frame(root)
        content.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        plot_frame = ttk.Frame(content)
        plot_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        parameter_frame = ttk.LabelFrame(
            content, text="Extracted electrical parameters", padding=(8, 8)
        )
        parameter_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 10), pady=(4, 8))
        self._build_parameter_panel(parameter_frame)
        self.parameter_note_var = tk.StringVar()
        ttk.Label(
            parameter_frame,
            textvariable=self.parameter_note_var,
            justify=tk.LEFT,
            wraplength=560,
        ).grid(
            row=len(ELECTRICAL_PARAMETER_DISPLAYS) + 1,
            column=0,
            columnspan=5,
            padx=4,
            pady=(12, 0),
            sticky="w",
        )

        self.figure = Figure(figsize=(14, 8), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        toolbar_frame = ttk.Frame(root)
        toolbar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        NavigationToolbar2Tk(self.canvas, toolbar_frame)

        self.generate()

    def _build_curve_controls(
        self,
        parent,
        label: str,
        variables: dict[str, tk.StringVar],
    ) -> None:
        ttk.Label(parent, text=label, width=8).pack(side=tk.LEFT, padx=(0, 4))
        for name in PARAMETER_OPTIONS:
            ttk.Label(parent, text=name).pack(side=tk.LEFT)
            combo = ttk.Combobox(
                parent,
                textvariable=variables[name],
                values=PARAMETER_OPTIONS[name],
                state="normal",
                width=10,
            )
            combo.pack(side=tk.LEFT, padx=(3, 6))
            combo.bind("<<ComboboxSelected>>", self.generate)
            combo.bind("<Return>", self.generate)

    def _build_parameter_panel(self, parent) -> None:
        headers = ("Parameter", "Curve 1", "Curve 2", "C2 - C1", "C2 / C1")
        for column, header in enumerate(headers):
            ttk.Label(parent, text=header, anchor=tk.CENTER).grid(
                row=0, column=column, padx=5, pady=(0, 7), sticky="ew"
            )
        for row, (name, label, unit, _factor, _number_format) in enumerate(
            ELECTRICAL_PARAMETER_DISPLAYS, start=1
        ):
            ttk.Label(parent, text=f"{label}\n({unit})", anchor=tk.W).grid(
                row=row, column=0, padx=(2, 7), pady=5, sticky="w"
            )
            values = {
                key: tk.StringVar() for key in ("curve1", "curve2", "difference", "ratio")
            }
            self.parameter_value_vars[name] = values
            for column, key in enumerate(
                ("curve1", "curve2", "difference", "ratio"), start=1
            ):
                ttk.Label(
                    parent, textvariable=values[key], anchor=tk.E, width=12
                ).grid(row=row, column=column, padx=4, pady=5, sticky="e")
        for column in range(len(headers)):
            parent.columnconfigure(column, weight=1)

    @staticmethod
    def _input_values(variables: dict[str, tk.StringVar]) -> dict[str, str]:
        return {name: variable.get().strip() for name, variable in variables.items()}

    def toggle_curve2(self) -> None:
        self.show_curve2 = not self.show_curve2
        self.curve2_button.configure(
            text="Hide Curve 2" if self.show_curve2 else "Show Curve 2"
        )
        self.generate()

    def toggle_view(self) -> None:
        self.combined_view = not self.combined_view
        self.view_button.configure(
            text=(
                "Separate Biases (8 plots)"
                if self.combined_view
                else "Combine Biases (4 plots)"
            )
        )
        self.generate()

    def generate(self, _event=None) -> None:
        curve1_values = self._input_values(self.curve1_vars)
        curve2_values = self._input_values(self.curve2_vars)
        try:
            curve1_features = _device_features(curve1_values)
            predictions = [
                (
                    "Curve 1",
                    curve1_values,
                    self.predictor.predict("idvd", curve1_features),
                    self.predictor.predict("idvg", curve1_features),
                )
            ]
            if self.show_curve2:
                curve2_features = _device_features(curve2_values)
                predictions.append(
                    (
                        "Curve 2",
                        curve2_values,
                        self.predictor.predict("idvd", curve2_features),
                        self.predictor.predict("idvg", curve2_features),
                    )
                )
        except Exception as exc:
            messagebox.showerror("Curve prediction failed", str(exc), parent=self.root)
            self.status_var.set("Prediction failed")
            return

        self._update_parameter_panel(predictions)

        self.figure.clear()
        axes = self.figure.subplots(2, 2 if self.combined_view else 4, squeeze=False)
        for curve_index, (label, _values, idvd, idvg) in enumerate(predictions):
            self._plot_prediction_set(axes, idvd, idvg, label, curve_index)

        title = "Final PCA+XGBoost model-generated curves"
        if self.show_curve2:
            title += " | Curve 1 vs Curve 2"
        self.figure.suptitle(title, fontsize=13)
        self.figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.96))
        warnings = [
            f"{label}: {warning}"
            for label, values, _idvd, _idvg in predictions
            for warning in [_range_warning(values)]
            if warning
        ]
        self.status_var.set(" | ".join(warnings) or "Curves generated from the final model")
        self.canvas.draw()

    def _plot_prediction_set(
        self,
        axes,
        idvd: CurvePrediction,
        idvg: CurvePrediction,
        curve_label: str,
        curve_index: int,
    ) -> None:
        palettes = (
            ("#2196F3", "#0D47A1", "#03A9F4", "#1565C0"),
            ("#EF5350", "#B71C1C", "#FF7043", "#C62828"),
        )
        palette = palettes[curve_index % len(palettes)]
        floor = min(EVALUATION_LOG_FLOOR_MA_PER_UM, 1e-15)
        predictions = (idvd, idvg)

        if self.combined_view:
            for column, prediction in enumerate(predictions):
                fixed_name = "Vg" if prediction.kind == "idvd" else "Vd"
                sweep_name = "Vd" if prediction.kind == "idvd" else "Vg"
                for bias_index, (bias, current) in enumerate(
                    zip(prediction.fixed_biases, prediction.currents, strict=True)
                ):
                    label = f"{curve_label} {fixed_name}={bias:g} V"
                    color = palette[bias_index]
                    axes[0, column].plot(
                        prediction.grid, current, color=color, linewidth=2.0, label=label
                    )
                    axes[1, column].plot(
                        prediction.grid,
                        np.maximum(np.abs(current), floor),
                        color=color,
                        linewidth=2.0,
                        label=label,
                    )
                self._format_axes(axes, column, prediction.kind, sweep_name, fixed_name=None)
            return

        column = 0
        for prediction in predictions:
            fixed_name = "Vg" if prediction.kind == "idvd" else "Vd"
            sweep_name = "Vd" if prediction.kind == "idvd" else "Vg"
            for bias_index, (bias, current) in enumerate(
                zip(prediction.fixed_biases, prediction.currents, strict=True)
            ):
                color = palette[bias_index]
                axes[0, column].plot(
                    prediction.grid, current, color=color, linewidth=2.0, label=curve_label
                )
                axes[1, column].plot(
                    prediction.grid,
                    np.maximum(np.abs(current), floor),
                    color=color,
                    linewidth=2.0,
                    label=curve_label,
                )
                self._format_axes(
                    axes, column, prediction.kind, sweep_name, fixed_name=f"{fixed_name}={bias:g} V"
                )
                column += 1

    @staticmethod
    def _format_axes(axes, column: int, kind: str, sweep_name: str, fixed_name: str | None) -> None:
        title = kind.upper() + (f" ({fixed_name})" if fixed_name else "")
        axes[0, column].set_title(f"{title} — linear")
        axes[1, column].set_title(f"{title} — log |Id|")
        axes[1, column].set_yscale("log")
        for row in range(2):
            axes[row, column].set_xlabel(f"{sweep_name} (V)")
            axes[row, column].set_ylabel("Id (mA/µm)")
            axes[row, column].grid(True, alpha=0.3, which="both")
            axes[row, column].legend(fontsize=8)

    def _update_parameter_panel(
        self,
        predictions: list[tuple[str, dict[str, str], CurvePrediction, CurvePrediction]],
    ) -> None:
        extracted: list[dict[str, float] | None] = []
        failures: list[str] = []
        for label, _values, idvd, idvg in predictions:
            try:
                extracted.append(_extract_electrical_parameters(idvd, idvg))
            except (ValueError, FloatingPointError) as exc:
                extracted.append(None)
                failures.append(f"{label}: {exc}")
        for name, label, unit, factor, number_format in ELECTRICAL_PARAMETER_DISPLAYS:
            variables = self.parameter_value_vars[name]
            value1 = extracted[0][name] * factor if extracted[0] is not None else None
            value2 = (
                extracted[1][name] * factor
                if len(extracted) > 1 and extracted[1] is not None
                else None
            )
            variables["curve1"].set(format(value1, number_format) if value1 is not None else "-")
            variables["curve2"].set(format(value2, number_format) if value2 is not None else "-")
            variables["difference"].set(
                format(value2 - value1, number_format)
                if value1 is not None and value2 is not None
                else "-"
            )
            variables["ratio"].set(
                format(value2 / value1, ".5g")
                if value1 is not None and value2 is not None and not math.isclose(value1, 0.0)
                else "-"
            )
        self.parameter_note_var.set(
            "Parameter extraction failed:\n" + "\n".join(failures)
            if failures
            else "Extracted from model-generated curves with the final report definitions."
        )


def _parse_args() -> argparse.Namespace:
    root = _repo_root()
    parser = argparse.ArgumentParser(description="Visualize curves generated by the final model")
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=root / "ai/model_artifacts/curve_model/final/pca_xgboost",
    )
    parser.add_argument("--smoke-test", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    predictor = FinalCurvePredictor(args.model_dir.resolve())
    if args.smoke_test:
        features = _device_features(DEFAULT_PARAMETERS)
        for kind in ("idvd", "idvg"):
            prediction = predictor.predict(kind, features)
            print(
                f"{kind}: biases={prediction.fixed_biases.tolist()}, "
                f"shape={prediction.currents.shape}, finite={bool(np.all(np.isfinite(prediction.currents)))}"
            )
        parameters = _extract_electrical_parameters(
            predictor.predict("idvd", features), predictor.predict("idvg", features)
        )
        print(f"electrical_parameters: count={len(parameters)}, finite={all(np.isfinite(list(parameters.values())))}")
        return

    window = tk.Tk()
    CurveModelVisualizationApp(window, predictor)
    window.mainloop()


if __name__ == "__main__":
    main()
