from __future__ import annotations

from pathlib import Path

import numpy as np

from ai.field_map_model.inference import generate_gmsh_mesh
from backend.explanation.field_geometry import (
    build_field_geometry,
    build_field_geometry_interpretation,
    validate_field_geometry_interpretation,
)
from ai.shared.field_data import GeneratedFieldMap


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = REPO_ROOT / "tcad/data_extraction/base_case/gmsh_mos2d.geo"


def _output(length_nm: float, tox_nm: float) -> GeneratedFieldMap:
    mesh = generate_gmsh_mesh(length_nm, tox_nm, TEMPLATE)
    # Geometry interpretation is deliberately independent of model predictions.
    return GeneratedFieldMap(mesh, None, length_nm, tox_nm, 1e16, 1e20, 1e18)


def test_real_mesh_landmarks_follow_requested_device_dimensions() -> None:
    for length, tox in ((200.0, 20.0), (1200.0, 22.0)):
        geometry = build_field_geometry(_output(length, tox))
        landmarks = geometry.landmarks_nm
        assert abs((landmarks["gate_right"] - landmarks["gate_left"]) - length) < 1e-6
        assert abs((landmarks["silicon_oxide_interface_y"] - landmarks["oxide_top_y"]) - tox) < 1e-6
        assert geometry.quality["geometry_alignment"] == "high"
        assert geometry.quality["topology_valid"] is True
        assert geometry.quality["nondegenerate_elements"] is True


def test_normalized_channel_and_named_regions_survive_geometry_change() -> None:
    for output in (_output(200.0, 20.0), _output(1200.0, 22.0)):
        geometry = build_field_geometry(output)
        channel_u = geometry.node_coordinates["channel_u"]
        channel = geometry.node_masks["channel_near_surface"]
        assert np.min(channel_u[channel]) >= -1e-6
        assert np.max(channel_u[channel]) <= 1.0 + 1e-6
        for name in ("source_side_channel", "channel_center", "drain_side_channel"):
            assert np.count_nonzero(geometry.node_masks[name]) >= 5
            assert np.count_nonzero(geometry.element_masks[name]) >= 5
        assert geometry.quality["node_domain"]["core_region_coverage"] == "high"
        assert geometry.quality["element_domain"]["core_region_coverage"] == "high"


def test_cross_geometry_contract_forbids_index_and_pixel_comparison() -> None:
    outputs = [("Curve 1", _output(200.0, 20.0)), ("Curve 2", _output(1200.0, 22.0))]
    context, quality = build_field_geometry_interpretation(outputs)
    comparison = context["comparison"]
    assert comparison["device_dimensions_differ"] is True
    assert comparison["raw_index_comparison_allowed"] is False
    assert comparison["raw_pixel_comparison_allowed"] is False
    assert comparison["normalized_channel_comparison_allowed"] is True
    assert comparison["named_region_comparison_allowed"] is True
    assert quality["mesh_comparability"] == "valid"
    assert quality["normalized_coordinate_comparability"] == "valid"
    assert "raw_node_index_difference" in quality["suppressed_analysis_scope"]
    validate_field_geometry_interpretation(context, quality, {"curve_1", "curve_2"})
