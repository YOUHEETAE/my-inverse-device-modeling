from __future__ import annotations

from itertools import combinations

import numpy as np

from ai.shared.field_data import (
    GeneratedFieldMap,
    finite_limits,
    geometry_markers,
    region_interpolator,
    scalar_display,
)

from .curve_analyzer import PARAMETER_PRINCIPLES
from .payload_builders import build_payload
from .schemas import AnalysisPayload
from .field_geometry import build_field_geometry_interpretation, validate_field_geometry_interpretation
from .field_interpretation import build_common_field_interpretation, validate_common_field_interpretation
from .field_conclusions import build_field_specific_conclusions, validate_field_specific_conclusions
from .field_links import build_cross_domain_links, validate_cross_domain_links
from .payload_builders import validate_analysis_payload


def _device_parameters(output: GeneratedFieldMap) -> dict[str, float]:
    return {"L": output.length_nm, "T": output.tox_nm, "B": output.bulk_doping, "SD": output.sd_doping, "LDD": output.ldd_doping}


def _parameter_changes(baseline: dict[str, float], candidate: dict[str, float]) -> dict[str, dict[str, object]]:
    changes = {}
    for name, before in baseline.items():
        after = candidate[name]
        if before == after:
            continue
        direction = "increased" if after > before else "decreased"
        changes[name] = {
            "physical_name": PARAMETER_PRINCIPLES[name]["name"],
            "baseline": before, "candidate": after, "absolute": after - before,
            "percent": None if before == 0 else (after - before) / abs(before) * 100.0,
            "direction": direction,
            "general_principle": PARAMETER_PRINCIPLES[name]["increase" if after > before else "decrease"],
        }
    return changes


def _element_areas(output: GeneratedFieldMap) -> np.ndarray:
    points = output.mesh.node_xy_nm[output.mesh.triangles]
    cross = (points[:, 1, 0] - points[:, 0, 0]) * (points[:, 2, 1] - points[:, 0, 1]) - (points[:, 1, 1] - points[:, 0, 1]) * (points[:, 2, 0] - points[:, 0, 0])
    return np.abs(cross) * 0.5


def _region_masks(output: GeneratedFieldMap, domain: str) -> dict[str, np.ndarray]:
    mesh = output.mesh
    coordinates = mesh.node_xy_nm if domain == "node" else mesh.element_centroid_xy_nm
    region_ids = mesh.node_region if domain == "node" else mesh.element_region
    x, y = coordinates[:, 0], coordinates[:, 1]
    marker = geometry_markers(output)
    bulk = region_ids == 0
    near_surface = bulk & (y >= marker["surface"] - 1e-9) & (y <= marker["diffusion"] + 1e-9)
    return {
        "Gate": region_ids == 2,
        "Oxide": region_ids == 1,
        "Source near-surface": near_surface & (x < marker["spacer_left"]),
        "Source-side LDD near-surface": near_surface & (x >= marker["spacer_left"]) & (x < marker["gate_left"]),
        "Channel near-surface": near_surface & (x >= marker["gate_left"]) & (x <= marker["gate_right"]),
        "Drain-side LDD near-surface": near_surface & (x > marker["gate_right"]) & (x <= marker["spacer_right"]),
        "Drain near-surface": near_surface & (x > marker["spacer_right"]),
        "Deep bulk": bulk & (y > marker["diffusion"]),
    }


def _statistics(values: np.ndarray, coordinates: np.ndarray, mask: np.ndarray | None = None) -> dict[str, object]:
    values = np.asarray(values, dtype=float).reshape(-1)
    selected = np.ones(len(values), dtype=bool) if mask is None else np.asarray(mask, dtype=bool)
    finite_mask = selected & np.isfinite(values)
    finite = values[finite_mask]
    if not len(finite):
        return {"finite_count": 0, "total_count": int(np.count_nonzero(selected))}
    indices = np.flatnonzero(finite_mask)
    min_index, max_index = int(indices[np.argmin(finite)]), int(indices[np.argmax(finite)])
    return {
        "finite_count": int(len(finite)), "total_count": int(np.count_nonzero(selected)),
        "min": float(np.min(finite)), "max": float(np.max(finite)), "mean": float(np.mean(finite)),
        "median": float(np.median(finite)), "p01": float(np.percentile(finite, 1)), "p95": float(np.percentile(finite, 95)), "p99": float(np.percentile(finite, 99)),
        "min_position_nm": coordinates[min_index].astype(float).tolist(), "max_position_nm": coordinates[max_index].astype(float).tolist(),
    }


