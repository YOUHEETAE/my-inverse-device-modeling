from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np

from ai.shared.field_data import GeneratedFieldMap


GEOMETRY_CONTRACT_VERSION = "1.0"
REGION_IDS = {"bulk": 0, "oxide": 1, "gate": 2}
CORE_REGIONS = {"gate", "oxide", "channel_near_surface", "source_side_channel", "channel_center", "drain_side_channel", "deep_bulk"}


@dataclass(frozen=True)
class FieldGeometry:
    landmarks_nm: dict[str, float]
    node_masks: dict[str, np.ndarray]
    element_masks: dict[str, np.ndarray]
    node_coordinates: dict[str, np.ndarray]
    element_coordinates: dict[str, np.ndarray]
    quality: dict[str, Any]


def _landmarks(output: GeneratedFieldMap) -> dict[str, float]:
    mesh = output.mesh
    xy = np.asarray(mesh.node_xy_nm, dtype=float)
    bulk, oxide, gate = (np.asarray(mesh.node_region) == REGION_IDS[name] for name in ("bulk", "oxide", "gate"))
    if not all(np.any(mask) for mask in (bulk, oxide, gate)):
        raise ValueError("mesh_missing_required_material_region")
    surface = float(np.min(xy[bulk, 1])); body_bottom = float(np.max(xy[bulk, 1]))
    gate_left, gate_right = float(np.min(xy[gate, 0])), float(np.max(xy[gate, 0]))
    # The oxide physical group also contains the spacer-side dielectric up to the
    # gate top.  Tox must therefore be recovered from the oxide directly below
    # the gate, not from the global minimum y of the whole oxide region.
    edge_margin = max((gate_right - gate_left) * 1e-6, 1e-6)
    # Strictly exclude duplicated boundary nodes belonging to the side oxide.
    oxide_below_gate = oxide & (xy[:, 0] > gate_left + edge_margin) & (xy[:, 0] < gate_right - edge_margin)
    if not np.any(oxide_below_gate):
        raise ValueError("mesh_missing_gate_oxide_region")
    oxide_top = float(np.min(xy[oxide_below_gate, 1])); gate_top = float(np.min(xy[gate, 1]))
    spacer_width, contact_gap, near_surface_depth = 50.0, 50.0, min(50.0, max(body_bottom - surface, 0.0))
    return {
        "bulk_left": float(np.min(xy[bulk, 0])), "bulk_right": float(np.max(xy[bulk, 0])),
        "silicon_oxide_interface_y": surface, "body_bottom_y": body_bottom,
        "oxide_top_y": oxide_top, "gate_top_y": gate_top,
        "gate_left": gate_left, "gate_right": gate_right,
        "channel_center_x": 0.5 * (gate_left + gate_right),
        "spacer_left": gate_left - spacer_width, "spacer_right": gate_right + spacer_width,
        "source_contact_right": gate_left - spacer_width - contact_gap,
        "drain_contact_left": gate_right + spacer_width + contact_gap,
        "near_surface_bottom_y": surface + near_surface_depth,
    }


def normalized_coordinates(coordinates_nm: np.ndarray, landmarks: dict[str, float], tox_nm: float) -> dict[str, np.ndarray]:
    xy = np.asarray(coordinates_nm, dtype=float); x, y = xy[:, 0], xy[:, 1]
    length = max(landmarks["gate_right"] - landmarks["gate_left"], np.finfo(float).eps)
    body_depth = max(landmarks["body_bottom_y"] - landmarks["silicon_oxide_interface_y"], np.finfo(float).eps)
    return {
        "channel_u": (x - landmarks["gate_left"]) / length,
        "interface_offset_nm": y - landmarks["silicon_oxide_interface_y"],
        "oxide_v": (landmarks["silicon_oxide_interface_y"] - y) / max(float(tox_nm), np.finfo(float).eps),
        "bulk_v": (y - landmarks["silicon_oxide_interface_y"]) / body_depth,
    }


