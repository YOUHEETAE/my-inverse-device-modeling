from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ai.curve_model.data.current_preprocessing import constrain_current_predictions
from ai.curve_model.models.pca_xgboost import (
    BiasSeparatedPCAXGBoostRegressor,
    load_curve_regressor,
)
from ai.curve_model.training.target_transforms import TargetTransformer
from tcad.data_extraction.parameter_extraction_core import extract_parameters


PARAMETER_OPTIONS = {
    "L": ("100", "120", "150", "170", "200", "250", "300", "400", "500", "700", "1000", "1300", "1600"),
    "T": ("5", "7", "10", "12", "15", "20", "27", "35", "50"),
    "B": ("5e15", "1e16", "5e16"),
    "SD": ("1e19", "5e19", "1e20", "5e20"),
    "LDD": ("1e17", "5e17", "1e18", "5e18"),
}
DEFAULT_PARAMETERS = {"L": "200", "T": "20", "B": "1e16", "SD": "1e20", "LDD": "1e18"}
IDVG_FIXED_BIASES = (0.05, 1.5)


@dataclass(frozen=True)
class CurvePrediction:
    kind: str
    grid: np.ndarray
    fixed_biases: np.ndarray
    currents: np.ndarray


class FinalCurvePredictor:
    """Load the finalized IdVd/IdVg packages and generate physical currents."""

    def __init__(self, model_dir: Path) -> None:
        self.models = {}
        self.transforms: dict[str, TargetTransformer | None] = {}
        self.metadata: dict[str, dict[str, object]] = {}
        for kind in ("idvd", "idvg"):
            kind_dir = Path(model_dir) / kind
            model_path = kind_dir / "model.pkl"
            transform_path = kind_dir / "target_transform.json"
            metadata_path = kind_dir / "inference_metadata.json"
            for required in (model_path, transform_path, metadata_path):
                if not required.is_file():
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
        features = np.column_stack(
            (np.repeat(base, len(fixed_biases), axis=0), fixed_biases)
        ).astype(np.float32)
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


def device_features(values: dict[str, str]) -> np.ndarray:
    parsed = {name: float(text) for name, text in values.items()}
    if any(not math.isfinite(value) or value <= 0.0 for value in parsed.values()):
        raise ValueError("All structure and doping parameters must be positive finite numbers.")
    return np.asarray(
        [parsed["L"], parsed["T"], math.log10(parsed["B"]), math.log10(parsed["SD"]), math.log10(parsed["LDD"])],
        dtype=np.float32,
    )


def range_warning(values: dict[str, str]) -> str:
    outside = [
        name
        for name, options in PARAMETER_OPTIONS.items()
        if float(values[name]) < min(map(float, options))
        or float(values[name]) > max(map(float, options))
    ]
    return "" if not outside else "Extrapolation warning: " + ", ".join(outside) + " is outside the training range."


def _curve_at_bias(prediction: CurvePrediction, target_bias: float) -> tuple[np.ndarray, np.ndarray]:
    matches = np.flatnonzero(np.isclose(prediction.fixed_biases, target_bias, rtol=0.0, atol=1e-6))
    if not len(matches):
        raise ValueError(f"Missing {prediction.kind} curve at fixed bias {target_bias:g} V")
    return prediction.grid, prediction.currents[int(matches[0])]


def extract_electrical_parameters(idvd: CurvePrediction, idvg: CurvePrediction) -> dict[str, float]:
    return extract_parameters(
        {"IDVD_VG1P5": _curve_at_bias(idvd, 1.5), "IDVD_VG3P0": _curve_at_bias(idvd, 3.0)},
        {"IDVG_VD0P05": _curve_at_bias(idvg, 0.05), "IDVG_VD1P5": _curve_at_bias(idvg, 1.5)},
    )