def _potential_gradient_v_per_nm(output: GeneratedFieldMap) -> np.ndarray:
    points = output.mesh.node_xy_nm[output.mesh.triangles]
    potential = np.asarray(output.prediction.node_fields["Potential"], dtype=float)[output.mesh.triangles]
    matrix = np.stack((points[:, 1] - points[:, 0], points[:, 2] - points[:, 0]), axis=1)
    rhs = np.stack((potential[:, 1] - potential[:, 0], potential[:, 2] - potential[:, 0]), axis=1)
    determinant = matrix[:, 0, 0] * matrix[:, 1, 1] - matrix[:, 0, 1] * matrix[:, 1, 0]
    valid = np.abs(determinant) > np.finfo(float).eps
    gradient = np.full((len(matrix), 2), np.nan)
    gradient[valid] = np.linalg.solve(matrix[valid], rhs[valid, :, None])[:, :, 0]
    return np.linalg.norm(gradient, axis=1)


def _weighted_fraction(mask: np.ndarray, selected: np.ndarray, weights: np.ndarray) -> float | None:
    denominator = float(np.sum(weights[selected]))
    return None if denominator == 0 else float(np.sum(weights[selected & mask]) / denominator)


def _energy_band_metrics(output: GeneratedFieldMap) -> dict[str, object]:
    mesh = output.mesh; bulk = mesh.node_region == 0
    marker = geometry_markers(output)
    x_min, x_max = float(mesh.node_xy_nm[bulk, 0].min()), float(mesh.node_xy_nm[bulk, 0].max())
    positive_y = mesh.node_xy_nm[bulk & (mesh.node_xy_nm[:, 1] > 1e-8), 1]
    y_channel = float(positive_y.min()) if len(positive_y) else 0.0
    x_line = np.linspace(x_min, x_max, 600)
    potential = np.asarray(region_interpolator(output, 0)(x_line, np.full_like(x_line, y_channel)).filled(np.nan))
    finite = np.isfinite(potential)
    if not np.any(finite):
        return {"channel_cut": {"finite": False}}
    first = int(np.flatnonzero(finite)[0]); reference_potential = float(potential[first])
    ec = reference_potential - potential
    finite_indices = np.flatnonzero(np.isfinite(ec))
    channel = finite & (x_line >= marker["gate_left"]) & (x_line <= marker["gate_right"])
    source_plateau = finite & (x_line <= marker["source_contact_right"])
    if not np.any(source_plateau):
        source_plateau = finite & (x_line < marker["gate_left"])
    source_reference = float(np.median(ec[source_plateau])) if np.any(source_plateau) else float(ec[first])
    channel_center_x = (marker["gate_left"] + marker["gate_right"]) / 2.0
    injection_path = finite & (x_line >= marker["source_contact_right"]) & (x_line <= channel_center_x)
    if not np.any(injection_path):
        injection_path = channel
    injection_indices = np.flatnonzero(injection_path)
    peak_index = int(injection_indices[np.argmax(ec[injection_indices])])
    raw_barrier_height = float(ec[peak_index] - source_reference)
    channel_indices = np.flatnonzero(channel)
    channel_length = max(marker["gate_right"] - marker["gate_left"], 1e-12)
    u = (x_line - marker["gate_left"]) / channel_length

    def _segment_value(lower: float, upper: float) -> float | None:
        selected = channel & (u >= lower) & (u <= upper)
        return float(np.median(ec[selected])) if np.any(selected) else None

    source_edge = _segment_value(0.0, 0.1)
    center = _segment_value(0.45, 0.55)
    drain_edge = _segment_value(0.9, 1.0)
    channel_tilt = (
        None if source_edge is None or drain_edge is None
        else float(drain_edge - source_edge)
    )
    channel_cut = {
        "finite": True, "y_nm": y_channel,
        "source_relative_Ec_eV": source_reference, "drain_relative_Ec_eV": float(ec[finite_indices[-1]]),
        "maximum_relative_Ec_eV": float(ec[peak_index]), "minimum_relative_Ec_eV": float(np.nanmin(ec)),
        "barrier_height_from_source_eV": max(0.0, raw_barrier_height),
        "positive_barrier_resolved": raw_barrier_height > 1e-6,
        "barrier_position_x_nm": float(x_line[peak_index]),
        "barrier_position_channel_u": float(u[peak_index]),
        "channel_source_edge_Ec_eV": source_edge,
        "channel_center_Ec_eV": center,
        "channel_drain_edge_Ec_eV": drain_edge,
        "channel_tilt_eV": channel_tilt,
        "channel_slope_magnitude_eV_per_nm": (
            None if channel_tilt is None else abs(channel_tilt) / channel_length
        ),
        "channel_band_span_eV": (
            float(np.max(ec[channel_indices]) - np.min(ec[channel_indices]))
            if len(channel_indices) else None
        ),
    }
    x_center = (x_min + x_max) / 2.0
    region_specs = {0: (0.0, 1.12, "Bulk"), 1: (3.1, 9.0, "Oxide"), 2: (0.0, 1.12, "Gate")}
    vertical = {}
    for region, (offset, gap, name) in region_specs.items():
        mask = mesh.node_region == region
        y_min, y_max = float(mesh.node_xy_nm[mask, 1].min()), float(mesh.node_xy_nm[mask, 1].max())
        y_line = np.linspace(y_min, y_max, 300)
        region_potential = np.asarray(region_interpolator(output, region)(np.full_like(y_line, x_center), y_line).filled(np.nan))
        region_ec = -region_potential + offset + reference_potential
        finite_region = region_ec[np.isfinite(region_ec)]
        if not len(finite_region):
            continue
        vertical[name] = {
            "Ec_start_eV": float(finite_region[0]), "Ec_end_eV": float(finite_region[-1]),
            "Ec_change_eV": float(finite_region[-1] - finite_region[0]),
            "surface_minus_deep_Ec_eV": float(finite_region[0] - finite_region[-1]),
            "band_bending_magnitude_eV": float(abs(finite_region[0] - finite_region[-1])),
            "Ec_min_eV": float(np.min(finite_region)), "Ec_max_eV": float(np.max(finite_region)),
            "band_gap_eV": gap,
        }
    return {"channel_cut": channel_cut, "vertical_gate_oxide_bulk_cut": vertical, "x_center_nm": x_center, "interpretation_limit": "Energy bands are model-derived approximations relative to the source reference."}


