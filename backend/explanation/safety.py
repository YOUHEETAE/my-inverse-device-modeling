from __future__ import annotations

import math
import re
from enum import Enum
from typing import Any

from backend.answer_contract import normalize_public_text, validate_public_answer_text

from .warnings import make_warning, render_warning_cautions

RESPONSE_KEYS = ("descriptions", "comparisons", "tradeoffs", "cautions")
FORBIDDEN_CAUSAL_TERMS = ("증명", "입증", "유일한 원인", "반드시 유발")


def find_invalid_numeric_paths(value: Any, path: str = "$") -> list[str]:
    if isinstance(value, dict):
        return [found for key, item in value.items() for found in find_invalid_numeric_paths(item, f"{path}.{key}")]
    if isinstance(value, (list, tuple)) or (hasattr(value, "tolist") and not isinstance(value, (str, bytes))):
        sequence = value.tolist() if hasattr(value, "tolist") else value
        return [found for index, item in enumerate(sequence) for found in find_invalid_numeric_paths(item, f"{path}[{index}]")]
    if isinstance(value, float) or (not isinstance(value, (str, bytes, bool, type(None), int, Enum)) and hasattr(value, "__float__")):
        try: return [] if math.isfinite(float(value)) else [path]
        except (TypeError, ValueError, OverflowError): return []
    return []


def sanitize_json_value(value: Any) -> Any:
    if isinstance(value, Enum): return value.value
    if hasattr(value, "tolist") and not isinstance(value, (str, bytes)): return sanitize_json_value(value.tolist())
    if isinstance(value, dict): return {str(key): sanitize_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)): return [sanitize_json_value(item) for item in value]
    if isinstance(value, float) or (not isinstance(value, (str, bytes, bool, type(None), int)) and hasattr(value, "__float__")):
        try:
            number = float(value); return number if math.isfinite(number) else None
        except (TypeError, ValueError, OverflowError): return value
    return value


