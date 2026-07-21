import json
import os

from backend.explanation.iv_renderer import render_tradeoff_sentence
from backend.explanation.payload_builders import build_payload
from backend.explanation.providers.config import ProviderMode, ProviderSettings
from backend.explanation.providers.external import ExternalLLMProvider
from backend.explanation.providers.mock import MockExplanationProvider
from backend.explanation.service import ExplanationService
from backend.explanation.selection import build_tradeoff_conclusions


def _metric(value, name, unit, preference):
    return {"value": value, "name": name, "unit": unit, "preference": preference}


def _curve(label, length, ion, ioff, dibl, ron):
    return {"label": label, "device_parameters": {"L": length, "T": 5, "B": 1e17, "SD": 1e20, "LDD": 1e18},
            "electrical_parameters": {
                "ion_ma_per_um": _metric(ion, "Ion", "mA/um", "higher_is_better"),
                "ioff_ma_per_um": _metric(ioff, "Ioff", "mA/um", "lower_is_better"),
                "dibl_gm_v_per_v": _metric(dibl, "DIBL", "V/V", "lower_is_better"),
                "ron_kohm_um": _metric(ron, "Ron", "kohm um", "lower_is_better")}}


def _channel_length_payload():
    baseline = _curve("Curve 1", 100, 1, .01, .1, 1)
    candidate = _curve("Curve 2", 120, .8, .005, .07, 1.3)
    changes = {key: {"baseline": baseline["electrical_parameters"][key]["value"],
                     "candidate": candidate["electrical_parameters"][key]["value"],
                     "unit": baseline["electrical_parameters"][key]["unit"]}
               for key in baseline["electrical_parameters"]}
    return build_payload(kind="iv_curve", context={}, items=[baseline, candidate],
                         legacy_comparisons=[{"electrical_parameter_changes": changes, "current_curve_changes": {}}], warnings=[])


def test_golden_a_channel_length_mock_end_to_end():
    payload = _channel_length_payload()
    comparison = payload.comparisons[0]
    assert comparison["declared_claim_level"] == "controlled_association"
    assert [item["label"] for item in payload.conclusions if item["conclusion_type"] == "tradeoff"] == ["short_channel_control_vs_drive_performance"]
    result = ExplanationService(MockExplanationProvider())._explain(payload)
    assert result.descriptions and result.comparisons and result.tradeoffs
    assert "Short-channel control" in result.tradeoffs[0] and "Drive performance" in result.tradeoffs[0]
    json.dumps({key: list(getattr(result, key)) for key in ("descriptions", "comparisons", "tradeoffs", "cautions")}, ensure_ascii=False, allow_nan=False)


def test_all_tradeoff_taxonomy_has_specific_mock_sentence():
    labels = {"short_channel_control_vs_drive_performance", "drive_current_vs_off_state_leakage", "gate_control_vs_oxide_field",
              "series_resistance_vs_drain_field", "current_spreading_vs_current_crowding", "drive_performance_vs_saturation_behavior",
              "field_reduction_vs_extension_resistance", "channel_inversion_vs_field_concentration"}
    for label in labels:
        sentence = render_tradeoff_sentence({"label": label})
        assert "Trade-off" in sentence and "서로 다른 성능 지표" not in sentence


def _comparison(parameter="oxide_thickness"):
    return {"comparison_id": "cmp_1_2", "changed_parameter_count": 1, "effective_claim_level": "controlled_association",
            "baseline_subject_id": "curve_1", "candidate_subject_id": "curve_2", "comparison_role": "primary_baseline_to_variant",
            "changed_parameters": [{"parameter": parameter}]}


def _selected(eid, *, quantity=None, evidence_type="metric_change", observation="increased", display=None, region=None, assessment="improved"):
    return {"evidence_id": eid, "evidence_type": evidence_type, "source_type": "curve_parameter_analyzer" if display is None else "field_spatial_analyzer",
            "subject_ids": ["curve_1", "curve_2"], "comparison_id": "cmp_1_2", "field_display": display, "region": region,
            "quantity": quantity or (display + "_magnitude" if display else "unknown"), "observation": observation, "assessment": assessment,
            "magnitude_class": "major", "confidence": "high", "importance_score": .8, "eligible_for_output": True,
            "selected_for_explanation": True, "suppression_reasons": [], "physical_group": "audit"}