def _specialized_metrics(output: GeneratedFieldMap, display: str, contour_step_v: float | None, high_field_threshold: float | None, display_threshold: float | None) -> dict[str, object]:
    if display not in {"Potential", "Electric field"}:
        if display == "Energy band (1D)":
            return _energy_band_metrics(output)
        if display == "Mesh":
            return {}
        scalar = scalar_display(output, display)
        element_values = np.mean(np.asarray(scalar.values)[output.mesh.triangles], axis=1) if scalar.domain == "node" else np.asarray(scalar.values)
        magnitude = np.abs(element_values)
        coordinates = output.mesh.element_centroid_xy_nm
        masks = _region_masks(output, "element")
        areas = _element_areas(output)
        regions = {}
        for name, mask in masks.items():
            if not np.any(mask):
                continue
            positive = magnitude > 0
            log_values = np.full_like(magnitude, np.nan, dtype=float)
            log_values[positive] = np.log10(magnitude[positive])
            region = {"magnitude": _statistics(magnitude, coordinates, mask), "log10_magnitude": _statistics(log_values, coordinates, mask)}
            if display_threshold is not None:
                region["area_fraction_above_shared_display_threshold"] = _weighted_fraction(magnitude >= display_threshold, mask, areas)
            regions[name] = region
        return {"regions": regions, "shared_display_threshold": display_threshold, "threshold_basis": "90th percentile of combined absolute display values"}
    field = np.hypot(output.prediction.element_fields["ElectricField_x"], output.prediction.element_fields["ElectricField_y"])
    masks = _region_masks(output, "element")
    coordinates = output.mesh.element_centroid_xy_nm
    areas = _element_areas(output)
    gradient = _potential_gradient_v_per_nm(output)
    regions = {}
    for name, mask in masks.items():
        if not np.any(mask):
            continue
        field_stats = _statistics(field, coordinates, mask)
        region = {"electric_field_V_per_cm": field_stats}
        if high_field_threshold is not None:
            region["area_fraction_above_shared_high_field_threshold"] = _weighted_fraction(field >= high_field_threshold, mask, areas)
        finite_gradient = gradient[mask & np.isfinite(gradient)]
        if len(finite_gradient):
            median_gradient = float(np.median(finite_gradient))
            region["potential_gradient_median_V_per_nm"] = median_gradient
            region["estimated_median_contour_spacing_nm"] = None if not contour_step_v or median_gradient <= 0 else float(contour_step_v / median_gradient)
        regions[name] = region
    return {"regions": regions, "shared_high_field_threshold_V_per_cm": high_field_threshold, "shared_potential_contour_step_V": contour_step_v}


