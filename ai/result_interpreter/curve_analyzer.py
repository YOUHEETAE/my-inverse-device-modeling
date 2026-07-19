from __future__ import annotations

import math
from itertools import combinations

import numpy as np

from ai.curve_model.inference import CurvePrediction, extract_electrical_parameters, range_warning

from .payload_builders import build_payload
from .schemas import AnalysisPayload


METRICS = {
    "vth_low_v": ("Vth (Vd=0.05 V)", "V", 1.0, "context_dependent"),
    "vth_high_v": ("Vth (Vd=1.5 V)", "V", 1.0, "context_dependent"),
    "ion_ma_per_um": ("Ion", "mA/µm", 1.0, "higher_is_better"),
    "ioff_ma_per_um": ("Ioff", "mA/µm", 1.0, "lower_is_better"),
    "ion_ioff_ratio": ("Ion/Ioff", "ratio", 1.0, "higher_is_better"),
    "ss_mv_per_dec": ("SS", "mV/dec", 1.0, "lower_is_better"),
    "dibl_gm_v_per_v": ("DIBL", "mV/V", 1000.0, "lower_is_better"),
    "gm_max_ms_per_um": ("gm max", "mS/µm", 1.0, "higher_is_better"),
    "gds_ms_per_um": ("gds", "mS/µm", 1.0, "lower_is_better"),
    "ron_kohm_um": ("Ron", "kΩ·µm", 1.0, "lower_is_better"),
    "lambda_per_v": ("λ (CLM)", "1/V", 1.0, "lower_is_better"),
}

PARAMETER_PRINCIPLES = {
    "L": {
        "name": "Channel length (L)",
        "increase": "Channel length가 길어지면 일반적으로 short-channel effect와 DIBL은 완화될 수 있지만, channel resistance 증가로 Ion과 gm이 감소하고 Ron이 증가할 수 있다.",
        "decrease": "Channel length가 짧아지면 일반적으로 drive current는 증가할 수 있지만 short-channel effect, DIBL, Ioff가 커질 수 있다.",
    },
    "T": {
        "name": "Oxide thickness (Tox)",
        "increase": "Tox가 두꺼워지면 gate-to-channel electrostatic coupling이 약해져 gm과 drive current가 감소하고 SS 및 Vth 특성이 변할 수 있다.",
        "decrease": "Tox가 얇아지면 gate control이 강해져 gm, SS, short-channel control이 개선될 수 있지만 oxide field와 gate leakage 측면의 Trade-off를 고려해야 한다.",
    },
    "B": {
        "name": "Bulk doping (B)",
        "increase": "Bulk doping이 증가하면 depletion width가 감소하고 Vth와 short-channel control이 변할 수 있으며, mobility와 junction leakage에도 영향을 줄 수 있다.",
        "decrease": "Bulk doping이 감소하면 depletion width가 커지고 Vth와 electrostatic control이 변할 수 있으며, mobility·leakage 특성과 Trade-off가 발생할 수 있다.",
    },
    "SD": {
        "name": "Source/Drain doping (SD)",
        "increase": "Source/Drain doping이 증가하면 series resistance가 감소해 Ion과 drive performance가 증가할 수 있지만 junction field와 leakage가 변할 수 있다.",
        "decrease": "Source/Drain doping이 감소하면 series resistance가 증가해 Ion이 감소할 수 있지만 junction field와 leakage 측면은 완화될 수 있다.",
    },
    "LDD": {
        "name": "LDD doping",
        "increase": "LDD doping이 증가하면 extension resistance가 감소해 drive current가 증가할 수 있지만 drain-side electric field 분포와 leakage에 Trade-off가 생길 수 있다.",
        "decrease": "LDD doping이 감소하면 drain-side peak field를 완화할 수 있지만 extension resistance 증가로 Ion과 gm이 감소할 수 있다.",
    },
}


def _finite(value: float) -> float | None:
    return float(value) if math.isfinite(float(value)) else None


def _assessment(delta: float, preference: str) -> str:
    if delta == 0 or preference == "context_dependent":
        return "neutral_or_context_dependent"
    improved = delta > 0 if preference == "higher_is_better" else delta < 0
    return "improved" if improved else "degraded"


def _parameter_changes(baseline: dict[str, float], candidate: dict[str, float]) -> dict[str, dict[str, float | str | None]]:
    changes = {}
    for name in baseline:
        before, after = baseline[name], candidate[name]
        if before == after:
            continue
        changes[name] = {
            "baseline": before, "candidate": after, "absolute": after - before,
            "percent": None if before == 0 else (after - before) / abs(before) * 100.0,
            "direction": "increased" if after > before else "decreased",
            "physical_name": PARAMETER_PRINCIPLES[name]["name"],
            "general_principle": PARAMETER_PRINCIPLES[name]["increase" if after > before else "decrease"],
        }
    return changes


