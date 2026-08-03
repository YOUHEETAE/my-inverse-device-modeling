from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from backend.explanation.schemas import AnalysisPayload

from .analysis_schemas import (
    ElectricalChange,
    LearningAnalysisContext,
    LearningObservation,
    LearningWarning,
)
from .validation import (
    ConditionValidationError,
    ExperimentComparison,
    compare_experiment_conditions,
    validate_model_conditions,
)


ELECTRICAL_QUANTITIES = {
    "vth_low": "vth_at_vd_0_05",
    "vth_high": "vth_at_vd_1_5",
    "ion": "ion",
    "ioff": "ioff",
    "ion_ioff_ratio": "ion_ioff_ratio",
    "ss": "ss",
    "dibl": "dibl",
    "gm_max": "gm_max",
    "gds": "gds",
    "ron": "ron",
    "lambda_clm": "lambda_clm",
}


def _payload_dict(payload: AnalysisPayload | Mapping[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {}
    if isinstance(payload, AnalysisPayload):
        return payload.to_dict()
    return dict(payload)


def _finite(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _direction(value: Any) -> str:
    normalized = str(value or "").lower()
    return {
        "increased": "increase",
        "decreased": "decrease",
        "strengthened": "increase",
        "weakened": "decrease",
        "negligible": "stable",
        "unchanged": "stable",
        "no_meaningful_difference": "stable",
    }.get(normalized, normalized if normalized in {"increase", "decrease", "stable"} else "unknown")


def _experiment(
    baseline: Mapping[str, float],
    comparison: Mapping[str, float],
) -> tuple[dict[str, Any], bool]:
    before = {str(key): float(value) for key, value in baseline.items()}
    after = {str(key): float(value) for key, value in comparison.items()}
    try:
        validated_before = validate_model_conditions(before, require_supported_value=True)
        validated_after = validate_model_conditions(after, require_supported_value=True)
        compared = compare_experiment_conditions(validated_before, validated_after)
        in_range = True
    except ConditionValidationError:
        changed = tuple(name for name in before.keys() & after.keys() if before[name] != after[name])
        fixed = tuple(name for name in before.keys() & after.keys() if before[name] == after[name])
        compared = ExperimentComparison(changed, fixed)
        in_range = False
    changed_parameter = compared.changed_parameters[0] if len(compared.changed_parameters) == 1 else None
    return {
        "changed_parameter": changed_parameter,
        "changed_parameters": list(compared.changed_parameters),
        "before": before.get(changed_parameter) if changed_parameter else None,
        "after": after.get(changed_parameter) if changed_parameter else None,
        "baseline_conditions": before,
        "comparison_conditions": after,
        "fixed_parameters": {name: before[name] for name in compared.fixed_parameters},
    }, in_range


def _electrical_changes(curve: dict[str, Any]) -> dict[str, ElectricalChange]:
    changes_by_quantity = {
        str(item.get("quantity")): item
        for item in curve.get("evidence", [])
        if item.get("evidence_type") == "metric_change"
        and item.get("comparison_id")
        and item.get("eligible_for_output", False)
    }
    normalized: dict[str, ElectricalChange] = {}
    for output_name, quantity in ELECTRICAL_QUANTITIES.items():
        evidence = changes_by_quantity.get(quantity)
        if not evidence:
            normalized[output_name] = ElectricalChange()
            continue
        data = evidence.get("data", {})
        before = _finite(data.get("baseline"))
        after = _finite(data.get("candidate"))
        ratio = after / before if before not in {None, 0.0} and after is not None else None
        normalized[output_name] = ElectricalChange(
            before=before,
            after=after,
            difference=_finite(data.get("absolute_difference")),
            change_percent=_finite(data.get("percent_difference")),
            change_ratio=_finite(ratio),
            direction=_direction(evidence.get("observation")),
            unit=str(data["unit"]) if data.get("unit") else None,
            available=before is not None and after is not None,
            evidence_id=(
                str(evidence["evidence_id"])
                if evidence.get("evidence_id")
                else f"metric:{output_name}"
            ),
        )
    return normalized


def _safe_numeric_evidence(item: Mapping[str, Any]) -> dict[str, Any]:
    policy = item.get("numeric_display") or {}
    if not policy.get("allowed", False):
        return {}
    data = item.get("data") or {}
    clean = {}
    for name in policy.get("preferred_fields", []):
        value = data.get(name)
        if isinstance(value, (str, bool)) or _finite(value) is not None:
            clean[str(name)] = value
    return clean


def _observations(payload: dict[str, Any], source: str) -> tuple[LearningObservation, ...]:
    observations = []
    for item in payload.get("evidence", []):
        if not item.get("eligible_for_output", False) or not item.get("selected_for_explanation", False):
            continue
        evidence_type = str(item.get("evidence_type", ""))
        if source == "curve" and evidence_type not in {"curve_point_change", "curve_shape_change"}:
            continue
        if source == "field" and not item.get("field_display"):
            continue
        observations.append(LearningObservation(
            source=source,
            evidence_id=str(item.get("evidence_id", "")),
            quantity=str(item.get("quantity", "unknown")),
            observation=_direction(item.get("observation")),
            confidence=str(item.get("confidence", "unknown")),
            field_display=str(item["field_display"]) if item.get("field_display") else None,
            region=str(item["region"]) if item.get("region") else None,
            numeric_evidence=_safe_numeric_evidence(item),
        ))
    return tuple(observations)


def _validated_conclusions(payload: dict[str, Any], source: str) -> list[dict[str, Any]]:
    conclusions = []
    for item in payload.get("conclusions", []):
        if not item.get("eligible_for_output", False):
            continue
        supporting_ids = list(item.get("supporting_evidence_ids", []))
        if not supporting_ids:
            supporting_ids = [
                *item.get("positive_evidence_ids", []),
                *item.get("negative_evidence_ids", []),
                *item.get("evidence_ids", []),
            ]
        normalized = {
            "source": source,
            "conclusion_id": item.get("conclusion_id"),
            "conclusion_type": item.get("conclusion_type"),
            "changed_parameters": list(item.get("changed_parameters", [])),
            "principle_ids": list(item.get("principle_ids", [])),
            "supporting_evidence_ids": supporting_ids,
            "effective_claim_level": item.get("effective_claim_level"),
        }
        for name in (
            "label", "assessment", "relationship", "result_pattern",
            "positive_target", "negative_target", "parameter", "direction",
        ):
            if item.get(name) is not None:
                normalized[name] = item[name]
        conclusions.append(normalized)
    for item in (payload.get("interpretation") or {}).get("field_specific_conclusions", []):
        conclusions.append({
            "source": source,
            "conclusion_id": item.get("conclusion_id"),
            "conclusion_type": item.get("concept"),
            "assessment": item.get("assessment"),
            "supporting_evidence_ids": list(item.get("evidence_ids", [])),
            "spatial_feature_ids": list(item.get("spatial_feature_ids", [])),
        })
    return conclusions


def _warnings(payload: dict[str, Any], source: str) -> list[LearningWarning]:
    return [
        LearningWarning(
            warning_type=str(item.get("warning_type", "unknown")),
            severity=str(item.get("severity", "unknown")),
            source=source,
            affected_quantities=tuple(str(value) for value in item.get("affected_quantities", [])),
            affected_regions=tuple(str(value) for value in item.get("affected_regions", [])),
        )
        for item in payload.get("warnings", [])
    ]


class LearningAnalysisAdapter:
    """Normalize existing analysis payloads without depending on analyzer internals."""

    def normalize(
        self,
        *,
        baseline_conditions: Mapping[str, float],
        comparison_conditions: Mapping[str, float],
        curve_analysis: AnalysisPayload | Mapping[str, Any] | None,
        field_analyses: Mapping[str, AnalysisPayload | Mapping[str, Any] | None] | None = None,
    ) -> LearningAnalysisContext:
        curve = _payload_dict(curve_analysis)
        fields = {name: _payload_dict(payload) for name, payload in (field_analyses or {}).items()}
        experiment, in_range = _experiment(baseline_conditions, comparison_conditions)

        curve_observations = _observations(curve, "curve")
        field_observations = tuple(
            observation
            for payload in fields.values()
            for observation in _observations(payload, "field")
        )
        validated = _validated_conclusions(curve, "curve")
        warnings = _warnings(curve, "curve")
        source_versions = {"curve": str(curve.get("schema_version", "missing"))}
        statuses = [str((curve.get("context") or {}).get("analysis_status", "insufficient_data"))]
        for display, payload in fields.items():
            validated.extend(_validated_conclusions(payload, f"field:{display}"))
            warnings.extend(_warnings(payload, f"field:{display}"))
            source_versions[f"field:{display}"] = str(payload.get("schema_version", "missing"))
            statuses.append(str((payload.get("context") or {}).get("analysis_status", "insufficient_data")))

        warning_keys = set()
        deduplicated_warnings = []
        for warning in warnings:
            key = (warning.warning_type, warning.severity, warning.source, warning.affected_quantities, warning.affected_regions)
            if key not in warning_keys:
                warning_keys.add(key)
                deduplicated_warnings.append(warning)
        if any(warning.warning_type == "extrapolation" for warning in deduplicated_warnings):
            in_range = False

        electrical_changes = _electrical_changes(curve)
        available_count = sum(change.available for change in electrical_changes.values())
        if available_count == 0:
            status = "insufficient"
        elif any(value in {"partial_success", "insufficient_data"} for value in statuses):
            status = "partial"
        else:
            status = "complete"
        return LearningAnalysisContext(
            experiment=experiment,
            electrical_changes=electrical_changes,
            curve_observations=curve_observations,
            field_observations=field_observations,
            validated_observations=tuple(validated),
            warnings=tuple(deduplicated_warnings),
            in_training_range=in_range,
            analysis_status=status,
            source_schema_versions=source_versions,
        )