def test_golden_b_tox_gate_control_vs_oxide_field():
    evidence = [_selected("gm", quantity="gm_max"),
                _selected("oxide", evidence_type="hotspot_strength_change", observation="strengthened", display="electric_field", region="oxide", assessment="degraded")]
    conclusions = build_tradeoff_conclusions([_comparison()], evidence)
    assert [item["label"] for item in conclusions] == ["gate_control_vs_oxide_field"]


def test_golden_c_ldd_field_reduction_vs_extension_resistance():
    evidence = [_selected("field", evidence_type="hotspot_strength_change", observation="weakened", display="electric_field", region="drain_side_ldd_near_surface"),
                _selected("ron", quantity="ron", observation="increased", assessment="degraded")]
    conclusions = build_tradeoff_conclusions([_comparison("ldd_doping")], evidence)
    assert [item["label"] for item in conclusions] == ["field_reduction_vs_extension_resistance"]


def test_golden_d_source_drain_series_resistance_vs_drain_field():
    evidence = [_selected("ron", quantity="ron", observation="decreased"),
                _selected("field", evidence_type="hotspot_strength_change", observation="strengthened", display="electric_field", region="drain_near_surface", assessment="degraded")]
    conclusions = build_tradeoff_conclusions([_comparison("source_drain_doping")], evidence)
    assert [item["label"] for item in conclusions] == ["series_resistance_vs_drain_field"]


def test_golden_j_partial_success_keeps_valid_drive_metrics():
    baseline = _curve("Curve 1", 100, 1, .01, .1, 1); candidate = _curve("Curve 2", 120, .8, .005, .07, 1.3)
    baseline["electrical_parameters"]["dibl_gm_v_per_v"]["value"] = None
    candidate["electrical_parameters"]["dibl_gm_v_per_v"]["value"] = None
    changes = {key: {"baseline": baseline["electrical_parameters"][key]["value"], "candidate": candidate["electrical_parameters"][key]["value"], "unit": baseline["electrical_parameters"][key]["unit"]}
               for key in ("ion_ma_per_um", "ron_kohm_um")}
    payload = build_payload(kind="iv_curve", context={}, items=[baseline, candidate],
                            legacy_comparisons=[{"electrical_parameter_changes": changes, "current_curve_changes": {}}],
                            warnings=["Curve 1: parameter_extraction_failed for dibl", "Curve 2: parameter_extraction_failed for dibl"])
    result = ExplanationService(MockExplanationProvider())._explain(payload)
    assert payload.context["analysis_status"] == "partial_success"
    assert any("Ion" in line or "Ron" in line for line in result.comparisons)


class InvalidExternal:
    name = "external_llm"; model = "fake-invalid"
    def generate(self, *_args):
        return {"descriptions": ["Payload에 없는 값은 0.75 V입니다."], "comparisons": [], "tradeoffs": ["새 Trade-off"], "cautions": []}


def test_golden_n_invalid_external_uses_mock_fallback():
    result = ExplanationService(InvalidExternal())._explain(_channel_length_payload())
    assert result.provider == "mock" and result.tradeoffs
    assert all("0.75" not in sentence for section in (result.descriptions, result.comparisons, result.tradeoffs, result.cautions) for sentence in section)


def test_golden_o_timeout_retries_once_then_falls_back():
    calls = []
    def timeout_transport(*_args): calls.append(1); raise TimeoutError
    os.environ["AUDIT_LLM_KEY"] = "secret"
    settings = ProviderSettings(ProviderMode.EXTERNAL, "fake", "AUDIT_LLM_KEY", "https://example.invalid/v1", .01, 1, .2)
    provider = ExternalLLMProvider(settings, timeout_transport)
    result = ExplanationService(provider)._explain(_channel_length_payload())
    del os.environ["AUDIT_LLM_KEY"]
    assert len(calls) == 2 and result.provider == "mock" and result.descriptions
