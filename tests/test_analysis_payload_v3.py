import json

import numpy as np

from backend.explanation.payload_builders import build_payload
from backend.explanation.schemas import json_safe


def item(label, *, L=100.0, T=5.0):
    return {"label": label, "device_parameters": {"L": L, "T": T, "B": 1e17, "SD": 1e20, "LDD": 1e18}, "value": np.float64(1.0)}


def test_single_curve_payload_is_strict_json():
    payload = build_payload(kind="iv_curve", context={"curve_kinds": ["idvd", "idvg"]}, items=[item("Curve 1")], legacy_comparisons=[], warnings=[])
    data = payload.to_dict()
    assert data["schema_version"] == "3.0"
    assert data["analysis_type"] == "iv_curve_single"
    assert data["subjects"][0]["role"] == "single_subject"
    assert data["comparisons"] == []
    json.dumps(data, allow_nan=False)


def test_one_parameter_comparison_is_controlled():
    payload = build_payload(kind="iv_curve", context={}, items=[item("Curve 1"), item("Curve 2", L=200.0)], legacy_comparisons=[{}], warnings=[])
    comparison = payload.comparisons[0]
    assert comparison["changed_parameter_count"] == 1
    assert comparison["changed_parameters"][0]["parameter"] == "channel_length"
    assert comparison["declared_claim_level"] == "controlled_association"
    assert comparison["effective_claim_level"] == "descriptive_only"
    assert comparison["changed_parameters"][0]["percent_difference"] == 100.0


def test_three_curves_use_selected_pair_order():
    payload = build_payload(kind="iv_curve", context={}, items=[item("1"), item("2", L=200), item("3", T=6)], legacy_comparisons=[{}, {}, {}], warnings=[])
    assert [c["comparison_id"] for c in payload.comparisons] == ["cmp_1_2", "cmp_1_3", "cmp_2_3"]
    assert [c["comparison_order"] for c in payload.comparisons] == [1, 2, 3]
    assert payload.comparisons[-1]["comparison_role"] == "variant_to_variant"
    assert payload.comparisons[0]["subject_ids"] == ["curve_1", "curve_2"]


def test_multi_parameter_change_adds_warning():
    payload = build_payload(kind="field", context={"display": "electric_field"}, items=[item("1"), item("2", L=200, T=6)], legacy_comparisons=[{}], warnings=[])
    assert payload.analysis_type == "field_comparison"
    assert payload.comparisons[0]["causal_claim_level"] == "multi_parameter_association"
    assert any(w["warning_type"] == "multiple_parameter_change" for w in payload.warnings)


def test_single_field_context_and_policy():
    context = {"display": "potential", "scale": "auto", "range_mode": "robust_1_99", "fixed_bias": {"vg_v": 3.0, "vd_v": 3.0}}
    payload = build_payload(kind="field", context=context, items=[item("Curve 1")], legacy_comparisons=[], warnings=[])
    assert payload.analysis_type == "field_single"
    assert payload.context["comparison_strategy"] == "none"
    assert payload.output_policy["number_display_policy"] == "qualitative_only"


def test_single_field_selects_robust_regional_evidence():
    field_item = item("Curve 1")
    field_item["specialized_metrics"] = {
        "regions": {
            "Channel near-surface": {
                "electric_field_V_per_cm": {"p99": 12.0},
            },
            "Deep bulk": {
                "electric_field_V_per_cm": {"p99": 3.0},
            },
        }
    }
    payload = build_payload(
        kind="field",
        context={"display": "potential", "fixed_bias": {"vg_v": 3.0, "vd_v": 3.0}},
        items=[field_item],
        legacy_comparisons=[],
        warnings=[],
    )
    selected = [item for item in payload.evidence if item["selected_for_explanation"]]
    assert len(selected) == 1
    assert selected[0]["evidence_type"] == "regional_level"
    assert selected[0]["region"] == "channel_near_surface"


def test_field_pair_uses_selected_pair_strategy():
    payload = build_payload(kind="field", context={"display": "electric_field", "shared_color_scale": True}, items=[item("1"), item("2", L=200)], legacy_comparisons=[{}], warnings=[])
    assert payload.analysis_type == "field_comparison"
    assert payload.context["comparison_strategy"] == "selected_pair"
    assert payload.context["shared_color_scale"] is True


def test_non_finite_values_become_null():
    value = item("Curve 1")
    value["value"] = np.asarray([np.nan, np.inf, np.int64(3)])
    data = build_payload(kind="iv_curve", context={}, items=[value], legacy_comparisons=[], warnings=[]).to_dict()
    assert json_safe(value["value"]) == [None, None, 3]
    json.dumps(data, allow_nan=False)


def test_analysis_status_reports_success_partial_or_insufficient():
    data = build_payload(kind="iv_curve", context={}, items=[item("Curve 1")], legacy_comparisons=[], warnings=[]).to_dict()
    assert data["context"]["analysis_status"] in {"success", "partial_success", "insufficient_data"}
    assert data["context"]["valid_evidence_count"] + data["context"]["suppressed_evidence_count"] == len(data["evidence"])
