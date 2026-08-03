from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

from ai.shared.device_parameters import PARAMETER_OPTIONS


class ConditionValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ExperimentComparison:
    changed_parameters: tuple[str, ...]
    fixed_parameters: tuple[str, ...]


SUPPORTED_PARAMETERS = tuple(PARAMETER_OPTIONS)


def validate_model_conditions(
    conditions: Mapping[str, float],
    *,
    require_supported_value: bool = False,
) -> dict[str, float]:
    missing = set(SUPPORTED_PARAMETERS) - set(conditions)
    extra = set(conditions) - set(SUPPORTED_PARAMETERS)
    if missing or extra:
        details = []
        if missing:
            details.append("missing=" + ",".join(sorted(missing)))
        if extra:
            details.append("unknown=" + ",".join(sorted(extra)))
        raise ConditionValidationError("invalid_parameter_set:" + ";".join(details))

    validated: dict[str, float] = {}
    for name in SUPPORTED_PARAMETERS:
        value = float(conditions[name])
        if not math.isfinite(value) or value <= 0:
            raise ConditionValidationError(f"invalid_parameter_value:{name}")
        supported = tuple(float(item) for item in PARAMETER_OPTIONS[name])
        if value < min(supported) or value > max(supported):
            raise ConditionValidationError(f"outside_model_range:{name}")
        if require_supported_value and not any(math.isclose(value, item, rel_tol=1e-12) for item in supported):
            raise ConditionValidationError(f"unverified_parameter_value:{name}")
        validated[name] = value
    return validated


def compare_experiment_conditions(
    baseline: Mapping[str, float],
    comparison: Mapping[str, float],
    *,
    require_single_change: bool = True,
) -> ExperimentComparison:
    before = validate_model_conditions(baseline, require_supported_value=True)
    after = validate_model_conditions(comparison, require_supported_value=True)
    changed = tuple(name for name in SUPPORTED_PARAMETERS if before[name] != after[name])
    fixed = tuple(name for name in SUPPORTED_PARAMETERS if before[name] == after[name])
    if not changed:
        raise ConditionValidationError("experiment_has_no_changed_parameter")
    if require_single_change and len(changed) != 1:
        raise ConditionValidationError("experiment_must_change_exactly_one_parameter")
    return ExperimentComparison(changed, fixed)
