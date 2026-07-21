from __future__ import annotations

from itertools import combinations
from typing import Any

import numpy as np

from ai.shared.field_data import GeneratedFieldMap, scalar_display

from .field_geometry import FieldGeometry, build_field_geometry


FIELD_FEATURE_VERSION = "1.0"
PROFILE_BINS = 12
MIN_REGION_SAMPLES = 8
HOTSPOT_QUANTILE = 0.95
FEATURE_REGIONS = (
    "gate", "oxide", "source_near_surface", "source_side_ldd_near_surface",
    "channel_near_surface", "source_side_channel", "channel_center",
    "drain_side_channel", "drain_side_ldd_near_surface", "drain_near_surface",
    "deep_bulk",
)


def _field_values(output: GeneratedFieldMap, display: str) -> tuple[np.ndarray, str]:
    if display in {"Mesh", "Energy band (1D)"}:
        raise ValueError("common_spatial_features_not_applicable")
    scalar = scalar_display(output, display)
    return np.asarray(scalar.values, dtype=float).reshape(-1), scalar.domain


def _domain(geometry: FieldGeometry, output: GeneratedFieldMap, domain: str):
    if domain == "node":
        return output.mesh.node_xy_nm, geometry.node_masks, geometry.node_coordinates, np.ones(len(output.mesh.node_xy_nm))
    points = output.mesh.node_xy_nm[output.mesh.triangles]
    areas = np.abs(
        (points[:, 1, 0] - points[:, 0, 0]) * (points[:, 2, 1] - points[:, 0, 1])
        - (points[:, 1, 1] - points[:, 0, 1]) * (points[:, 2, 0] - points[:, 0, 0])
    ) * 0.5
    return output.mesh.element_centroid_xy_nm, geometry.element_masks, geometry.element_coordinates, areas


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    return float(np.average(values, weights=weights))


def _regional_summary(subject_id: str, region: str, values: np.ndarray, mask: np.ndarray, weights: np.ndarray) -> dict[str, Any] | None:
    selected = mask & np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    if np.count_nonzero(selected) < MIN_REGION_SAMPLES:
        return None
    current, current_weights = values[selected], weights[selected]
    magnitude = np.abs(current)
    return {
        "subject_id": subject_id, "region": region, "sample_count": int(len(current)),
        "signed_median": float(np.median(current)),
        "signed_weighted_mean": _weighted_mean(current, current_weights),
        "magnitude_median": float(np.median(magnitude)),
        "magnitude_p95": float(np.percentile(magnitude, 95)),
        "magnitude_p99": float(np.percentile(magnitude, 99)),
        "finite_fraction": float(np.count_nonzero(selected) / max(np.count_nonzero(mask), 1)),
    }


def _channel_profile(subject_id: str, values: np.ndarray, mask: np.ndarray, channel_u: np.ndarray, weights: np.ndarray) -> dict[str, Any]:
    selected = mask & np.isfinite(values) & np.isfinite(channel_u) & np.isfinite(weights) & (weights > 0)
    edges = np.linspace(0.0, 1.0, PROFILE_BINS + 1)
    bins = []
    for index in range(PROFILE_BINS):
        upper = channel_u <= edges[index + 1] if index == PROFILE_BINS - 1 else channel_u < edges[index + 1]
        current = selected & (channel_u >= edges[index]) & upper
        if not np.any(current):
            bins.append({"u_center": float((edges[index] + edges[index + 1]) / 2), "sample_count": 0, "signed_median": None, "magnitude_p90": None})
            continue
        bins.append({
            "u_center": float((edges[index] + edges[index + 1]) / 2),
            "sample_count": int(np.count_nonzero(current)),
            "signed_median": float(np.median(values[current])),
            "magnitude_p90": float(np.percentile(np.abs(values[current]), 90)),
        })
    populated = sum(item["sample_count"] > 0 for item in bins)
    return {
        "feature": "normalized_channel_profile", "subject_id": subject_id,
        "region": "channel_near_surface", "coordinate": "channel_u",
        "bin_count": PROFILE_BINS, "populated_bin_fraction": populated / PROFILE_BINS,
        "bins": bins,
    }


def _regional_hotspot(subject_id: str, region: str, values: np.ndarray, mask: np.ndarray, coordinates: dict[str, np.ndarray], weights: np.ndarray) -> dict[str, Any] | None:
    selected = mask & np.isfinite(values) & np.isfinite(coordinates["channel_u"]) & np.isfinite(coordinates["interface_offset_nm"]) & np.isfinite(weights) & (weights > 0)
    if np.count_nonzero(selected) < MIN_REGION_SAMPLES:
        return None
    magnitude = np.abs(values)
    threshold = float(np.quantile(magnitude[selected], HOTSPOT_QUANTILE))
    active = selected & (magnitude >= threshold)
    if not np.any(active):
        return None
    active_weights = weights[active]
    u = coordinates["channel_u"][active]
    depth = coordinates["interface_offset_nm"][active]
    centroid_u, centroid_depth = _weighted_mean(u, active_weights), _weighted_mean(depth, active_weights)
    spread_u = float(np.sqrt(np.average((u - centroid_u) ** 2, weights=active_weights)))
    spread_depth = float(np.sqrt(np.average((depth - centroid_depth) ** 2, weights=active_weights)))
    return {
        "feature": "regional_high_magnitude_cluster", "subject_id": subject_id, "region": region,
        "definition": "top_5_percent_magnitude_within_same_named_region",
        "threshold": threshold, "sample_count": int(np.count_nonzero(active)),
        "centroid_channel_u": centroid_u, "centroid_interface_offset_nm": centroid_depth,
        "spread_channel_u": spread_u, "spread_interface_offset_nm": spread_depth,
    }


