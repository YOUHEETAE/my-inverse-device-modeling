from __future__ import annotations

import argparse
import json
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk

import matplotlib
import numpy as np

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from ai.curve_model.data.current_preprocessing import (
    EVALUATION_LOG_FLOOR_MA_PER_UM,
    constrain_current_predictions,
)
from ai.curve_model.data.domain_policy import DomainPolicy, make_domain_policy
from ai.curve_model.evaluation.electrical_parameters import (
    PARAMETER_SPECS,
    ParameterEvaluation,
    evaluate_parameters,
)
from ai.curve_model.evaluation.metrics import curve_metric_arrays
from ai.curve_model.evaluation.report import build_evaluation_report
from ai.curve_model.models.pca_xgboost import (
    BiasSeparatedPCAXGBoostRegressor,
    PCAXGBoostRegressor,
    load_curve_regressor,
)
from ai.curve_model.models.residual_mlp import ResidualCurvePredictor
from ai.curve_model.models.shared_encoder import SharedCurvePredictor
from ai.curve_model.training.target_transforms import TargetTransformer
from tcad.data_extraction.visualization.common import configure_window


SPLIT_INDEX = {"train": 0, "validation": 1, "test": 2}
VIEW_MODES = (
    "Selected device",
    "Best IdVd linear",
    "Worst IdVd linear",
    "Best IdVd log",
    "Worst IdVd log",
    "Best IdVg linear",
    "Worst IdVg linear",
    "Best IdVg log",
    "Worst IdVg log",
    "Best Electrical overall",
    "Worst Electrical overall",
    *(
        f"{order} Parameter {spec.label}"
        for order in ("Best", "Worst")
        for spec in PARAMETER_SPECS.values()
    ),
)


@dataclass(frozen=True)
class PredictionBundle:
    kind: str
    split: str
    device_indices: np.ndarray
    features: np.ndarray
    targets: np.ndarray
    predictions: np.ndarray
    linear_mae: np.ndarray
    linear_rmse: np.ndarray
    nrmse: np.ndarray
    r_squared: np.ndarray
    log_mae: np.ndarray
    signed_log_rmse: np.ndarray
    decade_mae: np.ndarray
    decade_rmse: np.ndarray
    grid: np.ndarray


