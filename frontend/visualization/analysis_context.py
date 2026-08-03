from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from backend.explanation.comparison_planner import build_comparison_plan


_PARAMETER_KEYS = {
    "L": "channel_length_nm",
    "T": "oxide_thickness_nm",
    "B": "bulk_doping_cm3",
    "SD": "source_drain_doping_cm3",
    "LDD": "ldd_doping_cm3",
}
_PARAMETER_LABELS = {
    "channel_length": "L",
    "oxide_thickness": "Tox",
    "bulk_doping": "Bulk",
    "source_drain_doping": "S/D",
    "ldd_doping": "LDD",
}
_MODE_LABELS = {
    "single_characterization": ("SINGLE", "단일 조건"),
    "controlled_pair": ("PAIR", "통제 비교"),
    "compound_pair": ("COMPOUND", "복합 비교"),
    "controlled_sweep": ("SWEEP", "단일 변수 Sweep"),
    "mixed_group": ("GROUP", "혼합 실험군"),
}


@dataclass(frozen=True)
class AnalysisContextStatus:
    badge: str
    mode_label: str
    baseline_label: str
    scope_label: str
    representative_label: str = ""

    def display_text(self, *, include_representative: bool) -> str:
        parts = [
            f"{self.badge} · {self.mode_label}",
            f"기준: {self.baseline_label}",
            f"범위: {self.scope_label}",
        ]
        if include_representative and self.representative_label:
            parts.append(f"대표 Field: {self.representative_label}")
        return " | ".join(parts)


def ordered_analysis_indices(
    selected_indices: Iterable[int],
    preferred_baseline_index: int | None,
) -> tuple[int, ...]:
    selected = tuple(sorted(set(selected_indices)))
    if not selected:
        return ()
    baseline = (
        preferred_baseline_index
        if preferred_baseline_index in selected
        else selected[0]
    )
    return (baseline, *(index for index in selected if index != baseline))


def _subjects(
    ordered_indices: tuple[int, ...],
    configs: list[dict[str, str]],
) -> list[dict]:
    subjects = []
    for position, index in enumerate(ordered_indices, start=1):
        config = configs[index]
        subjects.append({
            "subject_id": f"curve_{position}",
            "display_name": f"Curve {index + 1}",
            "device_parameters": {
                output_key: float(config[input_key])
                for input_key, output_key in _PARAMETER_KEYS.items()
            },
        })
    return subjects


def build_analysis_context_status(
    selected_indices: Iterable[int],
    configs: list[dict[str, str]],
    *,
    preferred_baseline_index: int | None = None,
) -> AnalysisContextStatus | None:
    ordered = ordered_analysis_indices(
        selected_indices, preferred_baseline_index,
    )
    if not ordered:
        return None
    subjects = _subjects(ordered, configs)
    plan = build_comparison_plan(subjects)
    badge, mode_label = _MODE_LABELS[plan.analysis_mode]
    baseline = (
        next(
            (
                str(item["display_name"])
                for item in subjects
                if item["subject_id"] == plan.baseline_subject_id
            ),
            str(subjects[0]["display_name"]),
        )
        if len(subjects) > 1
        else str(subjects[0]["display_name"])
    )
    names = {
        str(item["subject_id"]): str(item["display_name"])
        for item in subjects
    }
    if plan.sweep_parameter:
        unit = (
            "nm"
            if plan.sweep_parameter in {"channel_length", "oxide_thickness"}
            else "cm⁻³"
        )
        values = " → ".join(f"{value:g}" for value in plan.sweep_values)
        scope = (
            f"{_PARAMETER_LABELS[plan.sweep_parameter]} "
            f"{values} {unit} ({len(subjects)}개)"
        )
    elif plan.changed_parameters:
        parameters = ", ".join(
            _PARAMETER_LABELS.get(value, value)
            for value in plan.changed_parameters
        )
        scope = f"{len(subjects)}개 조건 · 변화 변수: {parameters}"
    else:
        scope = (
            f"{len(subjects)}개 동일 조건"
            if len(subjects) > 1 else "현재 조건 1개"
        )
    representative = " ↔ ".join(
        names[value] for value in plan.representative_subject_ids
    )
    return AnalysisContextStatus(
        badge=badge,
        mode_label=mode_label,
        baseline_label=baseline,
        scope_label=scope,
        representative_label=representative,
    )