def _percent_change(before: float | None, after: float | None) -> float | None:
    if before is None or after is None or before == 0:
        return None
    return (after - before) / abs(before) * 100.0


def _trend_direction(values: list[float]) -> str:
    if len(values) < 2:
        return "insufficient"
    scale = max(max(abs(value) for value in values), 1e-30)
    tolerance = scale * 0.01
    differences = [
        after - before for before, after in zip(values, values[1:])
    ]
    significant = [
        value for value in differences if abs(value) > tolerance
    ]
    if not significant:
        return "stable"
    if all(value > 0 for value in significant):
        return "monotonic_increase"
    if all(value < 0 for value in significant):
        return "monotonic_decrease"
    return "non_monotonic"


def _build_multi_condition_trends(payload: AnalysisPayload) -> list[dict[str, object]]:
    plan = payload.comparison_plan or {}
    if (
        len(payload.subjects) < 3
        or plan.get("analysis_mode") != "controlled_sweep"
    ):
        return []
    ordered_ids = list(plan.get("sweep_subject_ids") or [])
    if len(ordered_ids) != len(payload.subjects):
        return []
    display = payload.context.get("display")
    trends: list[dict[str, object]] = []
    if display == "energy_band":
        profiles = {
            item.get("subject_id"): item
            for item in payload.interpretation.get("energy_band_profiles", [])
        }
        quantities = (
            (
                "channel_entry_barrier",
                lambda item: item.get("channel_cut", {}).get(
                    "barrier_height_from_source_eV"
                ),
            ),
            (
                "channel_band_slope",
                lambda item: item.get("channel_cut", {}).get(
                    "channel_slope_magnitude_eV_per_nm"
                ),
            ),
            (
                "vertical_band_bending",
                lambda item: item.get(
                    "vertical_gate_oxide_bulk_cut", {}
                ).get("Bulk", {}).get("band_bending_magnitude_eV"),
            ),
        )
        for quantity, getter in quantities:
            values = [
                getter(profiles.get(subject_id, {}))
                for subject_id in ordered_ids
            ]
            if any(value is None for value in values):
                continue
            numeric = [float(value) for value in values]
            trends.append({
                "trend_id": f"field_trend_{len(trends) + 1}",
                "quantity": quantity,
                "region": "channel_near_surface",
                "ordered_subject_ids": ordered_ids,
                "ordered_sweep_values": list(
                    plan.get("sweep_values") or []
                ),
                "direction": _trend_direction(numeric),
                "internal_values": numeric,
                "claim_limit": "spatial_prediction_only",
            })
        return trends

    summaries: dict[str, dict[str, float]] = {}
    for item in payload.interpretation.get("regional_summaries", []):
        subject_id = item.get("subject_id")
        region = item.get("region")
        value = item.get("magnitude_p95")
        if (
            subject_id in ordered_ids
            and region
            and isinstance(value, (int, float))
        ):
            summaries.setdefault(str(region), {})[str(subject_id)] = float(value)
    ranked: list[tuple[float, dict[str, object]]] = []
    for region, by_subject in summaries.items():
        if not all(subject_id in by_subject for subject_id in ordered_ids):
            continue
        values = [by_subject[subject_id] for subject_id in ordered_ids]
        scale = max(max(abs(value) for value in values), 1e-30)
        score = (max(values) - min(values)) / scale
        ranked.append((score, {
            "quantity": "regional_magnitude_p95",
            "region": region,
            "ordered_subject_ids": ordered_ids,
            "ordered_sweep_values": list(plan.get("sweep_values") or []),
            "direction": _trend_direction(values),
            "internal_values": values,
            "claim_limit": "spatial_prediction_only",
        }))
    for _score, trend in sorted(
        ranked, key=lambda item: (-item[0], str(item[1]["region"]))
    )[:5]:
        trend["trend_id"] = f"field_trend_{len(trends) + 1}"
        trends.append(trend)
    return trends