class EvaluationRepository:
    def __init__(self, dataset_path: Path, model_dir: Path, target_mode: str = "clean") -> None:
        if not dataset_path.exists():
            raise FileNotFoundError(f"Prepared dataset not found: {dataset_path}")
        with np.load(dataset_path, allow_pickle=False) as archive:
            self.arrays = {name: archive[name] for name in archive.files}
        self.device_ids = [str(value) for value in self.arrays["device_ids"]]
        self.target_mode = target_mode
        self.domain_policy = DomainPolicy(name="full")
        shared_model = model_dir / "model.pt"
        if shared_model.exists():
            self.model_family = "shared_encoder"
        elif (model_dir / "idvd" / "model.pt").exists():
            self.model_family = "residual_mlp"
        else:
            self.model_family = "pca_xgboost"
        self.models: dict[
            str,
            PCAXGBoostRegressor
            | BiasSeparatedPCAXGBoostRegressor
            | ResidualCurvePredictor
            | SharedCurvePredictor,
        ] = {}
        self.transforms: dict[str, TargetTransformer | None] = {}
        shared_predictor = (
            SharedCurvePredictor.load(shared_model) if shared_model.exists() else None
        )
        for kind in ("idvd", "idvg"):
            kind_dir = model_dir / kind
            if shared_predictor is not None:
                self.models[kind] = shared_predictor
                self.transforms[kind] = None
            elif (kind_dir / "model.pt").exists():
                self.models[kind] = ResidualCurvePredictor.load(
                    kind_dir / "model.pt"
                )
                self.transforms[kind] = None
            else:
                self.models[kind] = load_curve_regressor(kind_dir / "model.pkl")
                transform_state = json.loads(
                    (kind_dir / "target_transform.json").read_text(encoding="utf-8")
                )
                self.transforms[kind] = (
                    None
                    if transform_state.get("mode") == "bias_separated"
                    else TargetTransformer.from_state_dict(transform_state)
                )
        self._cache: dict[tuple[str, str], PredictionBundle] = {}
        self._parameter_cache: dict[str, list[ParameterEvaluation]] = {}

    def bundle(self, kind: str, split: str) -> PredictionBundle:
        key = (kind, split)
        if key in self._cache:
            return self._cache[key]
        split_index = SPLIT_INDEX[split]
        all_device_indices = self.arrays[f"{kind}_device_index"]
        mask = (
            (self.arrays["device_split"][all_device_indices] == split_index)
            & self.domain_policy.supported(self.arrays[f"{kind}_x"])
        )
        device_indices = all_device_indices[mask]
        features = self.arrays[f"{kind}_x"][mask]
        target_key = f"{kind}_y_{self.target_mode}"
        if target_key not in self.arrays:
            target_key = f"{kind}_y_raw"
        targets = self.arrays[target_key][mask]
        model = self.models[kind]
        if isinstance(model, SharedCurvePredictor):
            predictions = model.predict_current(kind, features)
        elif isinstance(
            model, (BiasSeparatedPCAXGBoostRegressor, ResidualCurvePredictor)
        ):
            predictions = model.predict_current(features)
        else:
            transformed_prediction = model.predict(features)
            transformer = self.transforms[kind]
            if transformer is None:
                raise RuntimeError(f"Missing target transformer for {kind}")
            predictions = transformer.inverse_transform(transformed_prediction)
        predictions = constrain_current_predictions(kind, predictions, self.arrays[f"{kind}_grid"])
        scale = EVALUATION_LOG_FLOOR_MA_PER_UM
        metrics = curve_metric_arrays(targets, predictions, scale)
        bundle = PredictionBundle(
            kind=kind,
            split=split,
            device_indices=device_indices,
            features=features,
            targets=targets,
            predictions=predictions,
            linear_mae=metrics["linear_mae"],
            linear_rmse=metrics["linear_rmse"],
            nrmse=metrics["nrmse"],
            r_squared=metrics["r_squared"],
            log_mae=metrics["signed_log_mae"],
            signed_log_rmse=metrics["signed_log_rmse"],
            decade_mae=metrics["decade_mae"],
            decade_rmse=metrics["decade_rmse"],
            grid=self.arrays[f"{kind}_grid"],
        )
        self._cache[key] = bundle
        return bundle

    def devices(self, split: str) -> list[int]:
        indices = np.flatnonzero(
            (self.arrays["device_split"] == SPLIT_INDEX[split])
            & self.domain_policy.supported(self.arrays["device_features"])
        )
        # Dataset IDs are strings, so lexical order places values such as L1000
        # before L120. Sort on the actual numeric device parameters instead.
        return sorted(
            (int(index) for index in indices),
            key=lambda index: tuple(
                float(value) for value in self.arrays["device_features"][index]
            ),
        )

    def parameter_evaluations(self, split: str) -> list[ParameterEvaluation]:
        if split not in self._parameter_cache:
            self._parameter_cache[split] = evaluate_parameters(
                self.devices(split), self.bundle("idvd", split), self.bundle("idvg", split)
            )
        return self._parameter_cache[split]

    def device_parameter_evaluation(
        self, device_index: int, split: str
    ) -> ParameterEvaluation | None:
        return next(
            (
                item
                for item in self.parameter_evaluations(split)
                if item.device_index == device_index
            ),
            None,
        )

    def ranked_sample(self, view_mode: str, split: str) -> tuple[int, str]:
        if "Electrical overall" in view_mode or " Parameter " in view_mode:
            return self._ranked_parameter(view_mode, split)
        words = view_mode.split()
        if len(words) != 3 or words[0] not in {"Best", "Worst"}:
            raise ValueError(f"Not a ranking view: {view_mode}")
        kind = words[1].lower()
        bundle = self.bundle(kind, split)
        values = bundle.linear_mae if words[2] == "linear" else bundle.log_mae
        position = int(np.argmin(values) if words[0] == "Best" else np.argmax(values))
        bias_name = "Vg" if kind == "idvd" else "Vd"
        detail = (
            f"{view_mode}: {bias_name}={bundle.features[position, -1]:g} V, "
            f"linear MAE={bundle.linear_mae[position]:.4g}, "
            f"log MAE={bundle.log_mae[position]:.4g}"
        )
        return int(bundle.device_indices[position]), detail

    def _ranked_parameter(self, view_mode: str, split: str) -> tuple[int, str]:
        successful = [
            item
            for item in self.parameter_evaluations(split)
            if item.overall_score is not None
        ]
        if not successful:
            raise ValueError("No successful electrical-parameter extractions")
        order = view_mode.split()[0]
        parameter_name: str | None = None
        if " Parameter " in view_mode:
            label = view_mode.split(" Parameter ", 1)[1]
            parameter_name = next(
                name for name, spec in PARAMETER_SPECS.items() if spec.label == label
            )
            values = np.asarray(
                [item.normalized_errors[parameter_name] for item in successful]
            )
        else:
            values = np.asarray([item.overall_score for item in successful])
        position = int(np.argmin(values) if order == "Best" else np.argmax(values))
        selected = successful[position]
        metric = (
            f"{PARAMETER_SPECS[parameter_name].label} score"
            if parameter_name is not None
            else "overall score"
        )
        return selected.device_index, f"{view_mode}: {metric}={values[position]:.4g}"


