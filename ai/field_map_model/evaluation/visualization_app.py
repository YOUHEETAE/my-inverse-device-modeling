from __future__ import annotations

import argparse
import json
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk

import h5py
import numpy as np
import torch
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.colors import Normalize, TwoSlopeNorm
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator

from ai.field_map_model.data.tecplot import ELEMENT_FIELD_NAMES
from ai.field_map_model.models.coordinate_mlp import CoordinateFieldMLP
from ai.field_map_model.training.screen_preprocessing import (
    INPUT_NAMES,
    NODE_TARGET_NAMES,
    _coordinate_features,
)
from ai.field_map_model.training.target_transforms import (
    FieldTransformer,
    inverse_transform_matrix,
)


FIELD_NAMES = NODE_TARGET_NAMES + ELEMENT_FIELD_NAMES
SPLIT_INDEX = {"train": 0, "validation": 1}


@dataclass(frozen=True)
class FieldData:
    case_id: str
    domain: str
    field_name: str
    coordinates_nm: np.ndarray
    triangles: np.ndarray
    raw: np.ndarray
    prediction: np.ndarray
    display_raw: np.ndarray
    display_prediction: np.ndarray
    display_label: str
    parameters: np.ndarray


class DomainPredictor:
    def __init__(self, checkpoint_path: Path) -> None:
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        architecture = checkpoint["architecture"]
        self.model = CoordinateFieldMLP(
            input_size=int(architecture["input_size"]),
            output_size=int(architecture["output_size"]),
            hidden_size=int(architecture["hidden_size"]),
            residual_blocks=int(architecture["residual_blocks"]),
            dropout=float(architecture["dropout"]),
        )
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.eval()
        self.field_names = tuple(str(name) for name in checkpoint["field_names"])
        if tuple(checkpoint["input_names"]) != INPUT_NAMES:
            raise ValueError("Checkpoint input feature schema does not match visualization code")
        feature_scaler = checkpoint["feature_scaler"]
        self.feature_mean = np.asarray(feature_scaler["mean"], dtype=np.float64)
        self.feature_scale = np.asarray(feature_scaler["scale"], dtype=np.float64)
        transform_states = checkpoint["target_transformers"]
        self.transformers = [
            FieldTransformer(
                mode=str(transform_states[name]["mode"]),
                nonlinear_scale=float(transform_states[name]["nonlinear_scale"]),
                scaler_mode=str(transform_states[name]["scaler_mode"]),
                center=float(transform_states[name]["center"]),
                spread=float(transform_states[name]["spread"]),
            )
            for name in self.field_names
        ]

    def predict(self, features: np.ndarray, batch_size: int = 8192) -> np.ndarray:
        scaled = ((features - self.feature_mean) / self.feature_scale).astype(np.float32)
        batches: list[np.ndarray] = []
        with torch.no_grad():
            for start in range(0, len(scaled), batch_size):
                batch = torch.from_numpy(scaled[start : start + batch_size])
                batches.append(self.model(batch).numpy())
        transformed = np.concatenate(batches).astype(np.float32)
        prediction = inverse_transform_matrix(transformed, self.transformers)
        for column, name in enumerate(self.field_names):
            if name in {"Electrons", "Holes"}:
                prediction[:, column] = np.maximum(prediction[:, column], 0.0)
        return prediction