def _visual_evidence(baseline: dict[str, object], candidate: dict[str, object], display: str) -> list[dict[str, object]]:
    if display == "Mesh":
        return []
    if display == "Energy band (1D)":
        base_cut = baseline.get("specialized_metrics", {}).get("channel_cut", {})
        candidate_cut = candidate.get("specialized_metrics", {}).get("channel_cut", {})
        before, after = base_cut.get("barrier_height_from_source_eV"), candidate_cut.get("barrier_height_from_source_eV")
        if before is None or after is None:
            return []
        evidence = [{
            "visual_cue": "channel_barrier_changed",
            "baseline_barrier_eV": before,
            "candidate_barrier_eV": after,
            "absolute_change_eV": after - before,
            "percent_change": _percent_change(before, after),
            "interpretation": "Horizontal Source-to-Channel cut에서 Source plateau 대비 국부 Ec maximum으로 확인",
        }]
        before_slope = base_cut.get("channel_slope_magnitude_eV_per_nm")
        after_slope = candidate_cut.get("channel_slope_magnitude_eV_per_nm")
        if before_slope is not None and after_slope is not None:
            evidence.append({
                "visual_cue": "channel_band_slope_changed",
                "baseline_slope": before_slope,
                "candidate_slope": after_slope,
                "absolute_change": after_slope - before_slope,
                "interpretation": "Horizontal channel cut에서 Source-side와 Drain-side Ec의 기울기 차이로 확인",
            })
        base_vertical = baseline.get("specialized_metrics", {}).get(
            "vertical_gate_oxide_bulk_cut", {}
        ).get("Bulk", {})
        candidate_vertical = candidate.get("specialized_metrics", {}).get(
            "vertical_gate_oxide_bulk_cut", {}
        ).get("Bulk", {})
        before_bending = base_vertical.get("band_bending_magnitude_eV")
        after_bending = candidate_vertical.get("band_bending_magnitude_eV")
        if before_bending is not None and after_bending is not None:
            evidence.append({
                "visual_cue": "vertical_band_bending_changed",
                "baseline_bending_eV": before_bending,
                "candidate_bending_eV": after_bending,
                "absolute_change_eV": after_bending - before_bending,
                "baseline_signed_bending_eV": base_vertical.get("surface_minus_deep_Ec_eV"),
                "candidate_signed_bending_eV": candidate_vertical.get("surface_minus_deep_Ec_eV"),
                "interpretation": "Vertical Gate-Oxide-Bulk cut에서 channel surface와 Deep bulk의 Ec separation으로 확인",
            })
        return evidence
    evidence = []
    base_regions = baseline.get("specialized_metrics", {}).get("regions", {})
    candidate_regions = candidate.get("specialized_metrics", {}).get("regions", {})
    for region in base_regions.keys() & candidate_regions.keys():
        before, after = base_regions[region], candidate_regions[region]
        value_key = "electric_field_V_per_cm" if "electric_field_V_per_cm" in before else "magnitude"
        base_value, candidate_value = before[value_key], after[value_key]
        value_change = _percent_change(base_value.get("p99"), candidate_value.get("p99"))
        fraction_key = "area_fraction_above_shared_high_field_threshold" if "area_fraction_above_shared_high_field_threshold" in before else "area_fraction_above_shared_display_threshold"
        base_fraction, candidate_fraction = before.get(fraction_key), after.get(fraction_key)
        if value_change is not None and abs(value_change) >= 1.0:
            cue = "stronger_or_weaker_field_color" if display in {"Potential", "Electric field"} else "display_magnitude_color_changed"
            evidence.append({"visual_cue": cue, "region": region, "p99_percent_change": value_change, "interpretation": "shared color scale에서 색상 강도 변화로 확인 가능"})
        if base_fraction is not None and candidate_fraction is not None and abs(candidate_fraction - base_fraction) >= 0.005:
            cue = "high_field_colored_area_changed" if display in {"Potential", "Electric field"} else "high_display_colored_area_changed"
            evidence.append({"visual_cue": cue, "region": region, "baseline_area_percent": base_fraction * 100.0, "candidate_area_percent": candidate_fraction * 100.0, "percentage_point_change": (candidate_fraction - base_fraction) * 100.0, "interpretation": "shared threshold 이상 색상 영역의 넓이 변화로 확인 가능"})
        if display == "Potential":
            base_spacing, candidate_spacing = before.get("estimated_median_contour_spacing_nm"), after.get("estimated_median_contour_spacing_nm")
            spacing_change = _percent_change(base_spacing, candidate_spacing)
            if spacing_change is not None and abs(spacing_change) >= 1.0:
                evidence.append({"visual_cue": "potential_contour_spacing_changed", "region": region, "baseline_spacing_nm": base_spacing, "candidate_spacing_nm": candidate_spacing, "percent_change": spacing_change, "interpretation": "contour 간격이 좁아지면 Potential gradient와 Electric field가 커진 경향"})
    base_position = np.asarray(baseline["statistics"].get("max_position_nm", []), dtype=float)
    candidate_position = np.asarray(candidate["statistics"].get("max_position_nm", []), dtype=float)
    if base_position.shape == (2,) and candidate_position.shape == (2,):
        shift = candidate_position - base_position
        evidence.append({"visual_cue": "hotspot_shift", "shift_nm": float(np.linalg.norm(shift)), "delta_xy_nm": shift.tolist(), "interpretation": "최댓값 위치의 이동으로 확인 가능"})
    return evidence