def _relative_change(before: float, after: float) -> float | None:
    return None if before == 0 else float((after - before) / abs(before) * 100.0)


def build_common_field_interpretation(outputs: list[tuple[str, GeneratedFieldMap]], display: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if display in {"Mesh", "Energy band (1D)"}:
        return [], [], {"profile_stability": "not_applicable", "hotspot_stability": "not_applicable"}
    regional: list[dict[str, Any]] = []
    features: list[dict[str, Any]] = []
    subject_data: dict[str, dict[str, Any]] = {}
    for index, (_label, output) in enumerate(outputs):
        subject_id = f"curve_{index + 1}"
        geometry = build_field_geometry(output)
        values, domain = _field_values(output, display)
        _xy, masks, coordinates, weights = _domain(geometry, output, domain)
        summaries = {}
        hotspots = {}
        for region in FEATURE_REGIONS:
            summary = _regional_summary(subject_id, region, values, masks[region], weights)
            if summary:
                regional.append(summary); summaries[region] = summary
            hotspot = _regional_hotspot(subject_id, region, values, masks[region], coordinates, weights)
            if hotspot:
                features.append(hotspot); hotspots[region] = hotspot
        profile = _channel_profile(subject_id, values, masks["channel_near_surface"], coordinates["channel_u"], weights)
        features.append(profile)
        subject_data[subject_id] = {"summaries": summaries, "hotspots": hotspots, "profile": profile}

    for left_index, right_index in combinations(range(len(outputs)), 2):
        baseline_id, candidate_id = f"curve_{left_index + 1}", f"curve_{right_index + 1}"
        baseline, candidate = subject_data[baseline_id], subject_data[candidate_id]
        for region in baseline["summaries"].keys() & candidate["summaries"].keys():
            before, after = baseline["summaries"][region], candidate["summaries"][region]
            features.append({
                "feature": "regional_change", "baseline_subject_id": baseline_id,
                "candidate_subject_id": candidate_id, "region": region,
                "signed_median_change": float(after["signed_median"] - before["signed_median"]),
                "magnitude_p95_percent_change": _relative_change(before["magnitude_p95"], after["magnitude_p95"]),
            })
        for region in baseline["hotspots"].keys() & candidate["hotspots"].keys():
            before, after = baseline["hotspots"][region], candidate["hotspots"][region]
            features.append({
                "feature": "regional_cluster_shift", "baseline_subject_id": baseline_id,
                "candidate_subject_id": candidate_id, "region": region,
                "delta_channel_u": float(after["centroid_channel_u"] - before["centroid_channel_u"]),
                "delta_interface_offset_nm": float(after["centroid_interface_offset_nm"] - before["centroid_interface_offset_nm"]),
                "comparison_basis": "same_named_region_normalized_coordinates",
            })
        base_bins, candidate_bins = baseline["profile"]["bins"], candidate["profile"]["bins"]
        paired = [(a["signed_median"], b["signed_median"]) for a, b in zip(base_bins, candidate_bins) if a["signed_median"] is not None and b["signed_median"] is not None]
        if paired:
            differences = np.asarray([after - before for before, after in paired])
            features.append({
                "feature": "normalized_channel_profile_change", "baseline_subject_id": baseline_id,
                "candidate_subject_id": candidate_id, "paired_bin_fraction": len(paired) / PROFILE_BINS,
                "median_signed_difference": float(np.median(differences)),
                "maximum_absolute_bin_difference": float(np.max(np.abs(differences))),
            })

    profile_coverages = [data["profile"]["populated_bin_fraction"] for data in subject_data.values()]
    hotspot_counts = [len(data["hotspots"]) for data in subject_data.values()]
    quality = {
        "field_feature_version": FIELD_FEATURE_VERSION,
        "profile_stability": "high" if profile_coverages and min(profile_coverages) >= 0.9 else ("medium" if profile_coverages and min(profile_coverages) >= 0.6 else "low"),
        "hotspot_stability": "high" if hotspot_counts and min(hotspot_counts) >= 5 else ("medium" if hotspot_counts and min(hotspot_counts) >= 1 else "low"),
        "profile_populated_bin_fraction_min": min(profile_coverages) if profile_coverages else 0.0,
        "regional_hotspot_count_min": min(hotspot_counts) if hotspot_counts else 0,
        "global_extremum_used_for_comparison": False,
    }
    for index, item in enumerate(regional, 1):
        item["summary_id"] = f"fsr_{index}"
    for index, item in enumerate(features, 1):
        item["feature_id"] = f"fsf_{index}"
    return regional, features, quality


def validate_common_field_interpretation(regional: list[dict[str, Any]], features: list[dict[str, Any]], subject_ids: set[str]) -> None:
    if any(item.get("subject_id") not in subject_ids for item in regional):
        raise ValueError("Regional summary subject mismatch.")
    if any(item.get("feature") == "global_hotspot_shift" for item in features):
        raise ValueError("Global single-point hotspot comparison is forbidden.")
    for item in features:
        if item.get("feature") == "normalized_channel_profile" and item.get("coordinate") != "channel_u":
            raise ValueError("Channel profiles must use normalized channel_u.")
