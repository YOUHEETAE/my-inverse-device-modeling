from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import combinations
from typing import Any, Literal

from .schemas import json_safe


ComparisonMode = Literal[
    "single_characterization",
    "controlled_pair",
    "compound_pair",
    "controlled_sweep",
    "mixed_group",
]
ClaimLevel = Literal[
    "descriptive_only",
    "multi_parameter_association",
    "controlled_association",
    "comparison_specific",
]

PARAMETER_VALUE_KEYS = {
    "channel_length": "channel_length_nm",
    "oxide_thickness": "oxide_thickness_nm",
    "bulk_doping": "bulk_doping_cm3",
    "source_drain_doping": "source_drain_doping_cm3",
    "ldd_doping": "ldd_doping_cm3",
}


@dataclass(frozen=True)
class ComparisonPlan:
    analysis_mode: ComparisonMode
    subject_count: int
    baseline_subject_id: str | None
    candidate_subject_ids: tuple[str, ...]
    selected_comparison_ids: tuple[str, ...]
    controlled_pair_ids: tuple[str, ...]
    compound_pair_ids: tuple[str, ...]
    same_condition_pair_ids: tuple[str, ...]
    changed_parameters: tuple[str, ...]
    fixed_parameters: tuple[str, ...]
    sweep_parameter: str | None
    sweep_subject_ids: tuple[str, ...]
    sweep_values: tuple[float, ...]
    sweep_order: Literal["ascending", "descending", "selected_order", "not_applicable"]
    representative_subject_ids: tuple[str, ...]
    allowed_claim_level: ClaimLevel
    requires_clarification: bool = False
    clarification_reason: str | None = None
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return json_safe(asdict(self))


def _subject_id(subject: dict[str, Any], index: int) -> str:
    return str(subject.get("subject_id") or f"curve_{index + 1}")


def _pair_id(left_index: int, right_index: int) -> str:
    return f"cmp_{left_index + 1}_{right_index + 1}"


def _parameter_values(
    subjects: list[dict[str, Any]],
) -> dict[str, tuple[float, ...]]:
    result: dict[str, tuple[float, ...]] = {}
    for parameter, value_key in PARAMETER_VALUE_KEYS.items():
        values = []
        for subject in subjects:
            raw = subject.get("device_parameters", {}).get(value_key)
            if raw is None:
                break
            values.append(float(raw))
        if len(values) == len(subjects):
            result[parameter] = tuple(values)
    return result


def _pair_change_count(
    parameter_values: dict[str, tuple[float, ...]],
    left_index: int,
    right_index: int,
) -> int:
    return sum(
        values[left_index] != values[right_index]
        for values in parameter_values.values()
    )


def _selected_order(
    values: tuple[float, ...],
) -> Literal["ascending", "descending", "selected_order"]:
    if all(left < right for left, right in zip(values, values[1:])):
        return "ascending"
    if all(left > right for left, right in zip(values, values[1:])):
        return "descending"
    return "selected_order"


