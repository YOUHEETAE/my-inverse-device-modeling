from __future__ import annotations

import numpy as np


PHYSICAL_NOISE_FLOOR_MA_PER_UM = 1e-10
EVALUATION_LOG_FLOOR_MA_PER_UM = 1e-10


def clean_current_targets(
    kind: str,
    currents: np.ndarray,
    grid: np.ndarray,
    *,
    noise_floor: float = PHYSICAL_NOISE_FLOOR_MA_PER_UM,
) -> np.ndarray:
    """Remove unresolved TCAD current noise without modifying source arrays."""
    cleaned = np.asarray(currents, dtype=np.float32).copy()
    if kind == "idvg":
        # Sub-floor and negative values are indistinguishable at TCAD resolution.
        np.maximum(cleaned, noise_floor, out=cleaned)
    elif kind == "idvd":
        # In this dataset every sub-floor IdVd value is the Vd=0 boundary point.
        zero_bias = np.isclose(np.asarray(grid), 0.0, rtol=0.0, atol=1e-12)
        if np.count_nonzero(zero_bias) != 1:
            raise ValueError("IdVd grid must contain exactly one Vd=0 point")
        cleaned[:, zero_bias] = 0.0
    else:
        raise ValueError(f"Unknown curve kind: {kind}")
    return cleaned


def constrain_current_predictions(
    kind: str, predictions: np.ndarray, grid: np.ndarray
) -> np.ndarray:
    """Apply the same physical output constraints used for clean targets."""
    return clean_current_targets(kind, predictions, grid)