class FieldMapComparison:
    def __init__(self, dataset_path: Path, model_dir: Path) -> None:
        self.archive = h5py.File(dataset_path, "r")
        self.predictors = {
            domain: DomainPredictor(model_dir / domain / "model.pt")
            for domain in ("node", "element")
        }
        self.case_keys = self.archive["case_keys"].asstr()[:]
        self.case_ids = self.archive["case_ids"].asstr()[:]
        self.case_splits = self.archive["case_split"][:]
        self._id_to_key = dict(zip(self.case_ids, self.case_keys))

    def close(self) -> None:
        self.archive.close()

    def cases(self, split: str) -> list[str]:
        split_index = SPLIT_INDEX[split]
        return [
            str(case_id)
            for case_id, value in zip(self.case_ids, self.case_splits)
            if int(value) == split_index
        ]

    def field_data(self, case_id: str, field_name: str, scale_mode: str) -> FieldData:
        case_key = self._id_to_key[case_id]
        case = self.archive[f"cases/{case_key}"]
        mesh = self.archive[f"meshes/{case.attrs['structure_id']}"]
        node_xy = mesh["node_xy_nm"][:]
        triangles = mesh["triangles"][:]
        node_fields = case["node_fields"][:]
        if field_name in NODE_TARGET_NAMES:
            domain = "node"
            column = NODE_TARGET_NAMES.index(field_name)
            feature_coordinates = node_xy
            plot_coordinates = node_xy
            regions = mesh["node_region"][:]
            local_doping = node_fields[:, 0]
            raw = node_fields[:, column + 1]
        else:
            domain = "element"
            column = ELEMENT_FIELD_NAMES.index(field_name)
            feature_coordinates = mesh["element_centroid_xy_nm"][:]
            plot_coordinates = node_xy
            regions = mesh["element_region"][:]
            local_doping = node_fields[:, 0][triangles].mean(axis=1)
            raw = case["element_fields"][:, column]
        features = _coordinate_features(
            case["device_features"][:],
            feature_coordinates,
            regions,
            local_doping,
            node_xy,
        )
        prediction = self.predictors[domain].predict(features)[:, column]
        transformer = self.predictors[domain].transformers[column]
        display_raw, display_label = _display_values(
            raw, field_name, transformer.nonlinear_scale, scale_mode
        )
        display_prediction, _ = _display_values(
            prediction, field_name, transformer.nonlinear_scale, scale_mode
        )
        return FieldData(
            case_id=case_id,
            domain=domain,
            field_name=field_name,
            coordinates_nm=plot_coordinates,
            triangles=triangles,
            raw=np.asarray(raw),
            prediction=np.asarray(prediction),
            display_raw=display_raw,
            display_prediction=display_prediction,
            display_label=display_label,
            parameters=case["device_features"][:],
        )


def _display_values(
    values: np.ndarray,
    field_name: str,
    transform_scale: float,
    scale_mode: str,
) -> tuple[np.ndarray, str]:
    array = np.asarray(values, dtype=np.float64)
    if scale_mode == "Linear" or field_name == "Potential":
        return array, field_name
    scale = max(float(transform_scale), np.finfo(np.float64).tiny)
    if field_name in {"Electrons", "Holes"}:
        return np.log10(1.0 + np.maximum(array, 0.0) / scale), (
            f"log10(1 + {field_name}/{scale:.2g})"
        )
    return np.sign(array) * np.log10(1.0 + np.abs(array) / scale), (
        f"signed log10(1 + |{field_name}|/{scale:.2g})"
    )


def _limits(values: np.ndarray, range_mode: str) -> tuple[float, float]:
    finite = np.asarray(values, dtype=np.float64)
    finite = finite[np.isfinite(finite)]
    if not len(finite):
        return -1.0, 1.0
    if range_mode == "Robust 1-99%":
        low, high = np.percentile(finite, (1.0, 99.0))
    else:
        low, high = float(np.min(finite)), float(np.max(finite))
    if high <= low:
        delta = max(abs(float(high)) * 0.01, 1e-12)
        return float(low - delta), float(high + delta)
    return float(low), float(high)


def _draw_field(axis, data: FieldData, values: np.ndarray, norm, cmap: str):
    x = data.coordinates_nm[:, 0]
    y = data.coordinates_nm[:, 1]
    if data.domain == "node":
        return axis.tripcolor(
            x,
            y,
            data.triangles,
            values,
            shading="gouraud",
            cmap=cmap,
            norm=norm,
            rasterized=True,
        )
    return axis.tripcolor(
        x,
        y,
        data.triangles,
        facecolors=values,
        shading="flat",
        cmap=cmap,
        norm=norm,
        rasterized=True,
    )


