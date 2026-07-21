from __future__ import annotations

import json

import numpy as np

from ai.field_map_model.inference import FieldMapPrediction
from backend.explanation.field_analyzer import build_field_payload
from backend.explanation.field_interpretation import build_common_field_interpretation
from ai.shared.field_data import GeneratedFieldMap
from tests.test_field_geometry import _output as geometry_output


def _predicted_output(length: float, tox: float, scale: float = 1.0) -> GeneratedFieldMap:
    blank = geometry_output(length, tox)
    mesh = blank.mesh
    node_x, node_y = mesh.node_xy_nm[:, 0], mesh.node_xy_nm[:, 1]
    element_x, element_y = mesh.element_centroid_xy_nm[:, 0], mesh.element_centroid_xy_nm[:, 1]
    center = 0.5 * (node_x.min() + node_x.max())
    potential = scale * (0.2 + 0.8 * (node_x - node_x.min()) / np.ptp(node_x)) * np.exp(-np.maximum(node_y, 0) / 500)
    ex = scale * (1e4 + 5e4 * np.exp(-((element_x - center) / max(length, 1)) ** 2))
    ey = scale * 2e4 * np.exp(-np.maximum(element_y, 0) / 100)
    node_fields = {
        "Potential": potential,
        "Electrons": np.abs(potential) * 1e17 + 1,
        "Holes": np.abs(1 - potential) * 1e15 + 1,
        "USRH": potential * 1e10,
    }
    element_fields = {
        "ElectricField_x": ex, "ElectricField_y": ey,
        "ElectronCurrent_x": ex * 1e-3, "ElectronCurrent_y": ey * 1e-3,
        "HoleCurrent_x": ex * 1e-5, "HoleCurrent_y": ey * 1e-5,
    }
    prediction = FieldMapPrediction(np.ones(len(node_x)), node_fields, element_fields)
    return GeneratedFieldMap(mesh, prediction, length, tox, 1e16, 1e20, 1e18)


def test_common_features_use_regions_profiles_and_clusters() -> None:
    outputs = [("Curve 1", _predicted_output(200, 20)), ("Curve 2", _predicted_output(1200, 22, 0.8))]
    regional, features, quality = build_common_field_interpretation(outputs, "Potential")
    assert any(item["region"] == "channel_center" for item in regional)
    profiles = [item for item in features if item["feature"] == "normalized_channel_profile"]
    assert len(profiles) == 2
    assert all(item["coordinate"] == "channel_u" for item in profiles)
    assert all(item["populated_bin_fraction"] >= 0.9 for item in profiles)
    assert any(item["feature"] == "regional_cluster_shift" for item in features)
    assert not any(item["feature"] == "global_hotspot_shift" for item in features)
    assert quality["profile_stability"] == "high"
    assert quality["global_extremum_used_for_comparison"] is False


def test_payload_contains_json_safe_common_field_interpretation() -> None:
    outputs = [("Curve 1", _predicted_output(200, 20)), ("Curve 2", _predicted_output(1200, 22, 0.8))]
    payload = build_field_payload(outputs, "Electric field", "Auto", "Robust 1-99%")
    interpretation = payload.interpretation
    assert interpretation["status"] == "partial"
    assert interpretation["regional_summaries"]
    assert interpretation["spatial_features"]
    assert interpretation["analysis_quality"]["profile_stability"] in {"high", "medium"}
    assert interpretation["analysis_quality"]["hotspot_stability"] in {"high", "medium"}
    json.dumps(payload.to_dict(), allow_nan=False)


def test_energy_band_marks_common_spatial_features_not_applicable() -> None:
    regional, features, quality = build_common_field_interpretation(
        [("Curve 1", _predicted_output(200, 20))], "Energy band (1D)"
    )
    assert regional == [] and features == []
    assert quality["profile_stability"] == "not_applicable"
    assert quality["hotspot_stability"] == "not_applicable"
