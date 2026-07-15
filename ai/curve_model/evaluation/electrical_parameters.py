from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from ai.curve_model.evaluation.metrics import distribution_summary
from tcad.data_extraction.parameter_extraction_core import extract_parameters


@dataclass(frozen=True)
class ParameterSpec:
    label: str
    error_unit: str
    tolerance: float
    error: Callable[[float, float], float]


def _absolute(factor: float = 1.0) -> Callable[[float, float], float]:
    return lambda actual, predicted: abs(predicted - actual) * factor


def _relative_percent(actual: float, predicted: float) -> float:
    return abs(predicted - actual) / max(abs(actual), 1e-30) * 100.0


def _decade_error(actual: float, predicted: float) -> float:
    return abs(
        np.log10(max(abs(predicted), 1e-30))
        - np.log10(max(abs(actual), 1e-30))
    )


PARAMETER_SPECS: dict[str, ParameterSpec] = {
    "vth_low_v": ParameterSpec("Vth low", "mV", 50.0, _absolute(1000.0)),
    "vth_high_v": ParameterSpec("Vth high", "mV", 50.0, _absolute(1000.0)),
    "ion_ma_per_um": ParameterSpec("Ion", "%", 5.0, _relative_percent),
    "ioff_ma_per_um": ParameterSpec("Ioff", "decade", 0.5, _decade_error),
    "ss_mv_per_dec": ParameterSpec("SS", "mV/dec", 10.0, _absolute()),
    "dibl_gm_v_per_v": ParameterSpec("DIBL", "mV/V", 50.0, _absolute(1000.0)),
    "gm_max_ms_per_um": ParameterSpec("gm max", "mS/um", 0.01, _absolute()),
    "gds_ms_per_um": ParameterSpec("gds", "mS/um", 0.01, _absolute()),
    "ron_kohm_um": ParameterSpec("Ron", "%", 10.0, _relative_percent),
    "lambda_per_v": ParameterSpec("lambda", "1/V", 0.01, _absolute()),
}


@dataclass(frozen=True)
class ParameterEvaluation:
    device_index: int
    actual: dict[str, float] | None
    predicted: dict[str, float] | None
    errors: dict[str, float]
    normalized_errors: dict[str, float]
    overall_score: float | None
    failure: str = ""


def evaluate_parameters(
    device_indices: list[int], idvd_bundle, idvg_bundle
) -> list[ParameterEvaluation]:
    results: list[ParameterEvaluation] = []
    for device_index in device_indices:
        try:
            actual = extract_parameters(
                _tagged_curves(idvd_bundle, device_index, predicted=False),
                _tagged_curves(idvg_bundle, device_index, predicted=False),
            )
        except (ValueError, FloatingPointError) as exc:
            results.append(
                ParameterEvaluation(device_index, None, None, {}, {}, None, f"target: {exc}")
            )
            continue
        try:
            predicted = extract_parameters(
                _tagged_curves(idvd_bundle, device_index, predicted=True),
                _tagged_curves(idvg_bundle, device_index, predicted=True),
            )
        except (ValueError, FloatingPointError) as exc:
            results.append(
                ParameterEvaluation(
                    device_index, actual, None, {}, {}, None, f"prediction: {exc}"
                )
            )
            continue
        errors = {
            name: spec.error(actual[name], predicted[name])
            for name, spec in PARAMETER_SPECS.items()
        }
        normalized = {
            name: errors[name] / spec.tolerance
            for name, spec in PARAMETER_SPECS.items()
        }
        results.append(
            ParameterEvaluation(
                device_index,
                actual,
                predicted,
                errors,
                normalized,
                float(np.mean(list(normalized.values()))),
            )
        )
    return results


def parameter_evaluation_report(
    evaluations: list[ParameterEvaluation],
) -> dict[str, object]:
    successful = [item for item in evaluations if item.overall_score is not None]
    return {
        "devices": len(evaluations),
        "successful": len(successful),
        "failed": len(evaluations) - len(successful),
        "overall_normalized_score": distribution_summary(
            item.overall_score for item in successful
        ),
        "parameters": {
            name: {
                "label": spec.label,
                "error_unit": spec.error_unit,
                "normalization_tolerance": spec.tolerance,
                "error_distribution": distribution_summary(
                    item.errors[name] for item in successful
                ),
                "normalized_error_distribution": distribution_summary(
                    item.normalized_errors[name] for item in successful
                ),
            }
            for name, spec in PARAMETER_SPECS.items()
        },
        "failures": [
            {"device_index": item.device_index, "reason": item.failure}
            for item in evaluations
            if item.failure
        ],
    }


def _tagged_curves(bundle, device_index: int, *, predicted: bool) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    positions = np.flatnonzero(bundle.device_indices == device_index)
    values = bundle.predictions if predicted else bundle.targets
    curves: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    expected = (
        ((1.5, "IDVD_VG1P5"), (3.0, "IDVD_VG3P0"))
        if bundle.kind == "idvd"
        else ((0.05, "IDVG_VD0P05"), (1.5, "IDVG_VD1P5"))
    )
    for target_bias, tag in expected:
        matches = [
            int(position)
            for position in positions
            if np.isclose(bundle.features[position, -1], target_bias, atol=1e-6)
        ]
        if not matches:
            raise ValueError(f"missing {tag}")
        curves[tag] = (bundle.grid, values[matches[0]])
    return curves