def _current_changes(baseline: CurvePrediction, candidate: CurvePrediction) -> list[dict[str, object]]:
    summaries = []
    for bias_index, bias in enumerate(baseline.fixed_biases):
        matches = np.flatnonzero(np.isclose(candidate.fixed_biases, bias, rtol=0.0, atol=1e-6))
        if not len(matches) or baseline.currents.shape[1] != candidate.currents.shape[1]:
            continue
        before = np.asarray(baseline.currents[bias_index], dtype=float)
        after = np.asarray(candidate.currents[int(matches[0])], dtype=float)
        end_before, end_after = float(before[-1]), float(after[-1])
        summaries.append({
            "fixed_bias_V": float(bias),
            "end_current_baseline_mA_per_um": end_before,
            "end_current_candidate_mA_per_um": end_after,
            "end_current_percent_change": None if end_before == 0 else (end_after - end_before) / abs(end_before) * 100.0,
            "max_absolute_curve_difference_mA_per_um": float(np.max(np.abs(after - before))),
        })
    return summaries


def build_curve_payload(
    results: list[tuple[str, CurvePrediction, CurvePrediction]],
    configs: list[dict[str, str]],
) -> AnalysisPayload:
    items: list[dict[str, object]] = []
    warnings: list[str] = []
    for (label, idvd, idvg), config in zip(results, configs, strict=True):
        electrical = extract_electrical_parameters(idvd, idvg)
        ioff = electrical.get("ioff_ma_per_um", 0.0)
        if ioff and ioff > 0:
            electrical["ion_ioff_ratio"] = electrical.get("ion_ma_per_um", 0.0) / ioff
        else:
            electrical["ion_ioff_ratio"] = math.nan
            warnings.append(f"{label}: zero_denominator for Ion/Ioff")
            warnings.append(f"{label}: nonpositive_log_input for Ion/Ioff")
        formatted = {}
        for name, (display_name, unit, factor, preference) in METRICS.items():
            value = _finite(electrical.get(name, math.nan) * factor)
            formatted[name] = {"name": display_name, "value": value, "unit": unit, "preference": preference}
            if value is None:
                warnings.append(f"{label}: parameter_extraction_failed for {name}")
        items.append({
            "label": label,
            "device_parameters": {name: float(value) for name, value in config.items()},
            "electrical_parameters": formatted,
        })
        warning = range_warning(config)
        if warning:
            warnings.append(f"{label}: {warning}")
    comparisons: list[dict[str, object]] = []
    if len(items) >= 2:
        for baseline_index, candidate_index in combinations(range(len(items)), 2):
            baseline_item, item = items[baseline_index], items[candidate_index]
            baseline = baseline_item["electrical_parameters"]
            changes = {}
            assessments = {"improved": [], "degraded": [], "neutral_or_context_dependent": []}
            for name, metric in item["electrical_parameters"].items():
                base_metric = baseline.get(name, {})
                base, value = base_metric.get("value"), metric.get("value")
                if base is None or value is None:
                    continue
                assessment = _assessment(value - base, metric["preference"])
                assessments[assessment].append(metric["name"])
                changes[name] = {
                    "name": metric["name"], "unit": metric["unit"],
                    "baseline": base, "candidate": value,
                    "absolute": value - base,
                    "percent": None if base == 0 else (value - base) / abs(base) * 100.0,
                    "preference": metric["preference"], "assessment": assessment,
                }
            device_changes = _parameter_changes(baseline_item["device_parameters"], item["device_parameters"])
            comparisons.append({
                "baseline": baseline_item["label"], "candidate": item["label"],
                "comparison_role": "primary_baseline_to_variant" if baseline_index == 0 else "variant_to_variant",
                "device_parameter_changes": device_changes,
                "is_single_parameter_controlled_comparison": len(device_changes) == 1,
                "current_curve_changes": {
                    "IdVd": _current_changes(results[baseline_index][1], results[candidate_index][1]),
                    "IdVg": _current_changes(results[baseline_index][2], results[candidate_index][2]),
                },
                "electrical_parameter_changes": changes,
                "assessment_groups": assessments,
                "has_trade_off": bool(assessments["improved"] and assessments["degraded"]),
            })
    mode = "single" if len(items) == 1 else "comparison"
    context = {"mode": mode, "language": "Korean", "technical_terms": "English", "comparison_order": "all pairwise comparisons in selected-curve order", "primary_baseline": items[0]["label"] if items else None, "evaluation_basis": "general device-performance direction; LLM must read supplied assessments rather than judge them"}
    context = {"curve_kinds": ["idvd", "idvg"], "current_unit": "mA/um",
               "evaluation_basis": "descriptive_only" if mode == "single" else "predefined_device_performance_preferences"}
    return build_payload(kind="iv_curve", context=context, items=items, legacy_comparisons=comparisons, warnings=warnings)
