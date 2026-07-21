import json
from pathlib import Path

from backend.explanation.cache import JsonExplanationCache
from backend.explanation.safety import (build_safe_fallback_response,
    find_invalid_numeric_paths, sanitize_payload_for_json, validate_provider_response)
from backend.explanation.schemas import AnalysisPayload
from backend.explanation.service import ExplanationService
from backend.explanation.warnings import make_warning, render_warning_cautions


def payload():
    return AnalysisPayload("a", "iv_curve_single", {"mode": "single"}, [{"subject_id": "curve_1"}],
        evidence=[], warnings=[], output_policy={"max_cautions": 1, "max_total_sentences": 3, "minimum_importance_score": 0.35})


class BrokenProvider:
    name = "broken"; model = "broken-v1"
    def generate(self, *_args): raise RuntimeError("internal secret")


class BrokenFallback(BrokenProvider):
    name = "broken-fallback"


class InvalidProvider:
    name = "invalid"; model = "v1"
    def generate(self, *_args): return {"descriptions": [1], "comparisons": [], "tradeoffs": [], "cautions": [], "unknown": []}


def test_nested_nonfinite_is_null_and_suppresses_affected_evidence():
    raw = {"evidence": [{"evidence_id": "ev", "data": {"x": [float("nan"), float("inf")]}, "eligible_for_output": True}]}
    clean, warnings = sanitize_payload_for_json(raw)
    assert clean["evidence"][0]["data"]["x"] == [None, None]
    assert not clean["evidence"][0]["eligible_for_output"] and "invalid_data" in clean["evidence"][0]["suppression_reasons"]
    assert warnings[0]["warning_type"] == "invalid_numeric_value"
    json.dumps(clean, allow_nan=False)


def test_invalid_numeric_paths_and_strict_response_validation():
    assert find_invalid_numeric_paths({"x": float("nan")}) == ["$.x"]
    try: validate_provider_response({"descriptions": [1], "comparisons": [], "tradeoffs": [], "cautions": []})
    except ValueError: pass
    else: raise AssertionError("numeric provider text was accepted")


def test_provider_and_fallback_failure_returns_safe_json_without_exception_details():
    result = ExplanationService(BrokenProvider(), fallback_provider=BrokenFallback())._explain(payload())
    text = result.display_text()
    assert result.provider == "safe-fallback" and "internal secret" not in text
    assert result.descriptions and result.cautions


def test_invalid_provider_response_uses_mock_fallback():
    result = ExplanationService(InvalidProvider())._explain(payload())
    assert result.provider == "mock" and result.descriptions


def test_corrupt_cache_and_write_failure_are_nonfatal(tmp_path=Path(".test-missing") / "cache.json"):
    cache = JsonExplanationCache(tmp_path)
    cache._entries["bad"] = "legacy"
    assert cache.get("bad") is None


def test_warning_priority_and_safe_fallback_policy():
    warnings = [make_warning("low", "model_approximation", severity="info"), make_warning("high", "invalid_numeric_value", severity="high")]
    assert "유효하지 않은" in render_warning_cautions(warnings, 1)[0]
    response = build_safe_fallback_response("field_comparison", warnings, {"max_cautions": 1})
    assert set(response) == {"descriptions", "comparisons", "tradeoffs", "cautions"} and len(response["cautions"]) == 1
