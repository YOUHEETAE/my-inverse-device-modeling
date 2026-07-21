from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Literal


AnalysisType = Literal["iv_curve_single", "iv_curve_comparison", "field_single", "field_comparison"]


def json_safe(value: Any) -> Any:
    """Convert numpy/Enum values and non-finite numbers to strict-JSON values."""
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "tolist") and not isinstance(value, (str, bytes)):
        return json_safe(value.tolist())
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float) or hasattr(value, "__float__"):
        number = float(value)
        return number if math.isfinite(number) else None
    return value


@dataclass(frozen=True)
class AnalysisPayload:
    analysis_id: str
    analysis_type: AnalysisType
    context: dict[str, Any]
    subjects: list[dict[str, Any]]
    comparisons: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    conclusions: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    output_policy: dict[str, Any] = field(default_factory=dict)
    interpretation: dict[str, Any] = field(default_factory=dict)
    schema_version: str = "3.0"

    def to_dict(self) -> dict[str, Any]:
        return json_safe(asdict(self))


@dataclass(frozen=True)
class ExplanationResult:
    descriptions: tuple[str, ...]
    comparisons: tuple[str, ...] = ()
    tradeoffs: tuple[str, ...] = ()
    cautions: tuple[str, ...] = ()
    provider: str = "unknown"
    model: str = "unknown"
    cached: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, provider: str, model: str, cached: bool = False) -> "ExplanationResult":
        from .safety import validate_provider_response
        clean = validate_provider_response(data)
        return cls(tuple(clean["descriptions"]), tuple(clean["comparisons"]), tuple(clean["tradeoffs"]), tuple(clean["cautions"]), provider, model, cached)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def display_text(self) -> str:
        sections = [("결과 설명", self.descriptions), ("비교", self.comparisons), ("Trade-off", self.tradeoffs), ("주의사항", self.cautions)]
        if self.provider == "external_llm":
            blocks = [title + "\n" + " ".join(lines) for title, lines in sections if lines]
        else:
            blocks = [title + "\n" + "\n".join(f"• {line}" for line in lines) for title, lines in sections if lines]
        source = f"{self.provider} / {self.model}" + (" / cached" if self.cached else "")
        return "\n\n".join(blocks) + f"\n\nSource: {source}"
