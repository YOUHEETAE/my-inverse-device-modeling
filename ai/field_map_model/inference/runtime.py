from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


INPUT_NAMES = (
    "L_um",
    "Tox_over_50nm",
    "log10_B_minus_16",
    "log10_SD_minus_19",
    "log10_LDD_minus_17",
    "inverse_L_um",
    "L_over_Tox_div_100",
    "x_device_fraction",
    "x_channel_coordinate",
    "y_device_fraction",
    "y_um",
    "region_bulk",
    "region_oxide",
    "region_gate",
    "signed_log_local_net_doping",
)


def coordinate_features(
    device_features: np.ndarray,
    coordinates_nm: np.ndarray,
    region_ids: np.ndarray,
    local_net_doping: np.ndarray,
    mesh_node_xy_nm: np.ndarray,
) -> np.ndarray:
    """Build the frozen 15-column feature schema used by the final checkpoints."""
    length_nm, tox_nm, log_bulk, log_sd, log_ldd = np.asarray(
        device_features, dtype=np.float64
    )
    x_min, y_min = np.min(mesh_node_xy_nm, axis=0)
    x_max, y_max = np.max(mesh_node_xy_nm, axis=0)
    width = max(float(x_max - x_min), 1.0)
    height = max(float(y_max - y_min), 1.0)
    side_extension = max((width - length_nm) / 2.0, 0.0)
    x = np.asarray(coordinates_nm[:, 0], dtype=np.float64)
    y = np.asarray(coordinates_nm[:, 1], dtype=np.float64)
    region_one_hot = np.eye(3, dtype=np.float64)[np.asarray(region_ids, dtype=np.int64)]
    local_doping = np.sign(local_net_doping) * np.log1p(
        np.abs(local_net_doping) / 1e15
    )
    global_columns = np.column_stack(
        (
            np.full(len(x), length_nm / 1000.0),
            np.full(len(x), tox_nm / 50.0),
            np.full(len(x), log_bulk - 16.0),
            np.full(len(x), log_sd - 19.0),
            np.full(len(x), log_ldd - 17.0),
            np.full(len(x), 1000.0 / max(length_nm, 1.0)),
            np.full(len(x), (length_nm / max(tox_nm, 1.0)) / 100.0),
        )
    )
    spatial_columns = np.column_stack(
        (
            (x - x_min) / width,
            (x - (x_min + side_extension)) / max(length_nm, 1.0),
            (y - y_min) / height,
            y / 1000.0,
        )
    )
    return np.column_stack(
        (global_columns, spatial_columns, region_one_hot, local_doping)
    ).astype(np.float32)


@dataclass(frozen=True)
class InverseFieldTransform:
    mode: str
    nonlinear_scale: float
    center: float
    spread: float

    def inverse(self, values: np.ndarray) -> np.ndarray:
        transformed = np.asarray(values, dtype=np.float64) * self.spread + self.center
        if self.mode == "identity":
            result = transformed
        elif self.mode == "log1p":
            result = np.maximum(self.nonlinear_scale * np.expm1(transformed), 0.0)
        elif self.mode == "asinh":
            result = self.nonlinear_scale * np.sinh(transformed)
        elif self.mode == "signed_log1p":
            result = (
                np.sign(transformed)
                * self.nonlinear_scale
                * np.expm1(np.abs(transformed))
            )
        else:
            raise ValueError(f"Unsupported checkpoint transform: {self.mode}")
        return np.asarray(result, dtype=np.float32)


class DomainPredictor:
    """NumPy-only inference loader for one node or element model package."""

    def __init__(self, model_dir: Path) -> None:
        model_dir = Path(model_dir)
        with np.load(model_dir / "model.npz", allow_pickle=False) as archive:
            self.weights = {name: archive[name] for name in archive.files}
        scaler = json.loads((model_dir / "feature_scaler.json").read_text(encoding="utf-8"))
        self.feature_mean = np.asarray(scaler["mean"], dtype=np.float64)
        self.feature_scale = np.asarray(scaler["scale"], dtype=np.float64)
        if len(self.feature_mean) != len(INPUT_NAMES):
            raise ValueError("Model input feature schema does not match runtime")
        states = json.loads((model_dir / "target_transform.json").read_text(encoding="utf-8"))
        self.field_names = tuple(str(name) for name in states)
        self.transforms = tuple(
            InverseFieldTransform(
                mode=str(states[name]["mode"]),
                nonlinear_scale=float(states[name]["nonlinear_scale"]),
                center=float(states[name]["center"]),
                spread=float(states[name]["spread"]),
            )
            for name in self.field_names
        )
        self.residual_blocks = len(
            {
                int(name.split(".")[1])
                for name in self.weights
                if name.startswith("blocks.")
            }
        )
        output_weight = self.weights["output_layer.weight"]
        if output_weight.shape[0] != len(self.field_names):
            raise ValueError("Model output schema does not match target transforms")

    def _linear(self, values: np.ndarray, prefix: str) -> np.ndarray:
        return values @ self.weights[f"{prefix}.weight"].T + self.weights[f"{prefix}.bias"]

    @staticmethod
    def _silu(values: np.ndarray) -> np.ndarray:
        sigmoid = np.empty_like(values)
        positive = values >= 0
        sigmoid[positive] = 1.0 / (1.0 + np.exp(-values[positive]))
        exponential = np.exp(values[~positive])
        sigmoid[~positive] = exponential / (1.0 + exponential)
        return values * sigmoid

    def _forward(self, values: np.ndarray) -> np.ndarray:
        hidden = self._silu(self._linear(values, "input_layer.0"))
        for block in range(self.residual_blocks):
            residual = self._silu(self._linear(hidden, f"blocks.{block}.layers.0"))
            residual = self._linear(residual, f"blocks.{block}.layers.3")
            combined = hidden + residual
            mean = combined.mean(axis=1, keepdims=True)
            variance = ((combined - mean) ** 2).mean(axis=1, keepdims=True)
            normalized = (combined - mean) / np.sqrt(variance + 1e-5)
            hidden = (
                normalized * self.weights[f"blocks.{block}.normalization.weight"]
                + self.weights[f"blocks.{block}.normalization.bias"]
            )
        return self._linear(hidden, "output_layer")

    def predict(self, features: np.ndarray, batch_size: int = 8192) -> np.ndarray:
        scaled = ((features - self.feature_mean) / self.feature_scale).astype(np.float32)
        batches = [
            self._forward(scaled[start:start + batch_size])
            for start in range(0, len(scaled), batch_size)
        ]
        transformed = np.concatenate(batches).astype(np.float32)
        prediction = np.column_stack(
            [transform.inverse(transformed[:, column]) for column, transform in enumerate(self.transforms)]
        ).astype(np.float32)
        for column, name in enumerate(self.field_names):
            if name in {"Electrons", "Holes"}:
                prediction[:, column] = np.maximum(prediction[:, column], 0.0)
        return prediction