def named_region_masks(coordinates_nm: np.ndarray, region_ids: np.ndarray, landmarks: dict[str, float]) -> dict[str, np.ndarray]:
    xy = np.asarray(coordinates_nm, dtype=float); ids = np.asarray(region_ids)
    x, y = xy[:, 0], xy[:, 1]; eps = 1e-6
    bulk, oxide, gate = ids == 0, ids == 1, ids == 2
    surface = landmarks["silicon_oxide_interface_y"]
    near = bulk & (y >= surface - eps) & (y <= landmarks["near_surface_bottom_y"] + eps)
    channel = near & (x >= landmarks["gate_left"] - eps) & (x <= landmarks["gate_right"] + eps)
    length = max(landmarks["gate_right"] - landmarks["gate_left"], np.finfo(float).eps)
    u = (x - landmarks["gate_left"]) / length
    return {
        "gate": gate, "oxide": oxide,
        "source_near_surface": near & (x < landmarks["spacer_left"]),
        "source_side_ldd_near_surface": near & (x >= landmarks["spacer_left"]) & (x < landmarks["gate_left"]),
        "channel_near_surface": channel,
        "source_side_channel": channel & (u <= 1.0 / 3.0 + eps),
        "channel_center": channel & (u > 1.0 / 3.0 + eps) & (u < 2.0 / 3.0 - eps),
        "drain_side_channel": channel & (u >= 2.0 / 3.0 - eps),
        "drain_side_ldd_near_surface": near & (x > landmarks["gate_right"]) & (x <= landmarks["spacer_right"]),
        "drain_near_surface": near & (x > landmarks["spacer_right"]),
        "deep_bulk": bulk & (y > landmarks["near_surface_bottom_y"] + eps),
    }


def _domain_quality(coordinates: np.ndarray, regions: np.ndarray, masks: dict[str, np.ndarray]) -> dict[str, Any]:
    counts = {name: int(np.count_nonzero(mask)) for name, mask in masks.items()}
    required_counts = [counts.get(name, 0) for name in CORE_REGIONS]
    finite = bool(np.isfinite(coordinates).all())
    coverage = "high" if required_counts and min(required_counts) >= 5 else ("medium" if required_counts and min(required_counts) >= 1 else "low")
    return {
        "sample_count": int(len(coordinates)), "finite_coordinates": finite,
        "material_region_ids": sorted(int(value) for value in np.unique(regions)),
        "named_region_sample_counts": counts, "core_region_coverage": coverage,
    }


def build_field_geometry(output: GeneratedFieldMap) -> FieldGeometry:
    mesh = output.mesh; landmarks = _landmarks(output)
    node_masks = named_region_masks(mesh.node_xy_nm, mesh.node_region, landmarks)
    element_masks = named_region_masks(mesh.element_centroid_xy_nm, mesh.element_region, landmarks)
    node_coordinates = normalized_coordinates(mesh.node_xy_nm, landmarks, output.tox_nm)
    element_coordinates = normalized_coordinates(mesh.element_centroid_xy_nm, landmarks, output.tox_nm)
    triangles = np.asarray(mesh.triangles)
    topology_valid = bool(triangles.ndim == 2 and triangles.shape[1:] == (3,) and len(triangles)
                          and np.min(triangles) >= 0 and np.max(triangles) < len(mesh.node_xy_nm))
    if topology_valid:
        points = np.asarray(mesh.node_xy_nm, dtype=float)[triangles]
        twice_area = np.abs((points[:, 1, 0] - points[:, 0, 0]) * (points[:, 2, 1] - points[:, 0, 1])
                            - (points[:, 1, 1] - points[:, 0, 1]) * (points[:, 2, 0] - points[:, 0, 0]))
        nondegenerate = bool(np.all(twice_area > np.finfo(float).eps))
    else: nondegenerate = False
    actual_length = landmarks["gate_right"] - landmarks["gate_left"]
    actual_tox = landmarks["silicon_oxide_interface_y"] - landmarks["oxide_top_y"]
    length_error = abs(actual_length - float(output.length_nm))
    tox_error = abs(actual_tox - float(output.tox_nm))
    interface_error = abs(landmarks["silicon_oxide_interface_y"] - float(np.max(np.asarray(mesh.node_xy_nm)[np.asarray(mesh.node_region) == 1, 1])))
    node_quality = _domain_quality(np.asarray(mesh.node_xy_nm), np.asarray(mesh.node_region), node_masks)
    element_quality = _domain_quality(np.asarray(mesh.element_centroid_xy_nm), np.asarray(mesh.element_region), element_masks)
    valid = topology_valid and nondegenerate and node_quality["finite_coordinates"] and element_quality["finite_coordinates"] and length_error <= 1e-3 and tox_error <= 1e-3 and interface_error <= 1e-3
    quality = {
        "geometry_alignment": "high" if valid else "low",
        "topology_valid": topology_valid, "nondegenerate_elements": nondegenerate,
        "channel_length_error_nm": float(length_error), "oxide_thickness_error_nm": float(tox_error),
        "interface_alignment_error_nm": float(interface_error),
        "node_domain": node_quality, "element_domain": element_quality,
    }
    return FieldGeometry(landmarks, node_masks, element_masks, node_coordinates, element_coordinates, quality)


