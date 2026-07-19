from __future__ import annotations

import json
import math
from typing import Any

from .iv_templates import CONCEPT_LABELS, IV_TEMPLATES, METRIC_LABELS, PARAMETER_LABELS, TRADEOFF_TEMPLATES

GROUPS = {
    "switching": ("vth_at_vd_0_05", "vth_at_vd_1_5", "ioff", "ion_ioff_ratio", "ss", "dibl"),
    "drive": ("ion", "gm_max", "ron"),
    "saturation": ("gds", "lambda_clm"),
}
METRIC_PRIORITY = {"dibl": 1.0, "ion": 1.0, "ioff": .95, "ion_ioff_ratio": .95, "ss": .9, "gm_max": .85,
                   "ron": .85, "vth_at_vd_0_05": .8, "vth_at_vd_1_5": .75, "gds": .7, "lambda_clm": .65}
FORBIDDEN = ("증명", "입증", "유일한 원인", "반드시 유발", "완전히 최적", "절대적으로 우수")


def _number(value: Any, unit: str | None = None) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if not math.isfinite(number):
        return "N/A"
    absolute = abs(number)
    text = f"{number:.2e}" if absolute and (absolute >= 1e4 or absolute < 1e-3) else f"{number:.3g}"
    return f"{text} {unit}".strip()


def validate_explanation_response(response: dict[str, Any]) -> dict[str, list[str]]:
    keys = ("descriptions", "comparisons", "tradeoffs", "cautions")
    if set(response) != set(keys):
        raise ValueError("Explanation response must contain exactly four output arrays.")
    result = {}
    for key in keys:
        values = response[key]
        if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
            raise ValueError(f"{key} must be an array of strings.")
        if any(term in sentence for sentence in values for term in FORBIDDEN):
            raise ValueError("Explanation contains forbidden causal wording.")
        result[key] = values
    json.dumps(result, ensure_ascii=False, allow_nan=False)
    return result


def select_evidence_for_rendering(payload: dict[str, Any], comparison_id: str | None = None) -> list[dict[str, Any]]:
    threshold = float(payload.get("output_policy", {}).get("minimum_importance_score", 0.0))
    selection_available = any("selected_for_explanation" in item for item in payload.get("evidence", []))
    selected = [item for item in payload.get("evidence", []) if item.get("eligible_for_output")
                and (not selection_available or item.get("selected_for_explanation"))
                and (selection_available or float(item.get("importance_score", 0)) >= threshold)
                and item.get("source_type") in {"curve_parameter_analyzer", "curve_array_analyzer"}
                and (comparison_id is None and item.get("comparison_id") is None or item.get("comparison_id") == comparison_id)]
    return sorted(selected, key=lambda item: (-float(item.get("importance_score", 0)), -METRIC_PRIORITY.get(item.get("quantity"), 0), item["evidence_id"]))


