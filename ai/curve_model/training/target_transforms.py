from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.preprocessing import StandardScaler


SUPPORTED_MODES = ("standardized_raw", "signed_log", "asinh")
SUPPORTED_SCALERS = ("per_coordinate", "global")
DEFAULT_MODES = {"idvd": "asinh", "idvg": "signed_log"}
DEFAULT_CURRENT_SCALES = {"idvd": 1e-3, "idvg": 1e-10}


@dataclass
class TargetTransformer:
    """Invertible current transform fitted exclusively on training curves."""

    mode: str
    current_scale: float | None = None
    noise_floor: float = 0.0
    scaler_mode: str = "per_coordinate"
    scaler_: StandardScaler | None = None

    def fit(self, currents: np.ndarray) -> "TargetTransformer":
        currents = _curves(currents)
        if self.mode not in SUPPORTED_MODES:
            raise ValueError(f"Unsupported target mode {self.mode!r}: {SUPPORTED_MODES}")
        if self.scaler_mode not in SUPPORTED_SCALERS:
            raise ValueError(
                f"Unsupported scaler mode {self.scaler_mode!r}: {SUPPORTED_SCALERS}"
            )
        if self.mode != "standardized_raw":
            if self.current_scale is None:
                nonzero = np.abs(currents[np.nonzero(currents)])
                self.current_scale = (
                    float(np.percentile(nonzero, 1)) if len(nonzero) else 1.0
                )
            if not np.isfinite(self.current_scale) or self.current_scale <= 0:
                raise ValueError("current_scale must be finite and positive")
        if not np.isfinite(self.noise_floor) or self.noise_floor < 0:
            raise ValueError("noise_floor must be finite and non-negative")
        transformed = self.nonlinear_transform(currents)
        fit_values = (
            transformed
            if self.scaler_mode == "per_coordinate"
            else transformed.reshape(-1, 1)
        )
        self.scaler_ = StandardScaler().fit(fit_values)
        return self

    def transform(self, currents: np.ndarray) -> np.ndarray:
        self._check_fitted()
        return self.scale_transform(self.nonlinear_transform(_curves(currents)))

    def inverse_transform(self, values: np.ndarray) -> np.ndarray:
        self._check_fitted()
        nonlinear = self.inverse_scale_transform(_curves(values))
        return self.inverse_nonlinear_transform(nonlinear)

    def nonlinear_transform(self, currents: np.ndarray) -> np.ndarray:
        currents = _curves(currents)
        if self.mode == "signed_log":
            return np.sign(currents) * np.log1p(np.abs(currents) / self.current_scale)
        if self.mode == "asinh":
            return np.arcsinh(currents / self.current_scale)
        return currents

    def inverse_nonlinear_transform(self, values: np.ndarray) -> np.ndarray:
        values = _curves(values)
        if self.mode == "signed_log":
            raw = np.sign(values) * self.current_scale * np.expm1(np.abs(values))
        elif self.mode == "asinh":
            raw = self.current_scale * np.sinh(values)
        else:
            raw = values
        return raw.astype(np.float32)

    def scale_transform(self, values: np.ndarray) -> np.ndarray:
        self._check_fitted()
        values = _curves(values)
        return ((values - self.scaler_.mean_) / self.scaler_.scale_).astype(np.float32)

    def inverse_scale_transform(self, values: np.ndarray) -> np.ndarray:
        self._check_fitted()
        values = _curves(values)
        return values * self.scaler_.scale_ + self.scaler_.mean_

    def state_dict(self) -> dict[str, object]:
        self._check_fitted()
        return {
            "mode": self.mode,
            "current_scale": self.current_scale,
            "noise_floor": self.noise_floor,
            "scaler_mode": self.scaler_mode,
            "mean": self.scaler_.mean_.tolist(),
            "scale": self.scaler_.scale_.tolist(),
        }

    @classmethod
    def from_state_dict(cls, state: dict[str, object]) -> "TargetTransformer":
        transformer = cls(
            str(state["mode"]),
            state.get("current_scale"),
            float(state.get("noise_floor", 0.0)),
            str(state.get("scaler_mode", "per_coordinate")),
        )
        mean = np.asarray(state["mean"], dtype=np.float64)
        scale_key = "scale" if "scale" in state else "std"
        scale = np.asarray(state[scale_key], dtype=np.float64)
        transformer.scaler_ = StandardScaler()
        transformer.scaler_.mean_ = mean
        transformer.scaler_.scale_ = scale
        transformer.scaler_.var_ = np.square(scale)
        transformer.scaler_.n_features_in_ = len(mean)
        transformer.scaler_.n_samples_seen_ = 1
        return transformer

    def _check_fitted(self) -> None:
        if self.scaler_ is None:
            raise RuntimeError("TargetTransformer must be fitted on training targets first")


def _curves(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 2 or not np.all(np.isfinite(array)):
        raise ValueError("Expected a finite 2D curve array")
    return array


def make_target_transformer(
    kind: str,
    mode: str = "auto",
    *,
    current_scale: float | None = None,
    noise_floor: float = 0.0,
    scaler_mode: str = "per_coordinate",
) -> TargetTransformer:
    if kind not in DEFAULT_MODES:
        raise ValueError(f"Unknown curve kind {kind!r}; expected {tuple(DEFAULT_MODES)}")
    selected_mode = DEFAULT_MODES[kind] if mode == "auto" else mode
    scale = current_scale
    if scale is None and selected_mode != "standardized_raw":
        scale = DEFAULT_CURRENT_SCALES[kind]
    return TargetTransformer(selected_mode, scale, noise_floor, scaler_mode)
