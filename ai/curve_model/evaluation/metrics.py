from __future__ import annotations

from typing import Iterable

import numpy as np


PERCENTILES = (50, 90, 95, 99)


def signed_log(values: np.ndarray, scale: float) -> np.ndarray:
    return np.sign(values) * np.log1p(np.abs(values) / scale)


def curve_metric_arrays(
    targets: np.ndarray, predictions: np.ndarray, log_scale: float
) -> dict[str, np.ndarray]:
    target = np.asarray(targets, dtype=np.float64)
    prediction = np.asarray(predictions, dtype=np.float64)
    difference = prediction - target
    squared = np.square(difference)
    linear_rmse = np.sqrt(np.mean(squared, axis=1))
    amplitude = np.maximum(np.max(np.abs(target), axis=1), log_scale)
    target_mean = np.mean(target, axis=1, keepdims=True)
    total_variation = np.sum(np.square(target - target_mean), axis=1)
    residual = np.sum(squared, axis=1)
    r_squared = np.full(len(target), np.nan, dtype=np.float64)
    # R² is undefined/misleading for nearly flat off-state curves.
    valid_r2 = (np.ptp(target, axis=1) > log_scale) & (
        total_variation > np.finfo(np.float64).eps
    )
    r_squared[valid_r2] = 1.0 - residual[valid_r2] / total_variation[valid_r2]

    target_signed_log = signed_log(target, log_scale)
    prediction_signed_log = signed_log(prediction, log_scale)
    signed_log_difference = prediction_signed_log - target_signed_log
    target_decades = np.log10(np.maximum(np.abs(target), log_scale))
    prediction_decades = np.log10(np.maximum(np.abs(prediction), log_scale))
    decade_difference = prediction_decades - target_decades
    return {
        "linear_mae": np.mean(np.abs(difference), axis=1),
        "linear_rmse": linear_rmse,
        "nrmse": linear_rmse / amplitude,
        "r_squared": r_squared,
        "signed_log_mae": np.mean(np.abs(signed_log_difference), axis=1),
        "signed_log_rmse": np.sqrt(np.mean(np.square(signed_log_difference), axis=1)),
        "decade_mae": np.mean(np.abs(decade_difference), axis=1),
        "decade_rmse": np.sqrt(np.mean(np.square(decade_difference), axis=1)),
    }


def distribution_summary(values: Iterable[float]) -> dict[str, float | int]:
    array = np.asarray(list(values), dtype=np.float64)
    array = array[np.isfinite(array)]
    if not len(array):
        return {"valid_count": 0}
    summary: dict[str, float | int] = {
        "valid_count": int(len(array)),
        "mean": float(np.mean(array)),
        "std": float(np.std(array)),
        "min": float(np.min(array)),
        "max": float(np.max(array)),
    }
    for percentile in PERCENTILES:
        summary[f"p{percentile}"] = float(np.percentile(array, percentile))
    return summary


def curve_evaluation_report(
    targets: np.ndarray, predictions: np.ndarray, log_scale: float
) -> dict[str, object]:
    arrays = curve_metric_arrays(targets, predictions, log_scale)
    difference = predictions.astype(np.float64) - targets.astype(np.float64)
    target_flat = targets.astype(np.float64).ravel()
    prediction_flat = predictions.astype(np.float64).ravel()
    total_variation = float(np.sum(np.square(target_flat - np.mean(target_flat))))
    residual = float(np.sum(np.square(prediction_flat - target_flat)))
    return {
        "samples": int(len(targets)),
        "points_per_curve": int(targets.shape[1]),
        "log_floor_mA_per_um": log_scale,
        "global": {
            "linear_mae": float(np.mean(np.abs(difference))),
            "linear_rmse": float(np.sqrt(np.mean(np.square(difference)))),
            "r_squared": 1.0 - residual / total_variation,
        },
        "per_curve_distributions": {
            name: distribution_summary(values) for name, values in arrays.items()
        },
    }