def build_comparison_plan(
    subjects: list[dict[str, Any]],
    *,
    preferred_baseline_id: str | None = None,
) -> ComparisonPlan:
    if not subjects:
        raise ValueError("comparison_plan_requires_subject")

    subject_ids = tuple(_subject_id(subject, index) for index, subject in enumerate(subjects))
    if len(subject_ids) != len(set(subject_ids)):
        raise ValueError("comparison_plan_duplicate_subject_id")

    subject_count = len(subjects)
    if subject_count == 1:
        return ComparisonPlan(
            analysis_mode="single_characterization",
            subject_count=1,
            baseline_subject_id=None,
            candidate_subject_ids=(),
            selected_comparison_ids=(),
            controlled_pair_ids=(),
            compound_pair_ids=(),
            same_condition_pair_ids=(),
            changed_parameters=(),
            fixed_parameters=tuple(_parameter_values(subjects)),
            sweep_parameter=None,
            sweep_subject_ids=(),
            sweep_values=(),
            sweep_order="not_applicable",
            representative_subject_ids=(subject_ids[0],),
            allowed_claim_level="descriptive_only",
        )

    invalid_preference = bool(
        preferred_baseline_id and preferred_baseline_id not in subject_ids
    )
    baseline_id = (
        preferred_baseline_id
        if preferred_baseline_id in subject_ids
        else subject_ids[0]
    )
    parameter_values = _parameter_values(subjects)
    changed_parameters = tuple(
        parameter
        for parameter, values in parameter_values.items()
        if len(set(values)) > 1
    )
    fixed_parameters = tuple(
        parameter
        for parameter, values in parameter_values.items()
        if len(set(values)) == 1
    )

    controlled_pair_ids: list[str] = []
    compound_pair_ids: list[str] = []
    same_condition_pair_ids: list[str] = []
    for left_index, right_index in combinations(range(subject_count), 2):
        pair_id = _pair_id(left_index, right_index)
        change_count = _pair_change_count(
            parameter_values,
            left_index,
            right_index,
        )
        if change_count == 0:
            same_condition_pair_ids.append(pair_id)
        elif change_count == 1:
            controlled_pair_ids.append(pair_id)
        else:
            compound_pair_ids.append(pair_id)

    sweep_parameter = None
    sweep_subject_ids: tuple[str, ...] = ()
    sweep_values: tuple[float, ...] = ()
    sweep_order: Literal[
        "ascending", "descending", "selected_order", "not_applicable"
    ] = "not_applicable"
    if subject_count >= 3 and len(changed_parameters) == 1:
        sweep_parameter = changed_parameters[0]
        selected_values = parameter_values[sweep_parameter]
        ordered_indices = tuple(
            sorted(range(subject_count), key=lambda index: selected_values[index])
        )
        sweep_subject_ids = tuple(subject_ids[index] for index in ordered_indices)
        sweep_values = tuple(selected_values[index] for index in ordered_indices)
        sweep_order = _selected_order(selected_values)

    if subject_count == 2:
        if compound_pair_ids:
            analysis_mode: ComparisonMode = "compound_pair"
            allowed_claim_level: ClaimLevel = "multi_parameter_association"
        else:
            analysis_mode = "controlled_pair"
            allowed_claim_level = (
                "controlled_association"
                if controlled_pair_ids
                else "descriptive_only"
            )
    elif sweep_parameter:
        analysis_mode = "controlled_sweep"
        allowed_claim_level = "controlled_association"
    else:
        analysis_mode = "mixed_group"
        allowed_claim_level = (
            "comparison_specific"
            if controlled_pair_ids
            else "multi_parameter_association"
        )

    baseline_index = subject_ids.index(baseline_id)
    baseline_pair_ids = tuple(
        _pair_id(*sorted((baseline_index, candidate_index)))
        for candidate_index in range(subject_count)
        if candidate_index != baseline_index
    )
    if analysis_mode == "mixed_group" and controlled_pair_ids:
        selected_comparison_ids = tuple(controlled_pair_ids)
    else:
        selected_comparison_ids = baseline_pair_ids

    if sweep_subject_ids:
        representative_subject_ids = (
            sweep_subject_ids[0],
            sweep_subject_ids[-1],
        )
    elif controlled_pair_ids:
        representative_pair = controlled_pair_ids[0]
        left_index, right_index = (
            int(value) - 1
            for value in representative_pair.removeprefix("cmp_").split("_")
        )
        representative_subject_ids = (
            subject_ids[left_index],
            subject_ids[right_index],
        )
    else:
        baseline_index = subject_ids.index(baseline_id)
        candidate_indices = [
            index for index in range(subject_count)
            if index != baseline_index
        ]
        representative_index = max(
            candidate_indices,
            key=lambda index: (
                _pair_change_count(
                    parameter_values,
                    min(baseline_index, index),
                    max(baseline_index, index),
                ),
                sum(
                    abs(values[index] - values[baseline_index])
                    / max(abs(values[index]), abs(values[baseline_index]), 1e-30)
                    for values in parameter_values.values()
                ),
                -index,
            ),
        )
        representative_subject_ids = (
            baseline_id,
            subject_ids[representative_index],
        )

    plan = ComparisonPlan(
        analysis_mode=analysis_mode,
        subject_count=subject_count,
        baseline_subject_id=baseline_id,
        candidate_subject_ids=tuple(
            subject_id for subject_id in subject_ids if subject_id != baseline_id
        ),
        selected_comparison_ids=selected_comparison_ids,
        controlled_pair_ids=tuple(controlled_pair_ids),
        compound_pair_ids=tuple(compound_pair_ids),
        same_condition_pair_ids=tuple(same_condition_pair_ids),
        changed_parameters=changed_parameters,
        fixed_parameters=fixed_parameters,
        sweep_parameter=sweep_parameter,
        sweep_subject_ids=sweep_subject_ids,
        sweep_values=sweep_values,
        sweep_order=sweep_order,
        representative_subject_ids=representative_subject_ids,
        allowed_claim_level=allowed_claim_level,
        requires_clarification=invalid_preference,
        clarification_reason=(
            "requested_baseline_not_found" if invalid_preference else None
        ),
    )
    validate_comparison_plan(plan, subject_ids)
    return plan


def validate_comparison_plan(
    plan: ComparisonPlan,
    subject_ids: tuple[str, ...],
) -> None:
    known_subjects = set(subject_ids)
    if plan.subject_count != len(subject_ids):
        raise ValueError("comparison_plan_subject_count_mismatch")
    if plan.baseline_subject_id and plan.baseline_subject_id not in known_subjects:
        raise ValueError("comparison_plan_unknown_baseline")
    if not set(plan.candidate_subject_ids).issubset(known_subjects):
        raise ValueError("comparison_plan_unknown_candidate")
    if not set(plan.sweep_subject_ids).issubset(known_subjects):
        raise ValueError("comparison_plan_unknown_sweep_subject")
    if not set(plan.representative_subject_ids).issubset(known_subjects):
        raise ValueError("comparison_plan_unknown_representative_subject")
    if len(plan.representative_subject_ids) not in {1, 2}:
        raise ValueError("comparison_plan_invalid_representative_count")
    if bool(plan.sweep_parameter) != bool(plan.sweep_subject_ids):
        raise ValueError("comparison_plan_invalid_sweep")
    if plan.sweep_subject_ids and len(plan.sweep_subject_ids) != len(plan.sweep_values):
        raise ValueError("comparison_plan_sweep_length_mismatch")
    if set(plan.changed_parameters) & set(plan.fixed_parameters):
        raise ValueError("comparison_plan_parameter_overlap")
    if plan.requires_clarification != bool(plan.clarification_reason):
        raise ValueError("comparison_plan_clarification_mismatch")
