from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ElectricalChange:
    before: float | None = None
    after: float | None = None
    difference: float | None = None
    change_percent: float | None = None
    change_ratio: float | None = None
    direction: str = "unknown"
    unit: str | None = None
    available: bool = False
    evidence_id: str | None = None


@dataclass(frozen=True)
class LearningObservation:
    source: str
    evidence_id: str
    quantity: str
    observation: str
    confidence: str
    field_display: str | None = None
    region: str | None = None
    numeric_evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LearningWarning:
    warning_type: str
    severity: str
    source: str
    affected_quantities: tuple[str, ...] = ()
    affected_regions: tuple[str, ...] = ()


@dataclass(frozen=True)
class LearningAnalysisContext:
    experiment: dict[str, Any]
    electrical_changes: dict[str, ElectricalChange]
    curve_observations: tuple[LearningObservation, ...] = ()
    field_observations: tuple[LearningObservation, ...] = ()
    validated_observations: tuple[dict[str, Any], ...] = ()
    warnings: tuple[LearningWarning, ...] = ()
    in_training_range: bool = False
    analysis_status: str = "insufficient"
    source_schema_versions: dict[str, str] = field(default_factory=dict)
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        json.dumps(data, ensure_ascii=False, allow_nan=False)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LearningAnalysisContext":
        if str(data.get("schema_version", "")) != "1.0":
            raise ValueError("unsupported_learning_analysis_schema")
        return cls(
            experiment=dict(data.get("experiment", {})),
            electrical_changes={
                str(name): ElectricalChange(**value)
                for name, value in data.get("electrical_changes", {}).items()
            },
            curve_observations=tuple(LearningObservation(**item) for item in data.get("curve_observations", [])),
            field_observations=tuple(LearningObservation(**item) for item in data.get("field_observations", [])),
            validated_observations=tuple(dict(item) for item in data.get("validated_observations", [])),
            warnings=tuple(
                LearningWarning(
                    warning_type=item["warning_type"],
                    severity=item["severity"],
                    source=item["source"],
                    affected_quantities=tuple(item.get("affected_quantities", [])),
                    affected_regions=tuple(item.get("affected_regions", [])),
                )
                for item in data.get("warnings", [])
            ),
            in_training_range=bool(data.get("in_training_range", False)),
            analysis_status=str(data.get("analysis_status", "insufficient")),
            source_schema_versions={
                str(name): str(value) for name, value in data.get("source_schema_versions", {}).items()
            },
            schema_version="1.0",
        )
