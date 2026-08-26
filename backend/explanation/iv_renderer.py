from __future__ import annotations

import json
import math
from typing import Any

from .iv_templates import (CONCEPT_LABELS, IV_TEMPLATES, METRIC_LABELS,
                           PARAMETER_LABELS, PERFORMANCE_AREA_LABELS,
                           TRADEOFF_TEMPLATES)
from .physical_principles import PHYSICAL_PRINCIPLES
from .tradeoff_policy import select_observed_tradeoffs_for_output

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


def _eligible_iv_evidence(payload: dict[str, Any], comparison_id: str | None = None) -> list[dict[str, Any]]:
    eligible = [
        item for item in payload.get("evidence", [])
        if item.get("eligible_for_output")
        and item.get("source_type") in {"curve_parameter_analyzer", "curve_array_analyzer"}
        and item.get("comparison_id") == comparison_id
        and "physically_ambiguous_sign" not in item.get("suppression_reasons", [])
    ]
    return sorted(
        eligible,
        key=lambda item: (
            -METRIC_PRIORITY.get(item.get("quantity"), 0),
            -float(item.get("importance_score", 0)),
            item["evidence_id"],
        ),
    )


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
    if (
        item["quantity"] in {"vth_at_vd_0_05", "vth_at_vd_1_5"}
        and numeric
        and item.get("numeric_display", {}).get("allowed")
        and data.get("baseline") is not None
        and data.get("candidate") is not None
        and data.get("absolute_difference") is not None
    ):
        unit = data.get("unit") or "V"
        return (
            f"{label} {_number(data['baseline'], unit)}→"
            f"{_number(data['candidate'], unit)} "
            f"({_number(abs(float(data['absolute_difference'])), unit)} {direction})"
        )
    if item["quantity"] in {"ioff", "ion_ioff_ratio"} and numeric and data.get("decade_difference") is not None and abs(float(data["decade_difference"])) >= 1:
        return f"{label} {abs(float(data['decade_difference'])):.1f} decade {direction}"
    if numeric and item.get("numeric_display", {}).get("allowed") and data.get("percent_difference") is not None:
        return f"{label} {abs(float(data['percent_difference'])):.1f}% {direction}"
    return f"{label} {direction}"


def render_iv_single(payload: dict[str, Any]) -> dict[str, list[str]]:
    subjects = payload.get("subjects", []); evidence = _eligible_iv_evidence(payload)
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
    if any("physically_ambiguous_sign" in item.get("suppression_reasons", []) for item in payload.get("evidence", [])):
        cautions.append("DIBL 부호가 일반적인 barrier-lowering 정의와 일치하지 않아 해당 값은 해설에서 제외했습니다.")
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
    rendered = []
    for item in changes:
        parameter = PARAMETER_LABELS.get(item["parameter"], item["parameter"])
        direction = "증가" if item["direction"] == "increased" else "감소"
        rendered.append(f"{parameter} {_number(item['baseline'], item.get('unit'))}→{_number(item['candidate'], item.get('unit'))} {direction}")
    return f"{baseline} 대비 {candidate}에서는 {_join(rendered)}가 함께 변경되었습니다."


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
        group = [
            IV_TEMPLATES.get("multi_principle." + principle_id)
            or IV_TEMPLATES.get("principle." + principle_id)
            for principle_id in principle_ids
        ]
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