def render_comparison(
    figure: Figure,
    data: FieldData,
    range_mode: str = "Robust 1-99%",
) -> dict[str, float]:
    figure.clear()
    figure.set_facecolor("white")
    grid = figure.add_gridspec(
        1,
        5,
        width_ratios=(1.0, 1.0, 0.055, 1.0, 0.055),
        left=0.055,
        right=0.97,
        bottom=0.10,
        top=0.82,
        wspace=0.35,
    )
    axes = [figure.add_subplot(grid[0, index]) for index in (0, 1, 3)]
    shared_colorbar_axis = figure.add_subplot(grid[0, 2])
    error_colorbar_axis = figure.add_subplot(grid[0, 4])
    combined = np.concatenate((data.display_raw, data.display_prediction))
    low, high = _limits(combined, range_mode)
    signed = data.field_name not in {"Potential", "Electrons", "Holes"}
    if signed and low < 0.0 < high:
        extent = max(abs(low), abs(high))
        shared_norm = TwoSlopeNorm(vmin=-extent, vcenter=0.0, vmax=extent)
        cmap = "coolwarm"
    else:
        shared_norm = Normalize(vmin=low, vmax=high)
        cmap = "viridis"
    difference = data.display_prediction - data.display_raw
    error_limit = _limits(np.abs(difference), range_mode)[1]
    error_limit = max(error_limit, 1e-12)
    error_norm = TwoSlopeNorm(vmin=-error_limit, vcenter=0.0, vmax=error_limit)
    raw_image = _draw_field(axes[0], data, data.display_raw, shared_norm, cmap)
    _draw_field(axes[1], data, data.display_prediction, shared_norm, cmap)
    error_image = _draw_field(axes[2], data, difference, error_norm, "coolwarm")
    for index, (axis, title) in enumerate(
        zip(axes, ("Raw TCAD", "Coordinate MLP", "Model - Raw"))
    ):
        axis.set_facecolor("white")
        axis.set_title(title)
        axis.set_xlabel("x (nm)")
        axis.set_ylabel("y (nm)" if index == 0 else "")
        axis.tick_params(axis="y", labelleft=index == 0)
        axis.set_aspect("equal", adjustable="box")
        axis.yaxis.set_major_locator(MaxNLocator(6))
    shared_colorbar = figure.colorbar(raw_image, cax=shared_colorbar_axis)
    shared_colorbar.set_label(data.display_label)
    error_colorbar = figure.colorbar(error_image, cax=error_colorbar_axis)
    error_colorbar.set_label(f"difference in {data.display_label}")
    raw_difference = data.prediction.astype(np.float64) - data.raw.astype(np.float64)
    display_rmse = float(np.sqrt(np.mean(np.square(difference))))
    raw_mae = float(np.mean(np.abs(raw_difference)))
    length, tox, bulk, sd, ldd = data.parameters
    figure.suptitle(
        f"{data.case_id}  |  {data.field_name} ({data.domain})\n"
        f"L={length:g} nm, Tox={tox:g} nm, logB={bulk:g}, logSD={sd:g}, "
        f"logLDD={ldd:g}  |  display RMSE={display_rmse:.4g}, raw MAE={raw_mae:.4g}",
        fontsize=11,
    )
    return {"display_rmse": display_rmse, "raw_mae": raw_mae}