def build_field_payload(outputs: list[tuple[str, GeneratedFieldMap]], display: str, scale_mode: str, range_mode: str) -> AnalysisPayload:
    if display in {"Mesh", "Abs net doping", "Net doping"}:
        raise ValueError(f"{display} is not supported by LLM explanation.")
    if len(outputs) > 2:
        # The comparison mock-text renderer (field_renderer.py) and conclusion
        # builder below still assume a single baseline/candidate pair — they
        # were never extended for 3+ devices the way the iv_curve pipeline
        # was. Fail clearly here instead of an IndexError/validation error
        # deeper in the pipeline until that generalization is designed.
        raise ValueError("Field comparison explanation currently supports at most 2 devices.")
    scalar_data = []
    all_potential = np.concatenate([np.asarray(output.prediction.node_fields["Potential"], dtype=float) for _label, output in outputs])
    potential_low, potential_high = finite_limits(all_potential, range_mode)
    contour_step = (potential_high - potential_low) / 10.0 if display == "Potential" and scale_mode in {"Auto", "Linear"} else None
    all_field = np.concatenate([np.hypot(output.prediction.element_fields["ElectricField_x"], output.prediction.element_fields["ElectricField_y"]) for _label, output in outputs])
    finite_field = all_field[np.isfinite(all_field)]
    high_field_threshold = float(np.percentile(finite_field, 90)) if len(finite_field) else None
    display_magnitudes = []
    if display not in {"Mesh", "Energy band (1D)"}:
        for _label, output in outputs:
            display_magnitudes.append(np.abs(np.asarray(scalar_display(output, display).values, dtype=float)).reshape(-1))
    finite_display = np.concatenate(display_magnitudes) if display_magnitudes else np.asarray([])
    finite_display = finite_display[np.isfinite(finite_display)]
    display_threshold = float(np.percentile(finite_display, 90)) if len(finite_display) else None
    warnings: list[str] = []
    for label, output in outputs:
        if display in {"Mesh", "Energy band (1D)"}:
            values, domain, quantity = output.prediction.node_fields["Potential"], "node", "Potential (supporting data)"
        else:
            scalar = scalar_display(output, display); values, domain, quantity = scalar.values, scalar.domain, scalar.label
        coordinates = output.mesh.node_xy_nm if domain == "node" else output.mesh.element_centroid_xy_nm
        stats = _statistics(values, coordinates)
        if stats.get("finite_count") != stats.get("total_count"):
            warnings.append(f"{label}: non-finite values are present.")
        scalar_data.append({"label": label, "device_parameters": _device_parameters(output), "quantity": quantity, "domain": domain, "statistics": stats, "specialized_metrics": _specialized_metrics(output, display, contour_step, high_field_threshold, display_threshold)})
    comparisons = []
    for baseline_index, candidate_index in combinations(range(len(scalar_data)), 2):
        baseline, candidate = scalar_data[baseline_index], scalar_data[candidate_index]
        changes = {}
        for name in ("min", "max", "mean", "median", "p01", "p95", "p99"):
            before, after = baseline["statistics"].get(name), candidate["statistics"].get(name)
            if before is not None and after is not None:
                changes[name] = {"baseline": before, "candidate": after, "absolute": after - before, "percent": _percent_change(before, after)}
        device_changes = _parameter_changes(baseline["device_parameters"], candidate["device_parameters"])
        comparisons.append({"baseline": baseline["label"], "candidate": candidate["label"], "device_parameter_changes": device_changes, "is_single_parameter_controlled_comparison": len(device_changes) == 1, "global_statistic_changes": changes, "visual_evidence": _visual_evidence(baseline, candidate, display)})
    display_map = {"Potential": "potential", "Electric field": "electric_field", "Electron density": "electron_density", "Hole density": "hole_density", "Electron current density": "electron_current_density", "Hole current density": "hole_current_density", "Total current density": "total_current_density", "SRH recombination": "srh_recombination", "Energy band (1D)": "energy_band"}
    scale_map = {"Auto": "auto", "Linear": "linear", "Log magnitude": "log_magnitude", "SymLog": "symlog"}
    range_map = {"Robust 1–99%": "robust_1_99", "Robust 1-99%": "robust_1_99", "Full range": "full_range"}
    context = {"display": display_map.get(display, display.lower().replace(" ", "_")), "scale": scale_map.get(scale_mode, scale_mode.lower()),
               "range_mode": range_map.get(range_mode, range_mode.lower().replace(" ", "_")), "fixed_bias": {"vg_v": 3.0, "vd_v": 3.0},
               "shared_color_scale": len(outputs) >= 2, "region_definition_version": "1.0", "visual_evidence_policy": "supplied_evidence_only"}
    payload = build_payload(kind="field", context=context, items=scalar_data, legacy_comparisons=comparisons, warnings=warnings)
    geometry_context, analysis_quality = build_field_geometry_interpretation(outputs)
    regional_summaries, spatial_features, feature_quality = build_common_field_interpretation(outputs, display)
    analysis_quality.update(feature_quality)
    payload.interpretation.update({
        "status": "partial",
        "geometry_context": geometry_context,
        "analysis_quality": analysis_quality,
        "regional_summaries": regional_summaries,
        "spatial_features": spatial_features,
    })
    if display == "Energy band (1D)":
        payload.interpretation["energy_band_profiles"] = [
            {
                "subject_id": f"curve_{index + 1}",
                **item.get("specialized_metrics", {}),
            }
            for index, item in enumerate(scalar_data)
        ]
    payload.interpretation["multi_condition_trends"] = (
        _build_multi_condition_trends(payload)
    )
    field_specific_conclusions = build_field_specific_conclusions(payload)
    payload.interpretation["field_specific_conclusions"] = field_specific_conclusions
    cross_domain_links = build_cross_domain_links(field_specific_conclusions)
    payload.interpretation["cross_domain_links"] = cross_domain_links
    subject_ids = {item["subject_id"] for item in payload.subjects}
    validate_field_geometry_interpretation(geometry_context, analysis_quality, subject_ids)
    validate_common_field_interpretation(regional_summaries, spatial_features, subject_ids)
    for trend in payload.interpretation["multi_condition_trends"]:
        if not set(trend.get("ordered_subject_ids", [])).issubset(subject_ids):
            raise ValueError("Field trend references an unknown subject.")
        if trend.get("direction") not in {
            "stable", "monotonic_increase", "monotonic_decrease",
            "non_monotonic",
        }:
            raise ValueError("Field trend direction is invalid.")
        if trend.get("claim_limit") != "spatial_prediction_only":
            raise ValueError("Field trend claim limit is missing.")
    validate_field_specific_conclusions(field_specific_conclusions, payload)
    validate_cross_domain_links(cross_domain_links, payload)
    validate_analysis_payload(payload)
    return payload
