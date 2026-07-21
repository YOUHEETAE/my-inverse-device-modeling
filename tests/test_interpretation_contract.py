import json
from pathlib import Path

from backend.explanation.interpretation_contract import (
    build_interpretation_scaffold,
    validate_interpretation_contract,
)
from tests.test_final_audit import _channel_length_payload


def test_curve_contract_is_present_and_strict_json():
    payload = _channel_length_payload()
    contract = payload.interpretation
    assert contract["analysis_family"] == "curve"
    assert contract["status"] == "complete"
    assert contract["performance_summaries"]
    assert contract["parameter_interactions"] == []
    json.dumps(payload.to_dict(), ensure_ascii=False, allow_nan=False)


def test_field_contract_has_geometry_and_quality_destinations():
    contract = build_interpretation_scaffold("field_comparison")
    validate_interpretation_contract(contract, "field_comparison")
    assert contract["analysis_family"] == "field"
    assert contract["geometry_context"] is None
    assert contract["analysis_quality"] == {}
    assert contract["field_specific_conclusions"] == []


def test_contract_rejects_family_mismatch():
    contract = build_interpretation_scaffold("iv_curve_comparison")
    try:
        validate_interpretation_contract(contract, "field_comparison")
    except ValueError:
        return
    raise AssertionError("family mismatch must be rejected")


def test_phase1_baseline_is_frozen_and_covers_required_cases():
    path = Path(__file__).parent / "baselines" / "phase1_explanation_baseline.json"
    baseline = json.loads(path.read_text(encoding="utf-8"))
    assert baseline["baseline_version"] == "phase1-v1"
    required = {
        "curve_single_default", "curve_l1200_t22_reinforcing",
        "curve_l1200_t17_competing", "curve_three_dopings_doubled",
        "curve_three_variants", "field_potential_l1200_t22",
        "field_electric_field_l1200_t22",
    }
    assert set(baseline["cases"]) == required
    for case in baseline["cases"].values():
        assert case["payload"]["schema_version"] == "3.0"
        assert set(case["mock_response"]) == {"descriptions", "comparisons", "tradeoffs", "cautions"}