class CurveModelEvaluationApp:
    def __init__(self, root: tk.Tk, repository: EvaluationRepository) -> None:
        self.root = root
        self.repository = repository
        self.split_var = tk.StringVar(value="validation")
        self.device_var = tk.StringVar()
        self.view_var = tk.StringVar(value=VIEW_MODES[0])
        self.status_var = tk.StringVar()
        self._device_lookup: dict[str, int] = {}

        configure_window(root, "Curve Model Evaluation", "1900x900")
        controls = ttk.Frame(root, padding=(10, 8))
        controls.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(controls, text="Split").pack(side=tk.LEFT)
        split_combo = ttk.Combobox(
            controls,
            textvariable=self.split_var,
            values=("validation", "test"),
            state="readonly",
            width=11,
        )
        split_combo.pack(side=tk.LEFT, padx=(4, 12))
        split_combo.bind("<<ComboboxSelected>>", self._split_changed)

        ttk.Label(controls, text="Device").pack(side=tk.LEFT)
        self.device_combo = ttk.Combobox(
            controls, textvariable=self.device_var, state="readonly", width=47
        )
        self.device_combo.pack(side=tk.LEFT, padx=(4, 12))
        self.device_combo.bind("<<ComboboxSelected>>", self._device_changed)

        ttk.Label(controls, text="Case").pack(side=tk.LEFT)
        view_combo = ttk.Combobox(
            controls,
            textvariable=self.view_var,
            values=VIEW_MODES,
            state="readonly",
            width=27,
        )
        view_combo.pack(side=tk.LEFT, padx=(4, 12))
        view_combo.bind("<<ComboboxSelected>>", self._view_changed)
        ttk.Label(controls, textvariable=self.status_var).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(
            controls,
            text="Domain: full",
            foreground="#2E7D32",
        ).pack(side=tk.RIGHT, padx=(12, 0))

        content = ttk.Frame(root)
        content.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        plot_frame = ttk.Frame(content)
        plot_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        metrics_frame = ttk.LabelFrame(content, text="Per-curve errors", padding=(8, 8))
        metrics_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 10), pady=(4, 8))

        notebook = ttk.Notebook(metrics_frame)
        notebook.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        curve_tab = ttk.Frame(notebook, padding=(4, 4))
        parameter_tab = ttk.Frame(notebook, padding=(4, 4))
        notebook.add(curve_tab, text="Curve metrics")
        notebook.add(parameter_tab, text="Electrical parameters")

        columns = ("kind", "bias", "mae", "rmse", "nrmse", "r2", "log", "decade")
        self.metrics_tree = ttk.Treeview(
            curve_tab, columns=columns, show="headings", height=12
        )
        headings = {
            "kind": "Curve",
            "bias": "Fixed bias",
            "mae": "Linear MAE",
            "rmse": "Linear RMSE",
            "nrmse": "NRMSE",
            "r2": "R²",
            "log": "Log MAE",
            "decade": "Decade MAE",
        }
        widths = {
            "kind": 55,
            "bias": 78,
            "mae": 85,
            "rmse": 85,
            "nrmse": 72,
            "r2": 65,
            "log": 75,
            "decade": 85,
        }
        for column in columns:
            self.metrics_tree.heading(column, text=headings[column])
            self.metrics_tree.column(column, width=widths[column], anchor=tk.E)
        self.metrics_tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        parameter_columns = ("parameter", "actual", "predicted", "error", "score")
        self.parameter_tree = ttk.Treeview(
            parameter_tab, columns=parameter_columns, show="headings", height=12
        )
        parameter_headings = {
            "parameter": "Parameter",
            "actual": "Actual",
            "predicted": "Predicted",
            "error": "Natural error",
            "score": "Normalized score",
        }
        parameter_widths = {
            "parameter": 90,
            "actual": 90,
            "predicted": 90,
            "error": 120,
            "score": 105,
        }
        for column in parameter_columns:
            self.parameter_tree.heading(column, text=parameter_headings[column])
            self.parameter_tree.column(
                column, width=parameter_widths[column], anchor=tk.E
            )
        self.parameter_tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.parameter_summary_var = tk.StringVar()
        ttk.Label(
            parameter_tab,
            textvariable=self.parameter_summary_var,
            justify=tk.LEFT,
        ).pack(side=tk.BOTTOM, anchor=tk.W, pady=(10, 0))
        ttk.Label(
            metrics_frame,
            text=(
                "Solid: raw TCAD target\nDashed: model prediction\n"
                "Log plots show |Id|.\nCurve ranking is per bias.\n"
                "Parameter ranking is per device."
            ),
            justify=tk.LEFT,
        ).pack(side=tk.BOTTOM, anchor=tk.W, pady=(12, 0))

        self.figure = Figure(figsize=(13, 8), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        toolbar_frame = ttk.Frame(root)
        toolbar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        NavigationToolbar2Tk(self.canvas, toolbar_frame)

        self._refresh_devices()
        self.plot_selected()

    def _refresh_devices(self, preferred: int | None = None) -> None:
        indices = self.repository.devices(self.split_var.get())
        self._device_lookup = {
            self.repository.device_ids[index]: index for index in indices
        }
        values = list(self._device_lookup)
        self.device_combo["values"] = values
        if preferred is not None and self.repository.device_ids[preferred] in self._device_lookup:
            self.device_var.set(self.repository.device_ids[preferred])
        elif self.device_var.get() not in self._device_lookup:
            self.device_var.set(values[0] if values else "")

    def _split_changed(self, _event=None) -> None:
        self.view_var.set(VIEW_MODES[0])
        self._refresh_devices()
        self.plot_selected()

    def _device_changed(self, _event=None) -> None:
        self.view_var.set(VIEW_MODES[0])
        self.plot_selected()

    def _view_changed(self, _event=None) -> None:
        if self.view_var.get() != VIEW_MODES[0]:
            device_index, detail = self.repository.ranked_sample(
                self.view_var.get(), self.split_var.get()
            )
            self._refresh_devices(preferred=device_index)
            self.status_var.set(detail)
        self.plot_selected(keep_status=True)

    def plot_selected(self, *, keep_status: bool = False) -> None:
        device_index = self._device_lookup.get(self.device_var.get())
        self.figure.clear()
        for item in self.metrics_tree.get_children():
            self.metrics_tree.delete(item)
        for item in self.parameter_tree.get_children():
            self.parameter_tree.delete(item)
        if device_index is None:
            axis = self.figure.add_subplot(111)
            axis.text(0.5, 0.5, "No device in this split", ha="center", va="center")
            self.canvas.draw()
            return

        axes = self.figure.subplots(2, 2)
        for column, kind in enumerate(("idvd", "idvg")):
            bundle = self.repository.bundle(kind, self.split_var.get())
            positions = np.flatnonzero(bundle.device_indices == device_index)
            positions = positions[np.argsort(bundle.features[positions, -1])]
            bias_name = "Vg" if kind == "idvd" else "Vd"
            coordinate_name = "Vd" if kind == "idvd" else "Vg"
            scale = EVALUATION_LOG_FLOOR_MA_PER_UM
            colors = ("#2196F3", "#EF5350", "#43A047", "#8E24AA")
            for curve_number, position in enumerate(positions):
                color = colors[curve_number % len(colors)]
                bias = bundle.features[position, -1]
                label = f"{bias_name}={bias:g} V"
                axes[0, column].plot(
                    bundle.grid,
                    bundle.targets[position],
                    color=color,
                    linewidth=2.0,
                    label=f"Actual {label}",
                )
                axes[0, column].plot(
                    bundle.grid,
                    bundle.predictions[position],
                    color=color,
                    linewidth=1.8,
                    linestyle="--",
                    label=f"Predicted {label}",
                )
                floor = min(scale, 1e-15)
                axes[1, column].plot(
                    bundle.grid,
                    np.maximum(np.abs(bundle.targets[position]), floor),
                    color=color,
                    linewidth=2.0,
                )
                axes[1, column].plot(
                    bundle.grid,
                    np.maximum(np.abs(bundle.predictions[position]), floor),
                    color=color,
                    linewidth=1.8,
                    linestyle="--",
                )
                self.metrics_tree.insert(
                    "",
                    tk.END,
                    values=(
                        kind.upper(),
                        f"{bias_name}={bias:g}",
                        f"{bundle.linear_mae[position]:.4g}",
                        f"{bundle.linear_rmse[position]:.4g}",
                        f"{bundle.nrmse[position]:.4g}",
                        f"{bundle.r_squared[position]:.4g}",
                        f"{bundle.log_mae[position]:.4g}",
                        f"{bundle.decade_mae[position]:.4g}",
                    ),
                )
            axes[0, column].set_title(f"{kind.upper()} linear")
            axes[1, column].set_title(f"{kind.upper()} log |Id|")
            axes[1, column].set_yscale("log")
            for row in range(2):
                axes[row, column].set_xlabel(f"{coordinate_name} (V)")
                axes[row, column].set_ylabel("Id (mA/um)")
                axes[row, column].grid(True, alpha=0.3, which="both")
            axes[0, column].legend(fontsize=8)

        self._update_parameter_panel(device_index)

        device_id = self.repository.device_ids[device_index]
        self.figure.suptitle(
            f"{self.repository.model_family.replace('_', ' ').title()} "
            f"{self.split_var.get()} | {self.repository.target_mode} TCAD target | {device_id}",
            fontsize=14,
        )
        self.figure.tight_layout()
        if not keep_status or self.view_var.get() == VIEW_MODES[0]:
            self.status_var.set(f"Device {device_index}: {device_id}")
        self.canvas.draw()

    def _update_parameter_panel(self, device_index: int) -> None:
        evaluation = self.repository.device_parameter_evaluation(
            device_index, self.split_var.get()
        )
        if evaluation is None or evaluation.overall_score is None:
            reason = "parameter evaluation unavailable"
            if evaluation is not None and evaluation.failure:
                reason = evaluation.failure
            self.parameter_summary_var.set(f"Extraction failed: {reason}")
            return
        for name, spec in PARAMETER_SPECS.items():
            self.parameter_tree.insert(
                "",
                tk.END,
                values=(
                    spec.label,
                    f"{evaluation.actual[name]:.5g}",
                    f"{evaluation.predicted[name]:.5g}",
                    f"{evaluation.errors[name]:.4g} {spec.error_unit}",
                    f"{evaluation.normalized_errors[name]:.4g}",
                ),
            )
        self.parameter_summary_var.set(
            "Overall normalized parameter score: "
            f"{evaluation.overall_score:.4g}\n"
            "1.0 means the average configured tolerance."
        )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _parse_args() -> argparse.Namespace:
    root = _repo_root()
    parser = argparse.ArgumentParser(description="Interactive curve-model evaluation")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=root / "ai" / "model_artifacts" / "curve_model" / "dataset" / "curves.npz",
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=root
        / "ai/model_artifacts/curve_model/final/pca_xgboost",
    )
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--target", choices=("raw", "clean"), default="raw")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    repository = EvaluationRepository(
        args.dataset.resolve(), args.model_dir.resolve(), target_mode=args.target
    )
    if args.smoke_test:
        print(json.dumps(build_evaluation_report(repository, "validation"), indent=2))
        return
    root = tk.Tk()
    CurveModelEvaluationApp(root, repository)
    root.mainloop()


if __name__ == "__main__":
    main()
