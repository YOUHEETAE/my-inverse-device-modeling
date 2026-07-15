from __future__ import annotations

from datetime import datetime, timezone

from ai.curve_model.data.current_preprocessing import EVALUATION_LOG_FLOOR_MA_PER_UM
from ai.curve_model.evaluation.electrical_parameters import (
    parameter_evaluation_report,
)
from ai.curve_model.evaluation.metrics import curve_evaluation_report
from ai.curve_model.evaluation.selection import combined_selection_score


def build_evaluation_report(repository, split: str) -> dict[str, object]:
    curves: dict[str, object] = {}
    for kind in ("idvd", "idvg"):
        bundle = repository.bundle(kind, split)
        log_scale = EVALUATION_LOG_FLOOR_MA_PER_UM
        curves[kind] = curve_evaluation_report(
            bundle.targets, bundle.predictions, log_scale
        )
    split_index = {"train": 0, "validation": 1, "test": 2}[split]
    total_devices = int((repository.arrays["device_split"] == split_index).sum())
    evaluated_devices = len(repository.devices(split))
    report = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "model_family": repository.model_family,
        "split": split,
        "domain_policy": repository.domain_policy.state_dict(),
        "domain_coverage": {
            "evaluated_devices": evaluated_devices,
            "total_split_devices": total_devices,
            "excluded_devices": total_devices - evaluated_devices,
            "coverage_fraction": evaluated_devices / total_devices,
        },
        "curve_metrics": curves,
        "electrical_parameters": parameter_evaluation_report(
            repository.parameter_evaluations(split)
        ),
    }
    if split == "validation":
        report["selection_metric"] = combined_selection_score(curves)
    return report