def _subject_geometry(subject_id: str, label: str, output: GeneratedFieldMap, geometry: FieldGeometry) -> dict[str, Any]:
    return {
        "subject_id": subject_id, "display_name": label,
        "device_dimensions_nm": {"channel_length": float(output.length_nm), "oxide_thickness": float(output.tox_nm)},
        "landmarks_nm": geometry.landmarks_nm,
        "coordinate_systems": {
            "physical": {"x": "nm", "y": "nm", "source": "original_mesh"},
            "channel_u": {"origin": "gate_left", "end": "gate_right", "source_edge": 0.0, "center": 0.5, "drain_edge": 1.0},
            "interface_offset": {"unit": "nm", "zero": "silicon_oxide_interface", "positive_direction": "into_silicon_bulk"},
            "oxide_v": {"zero": "silicon_oxide_interface", "one": "oxide_top"},
            "bulk_v": {"zero": "silicon_oxide_interface", "one": "body_bottom"},
        },
        "named_region_definition": {
            "channel_partition": "equal thirds in normalized channel_u",
            "near_surface_depth_nm": geometry.landmarks_nm["near_surface_bottom_y"] - geometry.landmarks_nm["silicon_oxide_interface_y"],
            "region_names": list(geometry.node_masks),
        },
        "quality": geometry.quality,
    }


def build_field_geometry_interpretation(outputs: Iterable[tuple[str, GeneratedFieldMap]]) -> tuple[dict[str, Any], dict[str, Any]]:
    entries = []
    for index, (label, output) in enumerate(outputs):
        geometry = build_field_geometry(output)
        entries.append(_subject_geometry(f"curve_{index + 1}", label, output, geometry))
    aligned = all(item["quality"]["geometry_alignment"] == "high" for item in entries)
    node_coverages = [item["quality"]["node_domain"]["core_region_coverage"] for item in entries]
    element_coverages = [item["quality"]["element_domain"]["core_region_coverage"] for item in entries]
    dimensions = [item["device_dimensions_nm"] for item in entries]
    geometry_context = {
        "geometry_contract_version": GEOMETRY_CONTRACT_VERSION,
        "comparison_basis": "named_physical_regions_and_normalized_profiles",
        "subjects": entries,
        "comparison": {
            "subject_count": len(entries),
            "device_dimensions_differ": len({(item["channel_length"], item["oxide_thickness"]) for item in dimensions}) > 1,
            "raw_index_comparison_allowed": False,
            "raw_pixel_comparison_allowed": False,
            "physical_coordinate_comparison_allowed": aligned,
            "normalized_channel_comparison_allowed": aligned,
            "named_region_comparison_allowed": aligned,
        },
    }
    coverage = "high" if all(value == "high" for value in node_coverages + element_coverages) else ("medium" if all(value != "low" for value in node_coverages + element_coverages) else "low")
    analysis_quality = {
        "geometry_alignment": "high" if aligned else "low",
        "region_coverage": coverage,
        "mesh_comparability": "valid" if aligned else "invalid",
        "normalized_coordinate_comparability": "valid" if aligned else "invalid",
        "profile_stability": "unknown", "hotspot_stability": "unknown",
        "model_spatial_fidelity": "approximate",
        "allowed_analysis_scope": ["named_region_statistics", "normalized_profiles"] if aligned else [],
        "suppressed_analysis_scope": ["raw_node_index_difference", "rendered_pixel_difference"],
    }
    return geometry_context, analysis_quality


def validate_field_geometry_interpretation(geometry_context: dict[str, Any], analysis_quality: dict[str, Any], subject_ids: set[str]) -> None:
    if geometry_context.get("geometry_contract_version") != GEOMETRY_CONTRACT_VERSION:
        raise ValueError("Unsupported Field geometry contract.")
    entries = geometry_context.get("subjects", [])
    if {item.get("subject_id") for item in entries} != subject_ids:
        raise ValueError("Field geometry subjects do not match Payload subjects.")
    if geometry_context.get("comparison", {}).get("raw_index_comparison_allowed") is not False:
        raise ValueError("Raw Field index comparison must remain disabled.")
    if analysis_quality.get("geometry_alignment") not in {"high", "medium", "low"}:
        raise ValueError("Invalid Field geometry alignment quality.")
