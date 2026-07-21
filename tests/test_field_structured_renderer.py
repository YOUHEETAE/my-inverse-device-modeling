from __future__ import annotations

from backend.explanation.field_analyzer import build_field_payload
from backend.explanation.field_renderer import render_field_explanation
from backend.explanation.providers.mock import MockExplanationProvider
from tests.test_field_interpretation import _predicted_output


def _outputs():
    return [("Curve 1", _predicted_output(200, 20)), ("Curve 2", _predicted_output(1200, 22, 0.8))]


def test_structured_potential_mock_has_condition_principles_observation_and_limit() -> None:
    payload = build_field_payload(_outputs(), "Potential", "Auto", "Robust 1-99%").to_dict()
    response = render_field_explanation(payload)
    assert "Channel length 200→1200 nm" in response["descriptions"][0]
    assert "Oxide thickness(Tox) 20→22 nm" in response["descriptions"][0]
    assert "Drain 영향" in response["descriptions"][1]
    assert any("Potential gradient" in item for item in response["comparisons"])
    assert "개별 기여도" in response["cautions"][0]
    assert "TCAD 검증" in response["cautions"][0]


def test_structured_electric_field_groups_regions_and_keeps_reliability_limit() -> None:
    payload = build_field_payload(_outputs(), "Electric field", "Auto", "Robust 1-99%").to_dict()
    response = render_field_explanation(payload)
    assert any("Electric field concentration" in item for item in response["comparisons"])
    assert len(response["comparisons"]) <= payload["output_policy"]["max_comparisons"]
    assert "breakdown" in response["cautions"][0]
    assert "prediction" in response["cautions"][0]


def test_structured_single_field_uses_named_regions_without_comparative_claim() -> None:
    payload = build_field_payload(_outputs()[:1], "Electron density", "Auto", "Robust 1-99%").to_dict()
    response = render_field_explanation(payload)
    assert "named region" in response["descriptions"][0]
    assert "상대적으로 큰 공간 분포" in response["descriptions"][1]
    assert response["comparisons"] == []
    assert "terminal current" in response["cautions"][0]


def test_mock_model_version_invalidates_legacy_cached_text() -> None:
    assert MockExplanationProvider.model == "deterministic-interpretation-v8"