def sanitize_payload_for_json(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    invalid = find_invalid_numeric_paths(payload); clean = sanitize_json_value(payload)
    affected = []
    for index, item in enumerate(clean.get("evidence", [])):
        prefix = f"$.evidence[{index}]"
        if any(path.startswith(prefix) for path in invalid):
            item["eligible_for_output"] = False
            item["suppression_reasons"] = list(dict.fromkeys([*item.get("suppression_reasons", []), "invalid_data"]))
            affected.append(item.get("evidence_id"))
    warnings = []
    if invalid:
        warnings.append(make_warning("warn_invalid_numeric", "invalid_numeric_value", severity="high",
            fallback_action="omit_affected_evidence_and_include_caution", affected_evidence_ids=[x for x in affected if x],
            details={"invalid_paths": invalid}))
    clean.setdefault("warnings", []).extend(warnings)
    return clean, warnings


def validate_provider_response(data: Any) -> dict[str, list[str]]:
    if not isinstance(data, dict) or set(data) != set(RESPONSE_KEYS): raise ValueError("Invalid provider response keys.")
    result = {}
    for key in RESPONSE_KEYS:
        if not isinstance(data[key], list) or any(not isinstance(item, str) for item in data[key]): raise ValueError(f"{key} must be list[str].")
        result[key] = list(dict.fromkeys(
            clean
            for item in data[key]
            if (clean := normalize_public_text(item))
        ))
    if not result["descriptions"]: raise ValueError("Explanation response is missing descriptions.")
    validate_public_answer_text(
        " ".join(sentence for values in result.values() for sentence in values)
    )
    return result


def validate_grounded_response(response: dict[str, list[str]], payload: dict[str, Any]) -> None:
    text = " ".join(sentence for values in response.values() for sentence in values)
    if any(term in text for term in FORBIDDEN_CAUSAL_TERMS): raise ValueError("forbidden_causal_wording")
    if response["tradeoffs"] and not _has_grounded_tradeoff(payload):
        raise ValueError("ungrounded_tradeoff")
    if payload.get("analysis_type", "").startswith("field_"):
        forbidden = ("percentile", "p99", "threshold", "coordinate")
        if any(term.lower() in text.lower() for term in forbidden): raise ValueError("field_internal_statistics_exposed")
    allowed = _allowed_numeric_values(payload)
    for token in re.findall(r"(?<![A-Za-z_])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", text):
        number = float(token)
        if not any(math.isclose(number, value, rel_tol=.015, abs_tol=.015) for value in allowed):
            raise ValueError("ungrounded_numeric_value")
    important_warnings = [item for item in payload.get("warnings", []) if item.get("eligible_for_output", True) and item.get("severity") in {"high", "critical"}]
    if important_warnings and not response["cautions"]: raise ValueError("missing_required_caution")


def salvage_grounded_response(response: dict[str, list[str]], payload: dict[str, Any]) -> dict[str, list[str]]:
    """Keep individually grounded LLM sentences instead of discarding the whole response."""
    allowed = _allowed_numeric_values(payload)
    has_tradeoff = _has_grounded_tradeoff(payload)
    field_result = payload.get("analysis_type", "").startswith("field_")
    field_forbidden = ("percentile", "p99", "threshold", "coordinate")

    def grounded_sentence(sentence: str) -> bool:
        if any(term in sentence for term in FORBIDDEN_CAUSAL_TERMS):
            return False
        if field_result and any(term in sentence.lower() for term in field_forbidden):
            return False
        for token in re.findall(r"(?<![A-Za-z_])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", sentence):
            number = float(token)
            if not any(math.isclose(number, value, rel_tol=.015, abs_tol=.015) for value in allowed):
                return False
        return True

    clean = {key: [sentence for sentence in response[key] if grounded_sentence(sentence)] for key in RESPONSE_KEYS}
    if not has_tradeoff:
        clean["tradeoffs"] = []
    important_warnings = [item for item in payload.get("warnings", []) if item.get("eligible_for_output", True)
                          and item.get("severity") in {"high", "critical"}]
    if important_warnings and not clean["cautions"]:
        clean["cautions"] = ["입력 경고가 포함된 결과이므로 해석 범위와 모델 한계를 함께 확인해야 합니다."]
    if not clean["descriptions"]:
        raise ValueError("no_grounded_description_after_salvage")
    validate_grounded_response(clean, payload)
    return clean


def _has_grounded_tradeoff(payload: dict[str, Any]) -> bool:
    legacy = any(item.get("conclusion_type") == "tradeoff" and item.get("eligible_for_output", True)
                 for item in payload.get("conclusions", []))
    structured = bool((payload.get("interpretation") or {}).get("observed_tradeoffs"))
    return legacy or structured


def _allowed_numeric_values(payload: dict[str, Any]) -> set[float]:
    values: set[float] = {-3.0, -2.0, -1.0, *(float(index) for index in range(0, len(payload.get("subjects", [])) + 1))}
    def collect(value: Any) -> None:
        if isinstance(value, dict):
            for item in value.values(): collect(item)
        elif isinstance(value, list):
            for item in value: collect(item)
        elif isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)): values.add(float(value))
    for subject in payload.get("subjects", []): collect(subject.get("device_parameters", {}))
    collect(payload.get("context", {}).get("fixed_bias", {}))
    for comparison in payload.get("comparisons", []):
        for change in comparison.get("changed_parameters", []):
            for field in ("baseline", "candidate", "absolute_difference", "percent_difference"):
                collect(change.get(field))
    for evidence in payload.get("evidence", []):
        display = evidence.get("numeric_display", {})
        if display.get("allowed"):
            data = evidence.get("data", {})
            for field in display.get("preferred_fields", []): collect(data.get(field))
    # Renderers commonly express a signed payload value as a positive magnitude
    # plus a direction word (for example, -20% as "20% 감소").
    return values | {abs(value) for value in values}


def enforce_response_policy(response: dict[str, list[str]], policy: dict[str, Any]) -> dict[str, list[str]]:
    limits = {"descriptions": int(policy.get("max_descriptions", len(response["descriptions"]))),
              "comparisons": int(policy.get("max_comparisons", len(response["comparisons"]))),
              "tradeoffs": int(policy.get("max_tradeoffs", len(response["tradeoffs"]))),
              "cautions": int(policy.get("max_cautions", len(response["cautions"])))}
    result = {key: response[key][:limits[key]] for key in RESPONSE_KEYS}
    remaining = int(policy.get("max_total_sentences", sum(map(len, result.values()))))
    for key in RESPONSE_KEYS:
        result[key] = result[key][:remaining]; remaining -= len(result[key])
    if not result["descriptions"]: raise ValueError("output_policy_removed_descriptions")
    return result


def build_safe_fallback_response(analysis_type: str, warnings: list[dict[str, Any]] | None = None, output_policy: dict[str, Any] | None = None) -> dict[str, list[str]]:
    family = "I–V" if analysis_type.startswith("iv_curve") else "Field"
    caution_limit = int((output_policy or {}).get("max_cautions", 1))
    cautions = render_warning_cautions(warnings or [], caution_limit)
    if not cautions: cautions = [f"입력 {family} 데이터와 분석 조건을 확인해 주세요."][:caution_limit]
    return {"descriptions": [f"선택된 결과에서 유효한 {family} 분석 정보를 충분히 확보하지 못했습니다."], "comparisons": [], "tradeoffs": [], "cautions": cautions}
