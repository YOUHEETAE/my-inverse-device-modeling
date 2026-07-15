from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import numpy as np

from ai.curve_model.training.target_transforms import (
    SUPPORTED_MODES,
    SUPPORTED_SCALERS,
    TargetTransformer,
    make_target_transformer,
)


def load_preprocessing_config(path: Path | None) -> dict[str, object] | None:
    if path is None:
        return None
    state = json.loads(path.read_text(encoding="utf-8"))
    validate_preprocessing_config(state)
    state["source_file"] = str(path.resolve())
    return state


def validate_preprocessing_config(state: dict[str, object]) -> None:
    if int(state.get("schema_version", 0)) != 1:
        raise ValueError("Preprocessing config schema_version must be 1")
    if not str(state.get("name", "")).strip():
        raise ValueError("Preprocessing config requires a non-empty name")
    for kind in ("idvd", "idvg"):
        spec = state.get(kind)
        if not isinstance(spec, dict):
            raise ValueError(f"Preprocessing config requires an object for {kind}")
        if spec.get("mode") == "bias_separated":
            bias_specs = spec.get("bias_transforms")
            if kind != "idvd" or not isinstance(bias_specs, dict) or not bias_specs:
                raise ValueError("bias_separated is supported only for IdVd bias transforms")
            for bias, bias_spec in bias_specs.items():
                if not isinstance(bias_spec, dict):
                    raise ValueError(f"Invalid IdVd transform for bias {bias}")
                _validate_kind_spec(kind, bias_spec)
            continue
        _validate_kind_spec(kind, spec)


def _validate_kind_spec(kind: str, spec: dict[str, object]) -> None:
    if spec.get("mode") not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported {kind} transform mode: {spec.get('mode')}")
    if spec.get("scaler_mode", "per_coordinate") not in SUPPORTED_SCALERS:
        raise ValueError(f"Unsupported {kind} scaler mode")
    if spec.get("scale_rule", "explicit") != "explicit":
        raise ValueError(f"Only explicit frozen scales are supported for {kind}")


def bias_spec(spec: dict[str, object] | None, bias: float) -> dict[str, object] | None:
    if spec is None or spec.get("mode") != "bias_separated":
        return deepcopy(spec)
    transforms = spec["bias_transforms"]
    key = str(float(bias))
    if key not in transforms:
        raise ValueError(f"Missing configured IdVd transform for bias {key}")
    return deepcopy(transforms[key])


def kind_spec(config: dict[str, object] | None, kind: str) -> dict[str, object] | None:
    if config is None:
        return None
    return deepcopy(config[kind])


def fit_configured_transformer(
    kind: str,
    currents: np.ndarray,
    grid: np.ndarray,
    spec: dict[str, object],
) -> tuple[TargetTransformer, dict[str, object]]:
    scale = _resolve_scale(currents, grid, spec)
    multiplier = float(spec.get("scale_multiplier", 1.0))
    resolved_scale = scale * multiplier
    transformer = make_target_transformer(
        kind,
        str(spec["mode"]),
        current_scale=resolved_scale,
        noise_floor=float(spec.get("noise_floor", 0.0)),
        scaler_mode=str(spec.get("scaler_mode", "per_coordinate")),
    ).fit(currents)
    resolution = {
        "mode": transformer.mode,
        "scale_rule": str(spec.get("scale_rule", "explicit")),
        "base_scale_mA_per_um": scale,
        "scale_multiplier": multiplier,
        "resolved_scale_mA_per_um": resolved_scale,
        "noise_floor_mA_per_um": transformer.noise_floor,
        "scaler_mode": transformer.scaler_mode,
    }
    return transformer, resolution


def _resolve_scale(
    currents: np.ndarray, grid: np.ndarray, spec: dict[str, object]
) -> float:
    del currents, grid
    value = float(spec["current_scale_mA_per_um"])
    if not np.isfinite(value) or value <= 0:
        raise ValueError(f"Resolved current scale must be positive, got {value}")
    return value