def _interpretation_maps(payload: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    interpretation = payload.get("interpretation", {})
    summaries = {item["summary_id"]: item for item in interpretation.get("performance_summaries", [])}
    evidence = {item["evidence_id"]: item for item in payload.get("evidence", [])}
    overall = {item["comparison_id"]: item for item in (interpretation.get("overall_assessment") or {}).get("comparison_results", [])}
    return summaries, evidence, overall


def _structured_area_sentence(summary: dict[str, Any], evidence_by_id: dict[str, dict[str, Any]], candidate: str) -> str | None:
    area = summary["performance_area"]
    if area not in {"off_state_control", "short_channel_control", "subthreshold_behavior", "drive_performance", "saturation_behavior"}:
        return None
    items = [evidence_by_id[item] for item in summary.get("evidence_ids", []) if item in evidence_by_id]
    items = [item for item in items if item.get("magnitude_class") != "negligible" and "physically_ambiguous_sign" not in item.get("suppression_reasons", [])]
    items.sort(key=lambda item: (-METRIC_PRIORITY.get(item.get("quantity"), 0), -float(item.get("importance_score", 0))))
    if not items:
        if summary.get("assessment") == "unchanged":
            return IV_TEMPLATES["structured.area.unchanged"].format(candidate=candidate, area=PERFORMANCE_AREA_LABELS.get(area, area))
        return None
    metrics = _join([_metric_change(item) for item in items[:2]])
    return IV_TEMPLATES[f"structured.area.{area}"].format(candidate=candidate, metrics=metrics)


def _structured_interaction_sentence(payload: dict[str, Any], comparison_id: str) -> str | None:
    sentences = _structured_interaction_sentences(payload, comparison_id, maximum=1)
    return sentences[0] if sentences else None


def _structured_interaction_sentences(
    payload: dict[str, Any],
    comparison_id: str,
    *,
    maximum: int = 2,
) -> list[str]:
    interactions = [item for item in payload.get("interpretation", {}).get("parameter_interactions", [])
                    if item.get("comparison_id") == comparison_id and item.get("quantity") and item.get("observed_direction") in {"increased", "decreased"}]
    interactions.sort(key=lambda item: (-METRIC_PRIORITY.get(item.get("quantity"), 0), item["interaction_id"]))
    if not interactions:
        return []
    rendered = []
    used_types = set()
    for item in interactions:
        if item.get("interaction_type") in used_types:
            continue
        metric = METRIC_LABELS.get(item["quantity"], item["quantity"])
        observed = "증가" if item["observed_direction"] == "increased" else "감소"
        parameters = [PARAMETER_LABELS.get(value["parameter"], value["parameter"]) for value in item.get("contributors", [])]
        joined = _join(parameters)
        if item["interaction_type"] == "reinforcing":
            rendered.append(
                f"{metric}에 대해서는 {joined}의 일반적 영향이 같은 {observed} 방향으로 겹칠 수 있고, "
                f"이번 모델에서는 {observed}가 관찰됐습니다."
            )
        elif item["interaction_type"] == "competing":
            rendered.append(
                f"{metric}에 대해서는 {joined}의 일반적 영향이 서로 경쟁할 수 있으며, "
                f"이번 모델에서는 최종적으로 {observed}가 관찰됐습니다."
            )
        else:
            continue
        used_types.add(item.get("interaction_type"))
        if len(rendered) >= maximum:
            break
    return rendered


def _structured_mechanism_sentences(
    payload: dict[str, Any],
    comparison_id: str,
    evidence_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    chains = [
        item
        for item in payload.get("interpretation", {}).get("mechanism_chains", [])
        if item.get("comparison_id") == comparison_id
        and item.get("alignment") == "consistent"
    ]
    chains.sort(key=lambda item: (int(item.get("priority", 99)), item.get("mechanism_id", "")))
    rendered: list[str] = []
    used_quantities: set[str] = set()
    for chain in chains:
        mechanism_key = "mechanism." + str(chain.get("mechanism_key", ""))
        template = (
            IV_TEMPLATES.get(
                mechanism_key + "." + str(chain.get("change_direction", ""))
            )
            or IV_TEMPLATES.get(mechanism_key)
        )
        if not template:
            continue
        linked = [
            evidence_by_id[item["evidence_id"]]
            for item in chain.get("observed_metric_links", [])
            if item.get("evidence_id") in evidence_by_id
            and item.get("quantity") not in used_quantities
        ]
        linked.sort(
            key=lambda item: (
                -METRIC_PRIORITY.get(item.get("quantity"), 0),
                -float(item.get("importance_score", 0)),
            )
        )
        if not linked:
            continue
        chosen = linked[:3]
        used_quantities.update(item["quantity"] for item in chosen)
        rendered.append(
            template.format(metrics=_join([_metric_change(item) for item in chosen]))
        )
    return rendered


def _structured_overall_sentence(result: dict[str, Any], comparison: dict[str, Any], subjects: dict[str, str]) -> str:
    pattern = result.get("result_pattern", "insufficient_for_overall_assessment")
    key = "structured.overall." + pattern
    template = IV_TEMPLATES.get(key, IV_TEMPLATES["structured.overall.insufficient_for_overall_assessment"])
    return template.format(baseline=subjects[comparison["baseline_subject_id"]], candidate=subjects[comparison["candidate_subject_id"]])


def _comparison_mode(payload: dict[str, Any], comparison: dict[str, Any]) -> str:
    mode = payload.get("comparison_plan", {}).get("analysis_mode")
    if mode in {"controlled_pair", "compound_pair"}:
        return mode
    return "compound_pair" if comparison.get("changed_parameter_count", 0) > 1 else "controlled_pair"


def _comparison_curve_focus(
    payload: dict[str, Any],
    comparison_id: str,
    candidate: str,
    *,
    maximum: int = 2,
) -> list[str]:
    items = _eligible_iv_evidence(payload, comparison_id)
    by_quantity = {item.get("quantity"): item for item in items}
    lines = []

    switching = []
    ss = by_quantity.get("ss")
    if ss:
        shape = "더 완만해지고 한 decade 변화에 필요한 Gate 전압 폭이 커진" if ss.get("observation") == "increased" else "더 가팔라지고 한 decade 변화에 필요한 Gate 전압 폭이 작아진"
        switching.append(f"log(Id)-Vg의 subthreshold 구간이 {shape} 모습({_metric_change(ss)})")
    dibl = by_quantity.get("dibl")
    if dibl:
        separation = "커진" if dibl.get("observation") == "increased" else "작아진"
        switching.append(
            "Vth(low)와 Vth(high)의 간격이 "
            f"{separation} 모습({_metric_change(dibl)})"
        )
    ioff = by_quantity.get("ioff")
    if ioff and len(switching) < 2:
        switching.append(f"정의된 off-bias에서의 누설 전류 차이({_metric_change(ioff)})")
    if switching:
        lines.append(f"{candidate}의 switching 변화는 " + _join(switching[:2]) + "에서 확인할 수 있습니다.")

    drive = []
    ion = by_quantity.get("ion")
    if ion:
        drive.append(f"Id-Vg의 정의된 on-bias 전류({_metric_change(ion)})")
    gm = by_quantity.get("gm_max")
    if gm:
        drive.append(f"Id-Vg에서 가장 가파른 구간의 기울기({_metric_change(gm)})")
    ron = by_quantity.get("ron")
    if ron and len(drive) < 2:
        drive.append(f"낮은 Drain voltage Id-Vd 선형 구간의 기울기({_metric_change(ron)})")
    if drive:
        lines.append(f"{candidate}의 drive 변화는 " + _join(drive[:2]) + "에서 확인할 수 있습니다.")
    saturation = []
    gds = by_quantity.get("gds")
    lambda_clm = by_quantity.get("lambda_clm")
    if gds:
        saturation.append(f"Id-Vd 고전압 구간의 잔류 기울기({_metric_change(gds)})")
    if lambda_clm:
        saturation.append(f"saturation 이후 전류 증가 민감도({_metric_change(lambda_clm)})")
    if saturation:
        lines.append(
            f"{candidate}의 saturation 변화는 "
            + _join(saturation[:2])
            + "에서 확인할 수 있습니다."
        )
    return lines[:maximum]


def _controlled_experiment_sentence(comparison: dict[str, Any], subjects: dict[str, str]) -> str | None:
    changes = comparison.get("changed_parameters", [])
    if len(changes) < 2:
        return None
    baseline = subjects.get(comparison["baseline_subject_id"], comparison["baseline_subject_id"])
    experiments = []
    for item in changes:
        parameter = PARAMETER_LABELS.get(item["parameter"], item["parameter"])
        experiments.append(f"{parameter}만 {_number(item['candidate'], item.get('unit'))}로 바꾼 조건")
    return (
        f"개별 기여를 분리하려면 {baseline}을 기준으로 나머지 조건을 고정하고 "
        f"{_join(experiments)}을 각각 추가해 비교해야 합니다"
    )


def _structured_tradeoff_sentence(item: dict[str, Any]) -> str | None:
    if item.get("tradeoff_type") == "mechanism_supported_tradeoff":
        return TRADEOFF_TEMPLATES.get(str(item.get("result_pattern")))
    return IV_TEMPLATES.get("structured.tradeoff." + str(item.get("result_pattern")))


def _structured_caution(
    payload: dict[str, Any],
    comparisons: list[dict[str, Any]],
    subjects: dict[str, str] | None = None,
) -> str:
    parts = []
    if any(item.get("changed_parameter_count", 0) > 1 for item in comparisons):
        parts.append("여러 parameter가 동시에 변경되어 각 parameter의 개별 기여도를 현재 비교만으로 분리해 단정할 수 없습니다")
        if subjects and len(comparisons) == 1:
            experiment = _controlled_experiment_sentence(comparisons[0], subjects)
            if experiment:
                parts.append(experiment)
    if any("physically_ambiguous_sign" in item.get("suppression_reasons", []) for item in payload.get("evidence", [])):
        parts.append("DIBL 부호가 일반적인 barrier-lowering 정의와 일치하지 않아 해당 값은 성능 방향 판정에서 제외했습니다")
    warning_types = {item.get("warning_type") for item in payload.get("warnings", [])}
    if "extrapolation" in warning_types:
        parts.append("학습 범위를 벗어난 조건은 참고 경향으로 제한해 해석해야 합니다")
    if not parts:
        parts.append("이 결과는 학습 모델의 prediction이며 실제 측정 또는 TCAD 검증을 대체하지 않습니다")
    return ". 또한 ".join(parts) + "."


def _structured_two_curve(payload: dict[str, Any], comparisons: list[dict[str, Any]], subjects: dict[str, str]) -> dict[str, list[str]]:
    comparison = comparisons[0]; comparison_id = comparison["comparison_id"]
    summaries, evidence_by_id, overall = _interpretation_maps(payload)
    mode = _comparison_mode(payload, comparison)
    descriptions = [render_condition_sentence(comparison, subjects)]
    if mode == "compound_pair":
        descriptions.extend(render_multi_parameter_principles(payload, comparison_id))
    else:
        principle = render_principle_sentence(payload, comparison_id)
        if principle: descriptions.append(principle)
    comparison_summaries = {item["performance_area"]: item for item in summaries.values() if item["comparison_id"] == comparison_id}
    candidate = subjects[comparison["candidate_subject_id"]]
    lines = []
    if mode == "controlled_pair":
        lines.extend(_structured_mechanism_sentences(
            payload, comparison_id, evidence_by_id,
        )[:3])
        lines.extend(_comparison_curve_focus(payload, comparison_id, candidate, maximum=2))
    else:
        area_order = ("off_state_control", "drive_performance", "short_channel_control", "subthreshold_behavior", "saturation_behavior")
        for area in area_order:
            if area not in comparison_summaries: continue
            sentence = _structured_area_sentence(comparison_summaries[area], evidence_by_id, candidate)
            if sentence: lines.append(sentence)
            if len(lines) >= 2: break
        lines.extend(_structured_interaction_sentences(payload, comparison_id, maximum=2))
        lines.extend(_comparison_curve_focus(payload, comparison_id, candidate, maximum=1))
    if not lines:
        area_order = ("off_state_control", "drive_performance", "short_channel_control", "subthreshold_behavior", "saturation_behavior")
        for area in area_order:
            if area not in comparison_summaries: continue
            sentence = _structured_area_sentence(comparison_summaries[area], evidence_by_id, candidate)
            if sentence: lines.append(sentence)
            if len(lines) >= 4: break
    if comparison_id in overall: lines.append(_structured_overall_sentence(overall[comparison_id], comparison, subjects))
    tradeoffs = []
    candidates = [item for item in payload.get("interpretation", {}).get("observed_tradeoffs", []) if item.get("comparison_id") == comparison_id]
    candidates.sort(key=lambda item: 0 if item.get("tradeoff_type") == "mechanism_supported_tradeoff" else 1)
    for item in candidates:
        sentence = _structured_tradeoff_sentence(item)
        if sentence: tradeoffs.append(sentence); break
    response = {"descriptions": descriptions, "comparisons": lines, "tradeoffs": tradeoffs,
                "cautions": [_structured_caution(payload, comparisons, subjects)]}
    return enforce_output_policy(response, payload.get("output_policy", {}))


def _compact_multi_sentence(payload: dict[str, Any], comparison: dict[str, Any], subjects: dict[str, str], overall: dict[str, Any], summaries: dict[str, dict[str, Any]], evidence: dict[str, dict[str, Any]]) -> str:
    condition = render_condition_sentence(comparison, subjects)
    parts = []
    for area in ("off_state_control", "drive_performance"):
        summary = next((item for item in summaries.values() if item["comparison_id"] == comparison["comparison_id"] and item["performance_area"] == area), None)
        if not summary: continue
        items = [evidence[item] for item in summary.get("evidence_ids", []) if item in evidence and evidence[item].get("magnitude_class") != "negligible"]
        items.sort(key=lambda item: -METRIC_PRIORITY.get(item.get("quantity"), 0))
        if items: parts.append(_join([_metric_change(item) for item in items[:1]]))
    observed = (" 관찰 결과, " + _join(parts) + "했습니다.") if parts else ""
    final = (" " + _structured_overall_sentence(overall[comparison["comparison_id"]], comparison, subjects)) if comparison["comparison_id"] in overall else ""
    return condition + observed + final


def _ranking_sentence(ranking: dict[str, Any], subjects: dict[str, str]) -> str | None:
    best_id = ranking.get("best_candidate_subject_id")
    if not best_id: return None
    best = next(item for item in ranking["variants"] if item["candidate_subject_id"] == best_id)
    area = PERFORMANCE_AREA_LABELS.get(ranking["performance_area"], ranking["performance_area"])
    candidate = subjects.get(best_id, best_id)
    if best["assessment"] == "improved": return f"{area} 개선 폭은 {candidate}에서 가장 크게 나타났습니다."
    if best["assessment"] == "degraded": return f"모든 variant에서 {area}가 저하됐으며, 그 손실은 {candidate}에서 상대적으로 작았습니다."
    if best["assessment"] == "unchanged": return f"{candidate}의 {area}는 baseline과 가장 유사하게 유지됐습니다."
    return f"{area} 비교에서는 {candidate}가 상대적으로 가장 유리한 결과를 보였습니다."


def _trend_direction(values: list[float]) -> str:
    if len(values) < 2:
        return "insufficient"
    scale = max(1.0, *(abs(value) for value in values))
    tolerance = scale * 1e-9
    steps = [
        1 if right - left > tolerance else -1 if left - right > tolerance else 0
        for left, right in zip(values, values[1:])
    ]
    nonzero = {step for step in steps if step}
    if not nonzero:
        return "unchanged"
    if nonzero == {1}:
        return "increased"
    if nonzero == {-1}:
        return "decreased"
    return "non_monotonic"


def _sweep_metric_trends(payload: dict[str, Any]) -> dict[str, str]:
    plan = payload.get("comparison_plan", {})
    ordered_subjects = plan.get("sweep_subject_ids", [])
    values_by_quantity: dict[str, dict[str, float]] = {}
    for item in _eligible_iv_evidence(payload):
        subject_ids = item.get("subject_ids", [])
        value = item.get("data", {}).get("value")
        if len(subject_ids) != 1 or value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(numeric):
            continue
        values_by_quantity.setdefault(str(item.get("quantity")), {})[subject_ids[0]] = numeric
    result = {}
    for quantity, by_subject in values_by_quantity.items():
        if all(subject_id in by_subject for subject_id in ordered_subjects):
            result[quantity] = _trend_direction(
                [by_subject[subject_id] for subject_id in ordered_subjects]
            )
    return result


def _trend_phrase(quantity: str, direction: str) -> str:
    label = METRIC_LABELS.get(quantity, quantity)
    suffix = {
        "increased": "지속 증가",
        "decreased": "지속 감소",
        "unchanged": "현재 유의 수준에서 유사",
        "non_monotonic": "중간 조건에서 방향이 바뀌는 비단조 변화",
    }.get(direction, "추세 판단 불가")
    return f"{label}: {suffix}"


def _sweep_condition(payload: dict[str, Any], subjects: dict[str, str]) -> str:
    plan = payload.get("comparison_plan", {})
    parameter = PARAMETER_LABELS.get(plan.get("sweep_parameter"), plan.get("sweep_parameter", "parameter"))
    unit = {
        "channel_length": "nm",
        "oxide_thickness": "nm",
        "bulk_doping": "cm^-3",
        "source_drain_doping": "cm^-3",
        "ldd_doping": "cm^-3",
    }.get(plan.get("sweep_parameter"), "")
    ordered = [
        f"{_number(value, unit)} ({subjects.get(subject_id, subject_id)})"
        for subject_id, value in zip(
            plan.get("sweep_subject_ids", []),
            plan.get("sweep_values", []),
        )
    ]
    return (
        f"{parameter}만 변화한 controlled sweep이며, "
        f"{' → '.join(ordered)} 순서로 정렬해 추세를 분석했습니다."
    )


def _sweep_principle(payload: dict[str, Any]) -> str | None:
    plan = payload.get("comparison_plan", {})
    parameter = plan.get("sweep_parameter")
    values = plan.get("sweep_values", [])
    if not parameter or len(values) < 2:
        return None
    direction = "increased" if values[-1] > values[0] else "decreased"
    principle_ids = [
        item.get("principle_id")
        for item in PHYSICAL_PRINCIPLES.get((parameter, direction), [])
    ]
    rendered = [
        IV_TEMPLATES.get("principle." + str(principle_id))
        or IV_TEMPLATES.get("multi_principle." + str(principle_id))
        for principle_id in principle_ids
    ]
    return " ".join(item for item in rendered[:2] if item) or None


def _sweep_tradeoff(trends: dict[str, str]) -> str | None:
    preferences = {
        "ion": "increased", "ion_ioff_ratio": "increased", "gm_max": "increased",
        "ioff": "decreased", "dibl": "decreased", "ss": "decreased",
        "ron": "decreased", "gds": "decreased", "lambda_clm": "decreased",
    }
    improved = [
        METRIC_LABELS.get(quantity, quantity)
        for quantity, direction in trends.items()
        if direction == preferences.get(quantity)
    ]
    degraded = [
        METRIC_LABELS.get(quantity, quantity)
        for quantity, direction in trends.items()
        if direction in {"increased", "decreased"}
        and preferences.get(quantity)
        and direction != preferences[quantity]
    ]
    if not improved or not degraded:
        return None
    return (
        f"Sweep 방향에서 개선된 지표는 {_join(improved[:2])}이고, "
        f"저하된 지표는 {_join(degraded[:2])}이어서 Trade-off가 나타났습니다."
    )


def _structured_controlled_sweep(
    payload: dict[str, Any],
    subjects: dict[str, str],
) -> dict[str, list[str]]:
    trends = _sweep_metric_trends(payload)
    descriptions = [_sweep_condition(payload, subjects)]
    principle = _sweep_principle(payload)
    if principle:
        descriptions.append(principle)
    comparisons = []
    for quantities, label in (
        (("dibl", "ss", "ioff", "ion_ioff_ratio", "vth_at_vd_1_5"), "Switching"),
        (("ion", "gm_max", "ron"), "Drive"),
        (("gds", "lambda_clm"), "Saturation"),
    ):
        phrases = [
            _trend_phrase(quantity, trends[quantity])
            for quantity in quantities if quantity in trends
        ]
        if phrases:
            comparisons.append(f"{label} 추세는 " + ", ".join(phrases[:3]) + "입니다.")
    non_monotonic = [
        METRIC_LABELS.get(quantity, quantity)
        for quantity, direction in trends.items()
        if direction == "non_monotonic"
    ]
    if non_monotonic:
        comparisons.append(
            f"{_join(non_monotonic[:3])}은 비단조 변화이므로 두 endpoint만으로 "
            "중간 조건을 추정하지 말고 각 Curve를 개별 확인해야 합니다."
        )
    comparisons.append(
        "Curve에서는 정렬된 순서대로 log(Id)-Vg의 threshold 이동·subthreshold 기울기·off 전류와 "
        "Id-Vg의 on 전류, Id-Vd의 선형 및 saturation 기울기가 일관되게 이동하는지 확인합니다."
    )
    tradeoff = _sweep_tradeoff(trends)
    caution = (
        "이 추세는 선택한 sweep 지점과 고정된 나머지 조건 안에서의 모델 관찰입니다. "
        "지점 사이 또는 범위 밖을 단조롭게 이어서 단정하려면 추가 시뮬레이션이 필요합니다."
    )
    response = {
        "descriptions": descriptions,
        "comparisons": comparisons,
        "tradeoffs": [tradeoff] if tradeoff else [],
        "cautions": [caution],
    }
    return enforce_output_policy(response, payload.get("output_policy", {}))


def _compact_pair_observation(
    payload: dict[str, Any],
    comparison: dict[str, Any],
    subjects: dict[str, str],
) -> str:
    condition = render_condition_sentence(comparison, subjects)
    items = _eligible_iv_evidence(payload, comparison["comparison_id"])
    chosen = []
    for group in ("switching", "drive", "saturation"):
        grouped = group_iv_evidence(items)[group]
        if grouped:
            chosen.append(_metric_change(grouped[0]))
    if not chosen:
        return condition
    return condition + f" 관찰값은 {_join(chosen[:3])}했습니다."


def _structured_mixed_group(
    payload: dict[str, Any],
    comparisons: list[dict[str, Any]],
    subjects: dict[str, str],
) -> dict[str, list[str]]:
    plan = payload.get("comparison_plan", {})
    by_id = {item["comparison_id"]: item for item in comparisons}
    controlled = [
        by_id[comparison_id]
        for comparison_id in plan.get("controlled_pair_ids", [])
        if comparison_id in by_id
    ]
    compound = [
        by_id[comparison_id]
        for comparison_id in plan.get("compound_pair_ids", [])
        if comparison_id in by_id
    ]
    controlled_parameters = list(dict.fromkeys(
        change["parameter"]
        for comparison in controlled
        for change in comparison.get("changed_parameters", [])
    ))
    if controlled:
        descriptions = [
            "여러 device parameter 조합이 포함되어 전체 Curve를 하나의 원인 순서로 정렬하지 않고, "
            "한 parameter만 달라지는 controlled pair를 우선 분석했습니다."
        ]
    else:
        descriptions = [
            "모든 pair에서 여러 device parameter가 함께 변경되어 controlled pair가 없습니다. "
            "첫 Curve를 공통 기준으로 관찰된 결과 차이를 비교하되, 특정 parameter의 개별 영향으로 "
            "귀속하지 않습니다."
        ]
    if controlled_parameters:
        descriptions.append(
            "통제 가능한 비교 변수는 "
            + _join([PARAMETER_LABELS.get(item, item) for item in controlled_parameters])
            + "입니다."
        )
    descriptions.append(
        "I-V에서는 log(Id)-Vg의 threshold 위치·subthreshold 기울기·off-current floor로 "
        "switching을, Id-Vg의 on-current와 gm으로 drive를, Id-Vd의 저전압 선형 기울기와 "
        "고전압 잔류 기울기로 Ron과 saturation을 구분해 확인합니다."
    )
    lines = [
        _compact_pair_observation(payload, comparison, subjects)
        for comparison in controlled
    ]
    remaining = max(0, int(payload.get("output_policy", {}).get("max_comparisons", 6)) - len(lines))
    primary_compound = [
        item for item in compound
        if item.get("comparison_role") == "primary_baseline_to_variant"
    ]
    for comparison in primary_compound[:remaining]:
        lines.append(
            _compact_pair_observation(payload, comparison, subjects)
            + " 이 비교는 여러 조건이 함께 달라 결과만 기술합니다."
        )
    ranking_priority = {
        "off_state_control": 0,
        "drive_performance": 1,
        "short_channel_control": 2,
        "subthreshold_behavior": 3,
        "saturation_behavior": 4,
    }
    rankings = sorted(
        payload.get("interpretation", {}).get("variant_rankings", []),
        key=lambda item: ranking_priority.get(item.get("performance_area"), 9),
    )
    for ranking in rankings:
        sentence = _ranking_sentence(ranking, subjects)
        if sentence:
            lines.append(
                sentence
                + " 이는 baseline 대비 관찰 성능 순위이며 개별 parameter의 원인 순위는 아닙니다."
            )
        if len(lines) >= int(payload.get("output_policy", {}).get("max_comparisons", 6)):
            break
    if not lines:
        summaries, evidence, _overall = _interpretation_maps(payload)
        lines = [
            _compact_multi_sentence(
                payload, comparison, subjects, {}, summaries, evidence,
            )
            for comparison in comparisons[:2]
        ]
    tradeoffs = []
    selected_tradeoffs = select_observed_tradeoffs_for_output(payload)
    controlled_ids = {comparison["comparison_id"] for comparison in controlled}
    controlled_tradeoff = next(
        (
            item for item in selected_tradeoffs
            if item.get("comparison_id") in controlled_ids
        ),
        None,
    )
    if controlled_tradeoff:
        comparison = by_id.get(controlled_tradeoff.get("comparison_id"))
        observed = _structured_tradeoff_sentence(controlled_tradeoff)
        pair = (
            f"{subjects.get(comparison['baseline_subject_id'], comparison['baseline_subject_id'])}과 "
            f"{subjects.get(comparison['candidate_subject_id'], comparison['candidate_subject_id'])}"
            if comparison else "Controlled pair"
        )
        tradeoffs.append(
            f"{pair}의 controlled 비교에서 {observed or '개선 영역과 저하 영역이 함께 관찰됐습니다.'} "
            "따라서 목표 지표를 정한 뒤 후보를 선택해야 합니다."
        )
    elif selected_tradeoffs:
        item = selected_tradeoffs[0]
        comparison = by_id.get(item.get("comparison_id"))
        observed = _structured_tradeoff_sentence(item)
        if observed:
            pair = (
                f"{subjects.get(comparison['baseline_subject_id'], comparison['baseline_subject_id'])}과 "
                f"{subjects.get(comparison['candidate_subject_id'], comparison['candidate_subject_id'])}"
                if comparison else "일부 Curve"
            )
            tradeoffs.append(
                f"{pair}의 복합 비교에서 {observed} "
                "여러 parameter가 함께 달라 이 Trade-off의 존재만 기술하며 특정 parameter의 영향으로 귀속하지 않습니다."
            )
    caution_parts = []
    if compound:
        caution_parts.append(
            "여러 parameter가 동시에 달라지는 pair는 개별 변수의 기여도 산정이나 원인 귀속에 사용하지 않았습니다"
        )
    caution_parts.append(
        "전체 우열은 누설·구동·short-channel·saturation 중 어떤 성능을 우선하는지 정한 뒤 판단해야 합니다"
    )
    response = {
        "descriptions": descriptions,
        "comparisons": lines,
        "tradeoffs": tradeoffs,
        "cautions": [". 또한 ".join(caution_parts) + "."],
    }
    return enforce_output_policy(response, payload.get("output_policy", {}))


def _structured_multi_curve(payload: dict[str, Any], comparisons: list[dict[str, Any]], subjects: dict[str, str]) -> dict[str, list[str]]:
    mode = payload.get("comparison_plan", {}).get("analysis_mode")
    if mode == "controlled_sweep":
        return _structured_controlled_sweep(payload, subjects)
    if mode == "mixed_group":
        return _structured_mixed_group(payload, comparisons, subjects)
    summaries, evidence, overall = _interpretation_maps(payload)
    primary = [item for item in comparisons if item.get("comparison_role") == "primary_baseline_to_variant"]
    lines = [_compact_multi_sentence(payload, item, subjects, overall, summaries, evidence) for item in primary]
    ranking_priority = {"off_state_control": 0, "drive_performance": 1, "short_channel_control": 2, "subthreshold_behavior": 3, "saturation_behavior": 4}
    rankings = sorted(payload.get("interpretation", {}).get("variant_rankings", []), key=lambda item: ranking_priority.get(item["performance_area"], 9))
    for ranking in rankings:
        sentence = _ranking_sentence(ranking, subjects)
        if sentence: lines.append(sentence)
    tradeoffs = []
    patterns = {item.get("result_pattern") for item in payload.get("interpretation", {}).get("observed_tradeoffs", []) if item.get("tradeoff_type") == "observed_performance_tradeoff"}
    if patterns:
        tradeoffs.append("Variant별로 개선되는 성능 영역과 저하되는 영역이 달라 단일 지표만으로 전체 우수성을 결정할 수 없습니다.")
    response = {"descriptions": [IV_TEMPLATES["structured.multi_curve_condition"]], "comparisons": lines,
                "tradeoffs": tradeoffs, "cautions": [_structured_caution(payload, comparisons)]}
    return enforce_output_policy(response, payload.get("output_policy", {}))


def render_structured_iv_comparison(payload: dict[str, Any]) -> dict[str, list[str]]:
    comparisons = sorted(payload.get("comparisons", []), key=lambda item: item.get("comparison_order", 0))
    subjects = {item["subject_id"]: item["display_name"] for item in payload.get("subjects", [])}
    if len(payload.get("subjects", [])) >= 3:
        return _structured_multi_curve(payload, comparisons, subjects)
    return _structured_two_curve(payload, comparisons, subjects)


def render_iv_comparison(payload: dict[str, Any]) -> dict[str, list[str]]:
    if payload.get("interpretation", {}).get("status") == "complete":
        return render_structured_iv_comparison(payload)
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