class ComparisonApp:
    def __init__(self, root: tk.Tk, comparison: FieldMapComparison) -> None:
        self.root = root
        self.comparison = comparison
        root.title("Field-map model check: Raw TCAD vs Coordinate MLP")
        root.geometry("1580x820")
        controls = ttk.Frame(root, padding=8)
        controls.pack(side=tk.TOP, fill=tk.X)
        self.split_var = tk.StringVar(value="validation")
        self.case_var = tk.StringVar()
        self.field_var = tk.StringVar(value="Potential")
        self.scale_var = tk.StringVar(value="Physics-aware")
        self.range_var = tk.StringVar(value="Robust 1-99%")
        self._combo(controls, "Split", self.split_var, tuple(SPLIT_INDEX), 0, self._split_changed)
        self.case_combo = self._combo(controls, "Device", self.case_var, (), 1, self.plot)
        self._combo(controls, "Field", self.field_var, FIELD_NAMES, 2, self.plot)
        self._combo(
            controls,
            "Scale",
            self.scale_var,
            ("Physics-aware", "Linear"),
            3,
            self.plot,
        )
        self._combo(
            controls,
            "Range",
            self.range_var,
            ("Robust 1-99%", "Full range"),
            4,
            self.plot,
        )
        ttk.Button(controls, text="Refresh", command=self.plot).grid(
            row=1, column=5, padx=8, pady=2, sticky="w"
        )
        self.status_var = tk.StringVar(value="")
        ttk.Label(controls, textvariable=self.status_var).grid(
            row=2, column=0, columnspan=6, sticky="w", padx=4, pady=(5, 0)
        )
        plot_frame = ttk.Frame(root)
        plot_frame.pack(fill=tk.BOTH, expand=True)
        self.figure = Figure(figsize=(15.5, 7.2), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        toolbar_frame = ttk.Frame(root)
        toolbar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        NavigationToolbar2Tk(self.canvas, toolbar_frame)
        root.protocol("WM_DELETE_WINDOW", self._close)
        self._split_changed()

    def _combo(self, parent, label, variable, values, column, callback):
        ttk.Label(parent, text=label).grid(row=0, column=column, padx=5, sticky="w")
        width = 52 if label == "Device" else 22
        combo = ttk.Combobox(
            parent, textvariable=variable, values=values, state="readonly", width=width
        )
        combo.grid(row=1, column=column, padx=5, pady=2, sticky="w")
        combo.bind("<<ComboboxSelected>>", lambda _event: callback())
        return combo

    def _split_changed(self) -> None:
        cases = self.comparison.cases(self.split_var.get())
        self.case_combo.configure(values=cases)
        if cases:
            self.case_var.set(cases[0])
            self.plot()

    def plot(self) -> None:
        if not self.case_var.get():
            return
        try:
            data = self.comparison.field_data(
                self.case_var.get(), self.field_var.get(), self.scale_var.get()
            )
            metrics = render_comparison(self.figure, data, self.range_var.get())
            self.status_var.set(
                f"Display-space RMSE: {metrics['display_rmse']:.6g}    "
                f"Raw MAE: {metrics['raw_mae']:.6g}    Test split is excluded."
            )
            self.canvas.draw_idle()
        except Exception as exc:
            messagebox.showerror("Field-map visualization error", str(exc))

    def _close(self) -> None:
        self.comparison.close()
        self.root.destroy()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _parse_args() -> argparse.Namespace:
    root = _repo_root()
    final_model = root / "ai/model_artifacts/field_map_model/final/coordinate_mlp_physics"
    selected_model = root / "ai/model_artifacts/field_map_model/candidates/element_bulk_physics"
    baseline_model = root / "ai/model_artifacts/field_map_model/baselines/coordinate_mlp"
    default_model = final_model if (final_model / "element/model.pt").exists() else (selected_model if (selected_model / "element/model.pt").exists() else baseline_model)
    parser = argparse.ArgumentParser(description="Compare raw and predicted field maps")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=root / "ai/model_artifacts/field_map_model/dataset/fieldmap_dataset.h5",
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=default_model,
    )
    parser.add_argument("--split", choices=tuple(SPLIT_INDEX), default="validation")
    parser.add_argument("--device-id", default="")
    parser.add_argument("--field", choices=FIELD_NAMES, default="Potential")
    parser.add_argument("--scale", choices=("Physics-aware", "Linear"), default="Physics-aware")
    parser.add_argument(
        "--range", dest="range_mode", choices=("Robust 1-99%", "Full range"), default="Robust 1-99%"
    )
    parser.add_argument("--save", type=Path, help="Save one comparison image instead of opening the GUI")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    comparison = FieldMapComparison(args.dataset.resolve(), args.model_dir.resolve())
    if args.save:
        try:
            cases = comparison.cases(args.split)
            case_id = args.device_id or cases[0]
            if case_id not in cases:
                raise ValueError(f"Device {case_id!r} is not in the selected {args.split} split")
            data = comparison.field_data(case_id, args.field, args.scale)
            figure = Figure(figsize=(16, 6.8), dpi=120)
            render_comparison(figure, data, args.range_mode)
            FigureCanvasAgg(figure)
            args.save.resolve().parent.mkdir(parents=True, exist_ok=True)
            figure.savefig(args.save.resolve(), dpi=150, facecolor="white")
            print(
                json.dumps(
                    {"saved": str(args.save.resolve()), "device": case_id, "field": args.field},
                    indent=2,
                )
            )
            return 0
        finally:
            comparison.close()
    root = tk.Tk()
    ComparisonApp(root, comparison)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