def group_iv_evidence(evidence: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped = {name: [] for name in GROUPS}; grouped["array"] = []
    for item in evidence:
        if item.get("evidence_type") in {"curve_point_change", "curve_shape_change"}:
            grouped["array"].append(item); continue
        for name, quantities in GROUPS.items():
            if item.get("quantity") in quantities:
                grouped[name].append(item); break
    return grouped


def _join(values: list[str]) -> str:
    return values[0] if len(values) == 1 else ", ".join(values[:-1]) + " 및 " + values[-1]


def _metric_value(item: dict[str, Any], *, numeric: bool) -> str:
    label = METRIC_LABELS.get(item["quantity"], item["quantity"])
    if numeric and item.get("numeric_display", {}).get("allowed"):
        value = item.get("data", {}).get("value")
        if value is not None:
            return f"{label} {_number(value, item.get('data', {}).get('unit'))}"
    return label


def _metric_change(item: dict[str, Any], *, numeric: bool = True) -> str:
    label = METRIC_LABELS.get(item["quantity"], item["quantity"])
    direction = {"increased": "증가", "decreased": "감소", "unchanged": "유사"}.get(item.get("observation"), item.get("observation", "변화"))
    data = item.get("data", {})
    if item["quantity"] in {"ioff", "ion_ioff_ratio"} and numeric and data.get("decade_difference") is not None and abs(float(data["decade_difference"])) >= 1:
        return f"{label} {abs(float(data['decade_difference'])):.1f} decade {direction}"
    if numeric and item.get("numeric_display", {}).get("allowed") and data.get("percent_difference") is not None:
        return f"{label} {abs(float(data['percent_difference'])):.1f}% {direction}"
    return f"{label} {direction}"


def render_iv_single(payload: dict[str, Any]) -> dict[str, list[str]]:
    subjects = payload.get("subjects", []); evidence = select_evidence_for_rendering(payload)
    if not subjects or not evidence:
        return _fallback()
    policy = payload.get("output_policy", {}); grouped = group_iv_evidence(evidence)
    descriptions = [IV_TEMPLATES["single.condition"].format(curve=subjects[0]["display_name"])]
    numeric_budget = 3; used = 0
    for group, key in (("switching", "single.switching"), ("drive", "single.drive"), ("saturation", "single.saturation")):
        chosen = grouped[group][:3 if group == "switching" else 2 if group == "drive" else 2]
        if not chosen: continue
        labels = []
        for item in chosen:
            numeric = used < numeric_budget and group != "saturation"
            rendered = _metric_value(item, numeric=numeric); used += int(numeric and rendered != METRIC_LABELS.get(item["quantity"], item["quantity"]))
            labels.append(rendered)
        descriptions.append(IV_TEMPLATES[key].format(metrics=_join(labels)))
    cautions = [IV_TEMPLATES["caution.single"]]
    if policy.get("include_model_limitation", True): cautions.append(IV_TEMPLATES["caution.model"])
    cautions.extend(_warning_cautions(payload))
    return enforce_output_policy({"descriptions": descriptions, "comparisons": [], "tradeoffs": [], "cautions": cautions}, policy)


def render_condition_sentence(comparison: dict[str, Any], subjects: dict[str, str]) -> str:
    baseline = subjects.get(comparison["baseline_subject_id"], comparison["baseline_subject_id"]); candidate = subjects.get(comparison["candidate_subject_id"], comparison["candidate_subject_id"])
    changes = comparison.get("changed_parameters", [])
    if not changes: return IV_TEMPLATES["condition.same"].format(baseline=baseline, candidate=candidate)
    if len(changes) == 1:
        item = changes[0]; parameter = PARAMETER_LABELS.get(item["parameter"], item["parameter"])
        return IV_TEMPLATES[f"condition.single.{item['direction']}"].format(baseline=baseline, candidate=candidate, parameter=parameter,
                   before=_number(item["baseline"], item.get("unit")), after=_number(item["candidate"], item.get("unit")))
    labels = [PARAMETER_LABELS.get(item["parameter"], item["parameter"]) for item in changes]
    if len(labels) == 2: return IV_TEMPLATES["condition.multi.two"].format(baseline=baseline, candidate=candidate, first=labels[0], second=labels[1])
    return IV_TEMPLATES["condition.multi.many"].format(baseline=baseline, candidate=candidate, parameters=", ".join(labels[:2]))


def render_principle_sentence(payload: dict[str, Any], comparison_id: str) -> str | None:
    relationships = [item for item in payload.get("conclusions", []) if item.get("comparison_id") == comparison_id
                     and item.get("conclusion_type") == "physical_relationship" and item.get("eligible_for_output")]
    rendered = [IV_TEMPLATES.get("principle." + item.get("principle_id", "")) for item in relationships]
    rendered = [item for item in rendered if item]
    return " ".join(rendered[:2]) or None


def render_multi_parameter_principles(payload: dict[str, Any], comparison_id: str) -> list[str]:
    conclusion = next((item for item in payload.get("conclusions", []) if item.get("comparison_id") == comparison_id
                       and item.get("conclusion_type") == "multi_parameter_association"), None)
    if not conclusion: return []
    lines = []
    effects = conclusion.get("parameter_effects", [])
    principle_groups = [item.get("principle_ids", []) for item in effects] if effects else [conclusion.get("principle_ids", [])]
    for principle_ids in principle_groups:
        group = [IV_TEMPLATES.get("multi_principle." + principle_id) for principle_id in principle_ids]
        phrases = list(dict.fromkeys(item for item in group[:2] if item))
        if phrases: lines.append(" ".join(phrases))
    return list(dict.fromkeys(lines))


def render_parameter_interaction(payload: dict[str, Any], comparison_id: str) -> str | None:
    conclusion = next((item for item in payload.get("conclusions", []) if item.get("comparison_id") == comparison_id
                       and item.get("conclusion_type") == "multi_parameter_association"), None)
    if not conclusion: return None
    reinforcing = [METRIC_LABELS.get(item, item) for item in conclusion.get("reinforcing_quantities", [])]
    competing = [METRIC_LABELS.get(item, item) for item in conclusion.get("competing_quantities", [])]
    parts = []
    if reinforcing: parts.append(f"{_join(reinforcing)} 변화에는 두 parameter의 일반적 영향이 같은 방향으로 겹칠 수 있습니다")
    if competing: parts.append(f"{_join(competing)} 변화에는 두 parameter의 일반적 영향이 반대 방향으로 경쟁할 수 있습니다")
    return ". 반면 ".join(parts) + "." if parts else None


def render_dominant_alignment(payload: dict[str, Any], comparison_id: str) -> str | None:
    conclusion = next((item for item in payload.get("conclusions", []) if item.get("comparison_id") == comparison_id
                       and item.get("conclusion_type") == "multi_parameter_association"), None)
    dominant = conclusion.get("dominant_alignment_parameter") if conclusion else None
    if not dominant:
        return None
    other = [item.get("parameter") for item in conclusion.get("parameter_effects", []) if item.get("parameter") != dominant]
    dominant_label = PARAMETER_LABELS.get(dominant, dominant)
    if other:
        other_labels = ", ".join(PARAMETER_LABELS.get(item, item) for item in other)
        return f"최종 관찰 결과는 {other_labels}의 일반적 영향보다 {dominant_label} 변화의 예상 방향과 더 많이 일치했습니다."
    return f"최종 관찰 결과는 {dominant_label} 변화의 일반적 예상 방향과 더 많이 일치했습니다."


def _observation_sentence(payload: dict[str, Any], comparison: dict[str, Any]) -> str | None:
    selected = select_evidence_for_rendering(payload, comparison["comparison_id"]); grouped = group_iv_evidence(selected)
    phrases = []
    for name, maximum in (("switching", 2), ("drive", 2), ("saturation", 2)):
        values = [_metric_change(item) for item in grouped[name][:maximum]]
        if values: phrases.append(_join(values))
    if not phrases and grouped["array"]:
        item = grouped["array"][0]; phrases.append(f"{item.get('data', {}).get('curve_kind', 'Curve')}의 Drain current가 " + ("증가" if item.get("observation") == "increased" else "감소"))
    if not phrases: return None
    prefix = "보조적으로" if comparison.get("comparison_role") == "variant_to_variant" else "이 모델 결과에서"
    merged = phrases[0] if len(phrases) == 1 else ", ".join(phrases[:-1]) + "하고 " + phrases[-1]
    return f"{prefix} {merged}했습니다."


def _consistency_sentence(payload: dict[str, Any], comparison_id: str) -> str | None:
    relationships = [item for item in payload.get("conclusions", []) if item.get("comparison_id") == comparison_id and item.get("conclusion_type") == "physical_relationship" and item.get("eligible_for_output")]
    if not relationships: return None
    item = max(relationships, key=lambda value: value.get("importance_score", 0)); consistency = item.get("physical_consistency")
    if consistency not in {"consistent", "partially_consistent", "inconsistent"}: return None
    return IV_TEMPLATES[f"consistency.{consistency}"].format(concept=CONCEPT_LABELS.get(item.get("target_concept"), item.get("target_concept")))


def render_iv_comparison(payload: dict[str, Any]) -> dict[str, list[str]]:
    comparisons = sorted(payload.get("comparisons", []), key=lambda item: item.get("comparison_order", 0)); subjects = {item["subject_id"]: item["display_name"] for item in payload.get("subjects", [])}
    if not comparisons: return _fallback()
    policy = payload.get("output_policy", {}); descriptions = []
    if len(payload.get("subjects", [])) >= 3:
        descriptions.append("Curve 1을 primary baseline으로 두고 Curve 1→2, Curve 1→3 및 Curve 2→3 순서로 비교했습니다.")
    else:
        descriptions.append(render_condition_sentence(comparisons[0], subjects))
        if policy.get("include_general_physical_principle", True) and comparisons[0].get("effective_claim_level") != "descriptive_only":
            if comparisons[0].get("effective_claim_level") == "multi_parameter_association":
                descriptions.extend(render_multi_parameter_principles(payload, comparisons[0]["comparison_id"]))
            else:
                principle = render_principle_sentence(payload, comparisons[0]["comparison_id"])
                if principle: descriptions.append(principle)
    lines = []
    for comparison in comparisons:
        no_difference = any(item.get("comparison_id") == comparison["comparison_id"] and item.get("conclusion_type") == "no_meaningful_difference" for item in payload.get("conclusions", []))
        if no_difference:
            lines.append(IV_TEMPLATES["comparison.no_difference"].format(baseline=subjects[comparison["baseline_subject_id"]], candidate=subjects[comparison["candidate_subject_id"]])); continue
        observation = _observation_sentence(payload, comparison)
        if len(payload.get("subjects", [])) >= 3:
            condition = render_condition_sentence(comparison, subjects)
            lines.append(condition + (" " + observation if observation else ""))
        elif observation:
            lines.append(observation)
        interaction = render_parameter_interaction(payload, comparison["comparison_id"])
        if interaction and len(payload.get("subjects", [])) < 3: lines.append(interaction)
        alignment = render_dominant_alignment(payload, comparison["comparison_id"])
        if alignment and len(payload.get("subjects", [])) < 3: lines.append(alignment)
        consistency = _consistency_sentence(payload, comparison["comparison_id"])
        if consistency and comparison.get("comparison_role") != "variant_to_variant" and len(payload.get("subjects", [])) < 3: lines.append(consistency)
    for conclusion in payload.get("conclusions", []):
        if conclusion.get("conclusion_type") == "variant_effect_comparison" and conclusion.get("eligible_for_output"):
            lines.append(f"{METRIC_LABELS.get(conclusion['quantity'], conclusion['quantity'])} 변화는 {conclusion['larger_effect_comparison_id']}에서 더 크게 나타났습니다.")
    tradeoffs = [render_tradeoff_sentence(item) for item in payload.get("conclusions", []) if item.get("conclusion_type") == "tradeoff" and item.get("eligible_for_output")]
    cautions = _warning_cautions(payload)
    if any(item.get("effective_claim_level") == "multi_parameter_association" for item in comparisons): cautions.insert(0, IV_TEMPLATES["caution.multiple"])
    if policy.get("include_model_limitation", True): cautions.append(IV_TEMPLATES["caution.model"])
    response = {"descriptions": descriptions, "comparisons": lines, "tradeoffs": tradeoffs, "cautions": cautions}
    if not lines and not tradeoffs: return _fallback(policy)
    return enforce_output_policy(response, policy)


def render_tradeoff_sentence(conclusion: dict[str, Any]) -> str:
    if conclusion.get("label") in TRADEOFF_TEMPLATES:
        return TRADEOFF_TEMPLATES[conclusion["label"]]
    positive = conclusion.get("positive_aspects") or conclusion.get("positive_quantities") or []
    negative = conclusion.get("negative_aspects") or conclusion.get("negative_quantities") or []
    if positive and negative: return f"{_join(list(map(str, positive)))}은 개선 방향을 보였지만 {_join(list(map(str, negative)))}은 저하되어 Trade-off가 나타났습니다."
    return "서로 다른 성능 지표가 반대 방향으로 변해 Trade-off가 나타났습니다."


def _warning_cautions(payload: dict[str, Any]) -> list[str]:
    types = {item.get("warning_type") for item in payload.get("warnings", []) if item.get("eligible_for_output", True)}; cautions = []
    if "extrapolation" in types: cautions.append(IV_TEMPLATES["caution.extrapolation"])
    if types & {"invalid_numeric_value", "parameter_extraction_failed", "missing_data", "insufficient_curve_points"}: cautions.append(IV_TEMPLATES["caution.invalid"])
    return cautions


def deduplicate_sentences(response: dict[str, list[str]]) -> dict[str, list[str]]:
    seen = set(); result = {}
    for key, sentences in response.items():
        result[key] = []
        for sentence in sentences:
            normalized = " ".join(sentence.split())
            if normalized and normalized not in seen:
                seen.add(normalized); result[key].append(normalized)
    return result


def enforce_output_policy(response: dict[str, list[str]], policy: dict[str, Any]) -> dict[str, list[str]]:
    response = deduplicate_sentences(response)
    limits = {"descriptions": int(policy.get("max_descriptions", 4)), "comparisons": int(policy.get("max_comparisons", 3)),
              "tradeoffs": int(policy.get("max_tradeoffs", 1)), "cautions": int(policy.get("max_cautions", 2))}
    result = {key: response.get(key, [])[:limit] for key, limit in limits.items()}
    maximum = int(policy.get("max_total_sentences", sum(limits.values())))
    while sum(map(len, result.values())) > maximum:
        for key in ("comparisons", "descriptions", "tradeoffs", "cautions"):
            if len(result[key]) > (1 if key in {"descriptions", "cautions"} else 0):
                result[key].pop(); break
        else: break
    return validate_explanation_response(result)


def _fallback(policy: dict[str, Any] | None = None) -> dict[str, list[str]]:
    response = {"descriptions": [IV_TEMPLATES["fallback.description"]], "comparisons": [], "tradeoffs": [], "cautions": [IV_TEMPLATES["fallback.caution"]]}
    return enforce_output_policy(response, policy or {})


def render_iv_explanation(payload: dict[str, Any]) -> dict[str, list[str]]:
    try:
        response = render_iv_single(payload) if payload.get("analysis_type") == "iv_curve_single" else render_iv_comparison(payload)
        return validate_explanation_response(response)
    except (KeyError, TypeError, ValueError, OverflowError):
        return _fallback(payload.get("output_policy", {}))
