from __future__ import annotations

from backend.explanation.field_analyzer import build_field_payload
from backend.explanation.field_renderer import (
    _structured_energy_band_conclusions,
    render_field_explanation,
)
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
    assert MockExplanationProvider.model == "deterministic-interpretation-v12"


def test_structured_energy_band_names_cut_location_and_barrier_meaning() -> None:
    lines = _structured_energy_band_conclusions(
        [{
            "concept": "channel_entry_barrier",
            "assessment": "raised",
            "region": "channel_near_surface",
        }],
        "Curve 2",
    )
    text = " ".join(lines)
    assert "Horizontal Source-to-Channel cut" in text
    assert "Channel barrier가 Channel near-surface에서" in text
    assert "Carrier가 Channel에 주입될 때 넘어야 하는 상대적 에너지 장벽" in text


def test_single_energy_band_explains_horizontal_and_vertical_extractions() -> None:
    payload = build_field_payload(
        _outputs()[:1],
        "Energy band (1D)",
        "Auto",
        "Robust 1-99%",
    ).to_dict()
    response = render_field_explanation(payload)
    output = " ".join(sum(response.values(), []))
    assert "유효한 공간 분석 결과를 충분히 확보하지 못했습니다" not in output
    assert "Source plateau" in output
    assert "source-edge·center·drain-edge" in output
    assert "Vertical Gate-Oxide-Bulk cut" in output
    assert "surface band" in output and "Deep bulk" in output


def test_energy_band_comparison_keeps_barrier_bending_and_slope() -> None:
    outputs = [
        ("Curve 1", _predicted_output(700, 16)),
        ("Curve 2", _predicted_output(700, 16, 0.8)),
    ]
    payload = build_field_payload(
        outputs,
        "Energy band (1D)",
        "Auto",
        "Robust 1-99%",
    )
    quantities = {item["quantity"] for item in payload.evidence}
    assert {
        "channel_entry_barrier",
        "vertical_band_bending",
        "channel_band_slope",
    }.issubset(quantities)
    response = render_field_explanation(payload.to_dict())
    output = " ".join(sum(response.values(), []))
    assert "Source plateau" in output
    assert "surface와 Deep bulk" in output
    assert "Source-side에서 Drain-side" in output


def test_three_field_maps_analyze_full_sweep_and_display_endpoint_pair() -> None:
    outputs = [
        ("Curve 1", _predicted_output(700, 20, 1.0)),
        ("Curve 2", _predicted_output(500, 20, 0.9)),
        ("Curve 3", _predicted_output(350, 20, 0.8)),
    ]
    payload = build_field_payload(
        outputs,
        "Electric field",
        "Auto",
        "Robust 1-99%",
    ).to_dict()
    plan = payload["comparison_plan"]
    assert len(payload["subjects"]) == 3
    assert len(payload["comparisons"]) == 3
    assert plan["analysis_mode"] == "controlled_sweep"
    assert plan["representative_subject_ids"] == [
        "curve_3", "curve_1",
    ]
    assert payload["context"]["comparison_strategy"] == (
        "all_pairwise_with_representative_display"
    )
    assert payload["context"]["shared_color_scale"] is True
    assert payload["interpretation"]["multi_condition_trends"]

    response = render_field_explanation(payload)
    text = " ".join(sum(response.values(), []))
    assert "3개 조건" in text
    assert "Channel length sweep 350→500→700" in text
    assert "Curve 3와 Curve 1" in text
    assert "대표 2개 Map" in text
    assert "전체 추세" in text


def test_three_mixed_field_maps_keep_all_pairs_but_avoid_global_trend() -> None:
    outputs = [
        ("Curve 1", _predicted_output(700, 20, 1.0)),
        ("Curve 2", _predicted_output(500, 20, 0.9)),
        ("Curve 3", _predicted_output(700, 10, 0.8)),
    ]
    payload = build_field_payload(
        outputs,
        "Potential",
        "Auto",
        "Robust 1-99%",
    ).to_dict()
    assert payload["comparison_plan"]["analysis_mode"] == "mixed_group"
    assert len(payload["comparisons"]) == 3
    assert payload["interpretation"]["multi_condition_trends"] == []
    response = render_field_explanation(payload)
    text = " ".join(sum(response.values(), []))
    assert "모든 pair를 분석" in text
    assert "controlled pair" in text
    assert "나머지 조건도 분석 범위에는 포함" in text


def test_three_energy_bands_report_barrier_slope_and_bending_trends() -> None:
    outputs = [
        ("Curve 1", _predicted_output(700, 20, 1.0)),
        ("Curve 2", _predicted_output(500, 20, 0.9)),
        ("Curve 3", _predicted_output(350, 20, 0.8)),
    ]
    payload = build_field_payload(
        outputs,
        "Energy band (1D)",
        "Auto",
        "Robust 1-99%",
    ).to_dict()
    quantities = {
        item["quantity"]
        for item in payload["interpretation"]["multi_condition_trends"]
    }
    assert quantities == {
        "channel_entry_barrier",
        "channel_band_slope",
        "vertical_band_bending",
    }
    response = render_field_explanation(payload)
    text = " ".join(sum(response.values(), []))
    assert "Source plateau" in text
    assert "Source-edge와 Drain-edge" in text
    assert "surface와 Deep bulk Ec separation" in text
