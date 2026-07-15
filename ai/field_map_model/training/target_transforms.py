from __future__ import annotations

from dataclasses import dataclass

import numpy as np


SUPPORTED_MODES = ("identity", "log1p", "asinh", "signed_log1p")
SUPPORTED_SCALERS = ("standard", "robust")


def _nonlinear(values: np.ndarray, mode: str, scale: float) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if mode == "identity":
        return array
    if mode == "log1p":
        if np.any(array < 0.0):
            raise ValueError("log1p transform received negative values")
        return np.log1p(array / scale)
    if mode == "asinh":
        return np.arcsinh(array / scale)
    if mode == "signed_log1p":
        return np.sign(array) * np.log1p(np.abs(array) / scale)
    raise ValueError(f"Unsupported transform mode: {mode}")


def _inverse_nonlinear(values: np.ndarray, mode: str, scale: float) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if mode == "identity":
        return array
    if mode == "log1p":
        # Carrier densities are non-negative physical quantities. Regressors can
        # extrapolate slightly below the transformed zero boundary.
        return np.maximum(scale * np.expm1(array), 0.0)
    if mode == "asinh":
        return scale * np.sinh(array)
    if mode == "signed_log1p":
        return np.sign(array) * scale * np.expm1(np.abs(array))
    raise ValueError(f"Unsupported transform mode: {mode}")


def characteristic_scale(values: np.ndarray, quantile: float) -> float:
    array = np.abs(np.asarray(values, dtype=np.float64).ravel())
    nonzero = array[np.isfinite(array) & (array > 0.0)]
    if not len(nonzero):
        return 1.0
    value = float(np.percentile(nonzero, quantile))
    return max(value, np.finfo(np.float64).tiny)


@dataclass
class FieldTransformer:
    mode: str
    nonlinear_scale: float
    scaler_mode: str
    center: float = 0.0
    spread: float = 1.0

    def fit(self, values: np.ndarray) -> "FieldTransformer":
        if self.mode not in SUPPORTED_MODES:
            raise ValueError(f"Unsupported mode {self.mode!r}")
        if self.scaler_mode not in SUPPORTED_SCALERS:
            raise ValueError(f"Unsupported scaler {self.scaler_mode!r}")
        transformed = _nonlinear(values, self.mode, self.nonlinear_scale)
        if self.scaler_mode == "standard":
            self.center = float(np.mean(transformed, dtype=np.float64))
            self.spread = float(np.std(transformed, dtype=np.float64))
        else:
            self.center = float(np.median(transformed))
            q25, q75 = np.percentile(transformed, (25.0, 75.0))
            self.spread = float(q75 - q25)
        if not np.isfinite(self.spread) or self.spread <= np.finfo(np.float64).eps:
            self.spread = 1.0
        return self

    def transform(self, values: np.ndarray) -> np.ndarray:
        transformed = _nonlinear(values, self.mode, self.nonlinear_scale)
        return ((transformed - self.center) / self.spread).astype(np.float32)

    def inverse_transform(self, values: np.ndarray) -> np.ndarray:
        transformed = np.asarray(values, dtype=np.float64) * self.spread + self.center
        return _inverse_nonlinear(transformed, self.mode, self.nonlinear_scale).astype(
            np.float32
        )

    def state_dict(self) -> dict[str, float | str]:
        return {
            "mode": self.mode,
            "nonlinear_scale": self.nonlinear_scale,
            "scaler_mode": self.scaler_mode,
            "center": self.center,
            "spread": self.spread,
        }


def fit_transformers(
    targets: np.ndarray,
    field_names: tuple[str, ...],
    nonlinear_family: str,
    scaler_mode: str,
    scale_quantile: float,
    minimum_scales: dict[str, float] | None = None,
) -> list[FieldTransformer]:
    transformers: list[FieldTransformer] = []
    positive_fields = {"Electrons", "Holes"}
    for column, field_name in enumerate(field_names):
        values = targets[:, column]
        if nonlinear_family == "raw" or field_name == "Potential":
            mode = "identity"
            scale = 1.0
        elif field_name in positive_fields:
            mode = "log1p"
            scale = characteristic_scale(values, scale_quantile)
        elif nonlinear_family == "asinh":
            mode = "asinh"
            scale = characteristic_scale(values, scale_quantile)
        elif nonlinear_family == "signed_log1p":
            mode = "signed_log1p"
            scale = characteristic_scale(values, scale_quantile)
        else:
            raise ValueError(f"Unsupported nonlinear family: {nonlinear_family}")
        if minimum_scales is not None:
            scale = max(scale, float(minimum_scales.get(field_name, 0.0)))
        transformers.append(FieldTransformer(mode, scale, scaler_mode).fit(values))
    return transformers


def transform_matrix(values: np.ndarray, transformers: list[FieldTransformer]) -> np.ndarray:
    return np.column_stack(
        [transformer.transform(values[:, index]) for index, transformer in enumerate(transformers)]
    ).astype(np.float32)


def inverse_transform_matrix(
    values: np.ndarray, transformers: list[FieldTransformer]
) -> np.ndarray:
    return np.column_stack(
        [
            transformer.inverse_transform(values[:, index])
            for index, transformer in enumerate(transformers)
        ]
    ).astype(np.float32)
