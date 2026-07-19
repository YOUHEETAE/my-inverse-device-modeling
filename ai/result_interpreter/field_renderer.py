from __future__ import annotations

from typing import Any

from .field_templates import CONCEPT_LABELS, FIELD_COMMON_TEMPLATES, FIELD_LABELS, PARAMETER_LABELS, REGION_LABELS
from .field_policies import FIELD_POLICY_REGISTRY
from .field_specific_templates import FIELD_SPECIFIC_TEMPLATES, NO_DIFFERENCE_TEMPLATES
from .iv_renderer import enforce_output_policy, validate_explanation_response

SUPPORTED_DISPLAYS = set(FIELD_LABELS)
SHARED_SCALE_TYPES = {"regional_level_change", "high_value_area_change", "hotspot_strength_change", "distribution_width_change", "path_connectivity_change", "crowding_change"}


def validate_field_context(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    context = payload.get("context", {}); reasons = []
    if context.get("display") not in SUPPORTED_DISPLAYS: reasons.append("unsupported_display")
    if context.get("mode") == "comparison" and len(payload.get("subjects", [])) != 2: reasons.append("invalid_subject_count")
    if context.get("visual_evidence_policy") != "supplied_evidence_only": reasons.append("unsupported_visual_evidence_policy")
    if not context.get("fixed_bias"): reasons.append("missing_fixed_bias")
    return not any(reason in {"unsupported_display", "invalid_subject_count", "unsupported_visual_evidence_policy"} for reason in reasons), reasons


def select_field_evidence(payload: dict[str, Any], *, comparison_id: str | None = None) -> list[dict[str, Any]]:
    context = payload.get("context", {}); display = context.get("display"); shared = bool(context.get("shared_color_scale"))
    threshold = float(payload.get("output_policy", {}).get("minimum_importance_score", 0))
    selection_available = any("selected_for_explanation" in item for item in payload.get("evidence", []))
    selected = []
    for item in payload.get("evidence", []):
        if not item.get("eligible_for_output") or item.get("field_display") != display: continue
        if not selection_available and float(item.get("importance_score", 0)) < threshold: continue
        if selection_available and not item.get("selected_for_explanation"): continue
        if comparison_id is None:
            if item.get("comparison_id") is not None: continue
        elif item.get("comparison_id") != comparison_id: continue
        if not shared and item.get("evidence_type") in SHARED_SCALE_TYPES: continue
        selected.append(item)
    policy = FIELD_POLICY_REGISTRY.get(display)
    return sorted(selected, key=lambda item: (-(policy.evidence_score(item.get("evidence_type")) + policy.region_score(item.get("region"))) if policy else 0,
                                               -float(item.get("importance_score", 0)), item["evidence_id"]))


def _region(item: dict[str, Any]) -> str:
    return REGION_LABELS.get(item.get("region"), item.get("region") or "전체 영역")


def _feature(display: str, *, signed: bool = False) -> str:
    if display == "electric_field": return "고전계"
    if display in {"electron_density", "hole_density"}: return "고농도"
    if "current_density" in display: return "고전류"
    if display == "srh_recombination": return "SRH activity 절대 크기가 큰" if signed else "SRH 활성"
    if display == "potential": return "고 Potential"
    return "고값"


def render_field_condition_sentence(payload: dict[str, Any]) -> str:
    context = payload["context"]; display = FIELD_LABELS[context["display"]]; subjects = payload.get("subjects", [])
    if context.get("mode") == "single":
        curve = subjects[0].get("display_name", "Curve") if subjects else "Curve"; bias = context.get("fixed_bias") or {}
        if bias.get("vg_v") is not None and bias.get("vd_v") is not None:
            return FIELD_COMMON_TEMPLATES["condition.single.bias"].format(vg=f"{float(bias['vg_v']):g}", vd=f"{float(bias['vd_v']):g}", curve=curve, display=display)
        return FIELD_COMMON_TEMPLATES["condition.single"].format(curve=curve, display=display)
    comparison = payload.get("comparisons", [])[0]; names = {item["subject_id"]: item["display_name"] for item in subjects}
    values = {"baseline": names.get(comparison["baseline_subject_id"], comparison["baseline_subject_id"]), "candidate": names.get(comparison["candidate_subject_id"], comparison["candidate_subject_id"]), "display": display}
    if not context.get("shared_color_scale"): return FIELD_COMMON_TEMPLATES["condition.non_shared"].format(**values)
    count = comparison.get("changed_parameter_count", 0)
    if count == 0: return FIELD_COMMON_TEMPLATES["condition.same"].format(**values)
    if count == 1:
        values["parameter"] = PARAMETER_LABELS.get(comparison["changed_parameters"][0]["parameter"], comparison["changed_parameters"][0]["parameter"])
        return FIELD_COMMON_TEMPLATES["condition.controlled"].format(**values)
    return FIELD_COMMON_TEMPLATES["condition.multi"].format(**values)


def render_regional_sentence(item: dict[str, Any], candidate: str, display: str) -> str:
    observation = item.get("observation")
    if item["evidence_type"] == "regional_level":
        key = "single.regional.low" if observation == "dominant_low_value_region" else "single.regional.high"
        return FIELD_COMMON_TEMPLATES[key].format(region=_region(item), feature=_feature(display), display=FIELD_LABELS[display])
    key = "regional.increased" if observation == "increased" else "regional.decreased"
    return FIELD_COMMON_TEMPLATES[key].format(candidate=candidate, region=_region(item), display=FIELD_LABELS[display])


def render_spatial_sentence(item: dict[str, Any], candidate: str, display: str) -> str | None:
    specific = render_field_specific_observation(item, candidate, display)
    if specific: return specific
    evidence_type, observation = item.get("evidence_type"), item.get("observation"); values = {"candidate": candidate, "region": _region(item), "display": FIELD_LABELS[display], "feature": _feature(display, signed=item.get("data", {}).get("value_mode") == "signed")}
    if evidence_type in {"regional_level", "regional_level_change"}: return render_regional_sentence(item, candidate, display)
    if evidence_type == "high_value_area_change" and observation in {"expanded", "contracted"}: return FIELD_COMMON_TEMPLATES[f"area.{observation}"].format(**values)
    if evidence_type == "hotspot_strength_change" and observation in {"strengthened", "weakened"}: return FIELD_COMMON_TEMPLATES[f"hotspot.{observation}"].format(**values)
    if evidence_type == "hotspot_location_shift": return FIELD_COMMON_TEMPLATES.get(f"location.{observation}", "{display} hotspot의 위치가 이동했습니다.").format(**values)
    if evidence_type == "distribution_width_change" and observation in {"widened", "narrowed"}: return FIELD_COMMON_TEMPLATES[f"width.{observation}"].format(**values)
    if evidence_type == "path_connectivity_change":
        key = "connectivity.newly_connected" if observation == "newly_connected" else "connectivity.disconnected" if observation == "disconnected" else "connectivity.strengthened"
        return FIELD_COMMON_TEMPLATES[key]
    if evidence_type == "crowding_change" and observation in {"strengthened", "weakened"}: return FIELD_COMMON_TEMPLATES[f"crowding.{observation}"].format(**values)
    if evidence_type == "contour_spacing_change" and observation in {"narrowed", "widened"}: return FIELD_COMMON_TEMPLATES[f"contour.{observation}"].format(**values)
    if evidence_type == "barrier_or_band_change" and observation in {"raised", "lowered"}: return FIELD_COMMON_TEMPLATES[f"barrier.{observation}"]
    return None


def render_field_specific_observation(item: dict[str, Any], candidate: str, display: str) -> str | None:
    evidence_type, observation = item.get("evidence_type"), item.get("observation"); region = _region(item)
    single = item.get("comparison_id") is None
    values = {"candidate": candidate, "region": region}
    direction_labels = {"shifted_left": "Source 방향", "shifted_right": "Drain 방향", "shifted_toward_source": "Source 방향",
                        "shifted_toward_drain": "Drain 방향", "shifted_toward_channel": "Channel 방향",
                        "shifted_toward_surface": "surface 방향", "shifted_deeper_into_bulk": "Deep bulk 방향"}
    if evidence_type == "hotspot_location_shift" and observation in direction_labels and display in {"potential", "electron_density", "hole_density", "srh_recombination", "energy_band"}:
        values["direction"] = direction_labels[observation]
        return FIELD_SPECIFIC_TEMPLATES[f"{display}.location"].format(**values)
    if single and evidence_type == "regional_level":
        key = {
            "potential": "potential.single.regional", "electric_field": "electric_field.single.regional",
            "electron_density": "electron_density.single.channel" if item.get("region") == "channel_near_surface" else None,
            "hole_density": "hole_density.single.deep_bulk" if item.get("region") == "deep_bulk" else None,
            "electron_current_density": "electron_current_density.single.regional", "hole_current_density": "hole_current_density.single.regional",
            "total_current_density": "total_current_density.single.regional", "srh_recombination": "srh_recombination.single.regional",
            "energy_band": "energy_band.single.barrier",
        }.get(display)
        if key: return FIELD_SPECIFIC_TEMPLATES[key].format(**values)
    if display == "potential" and evidence_type == "distribution_width_change" and observation in {"widened", "narrowed"}:
        return FIELD_SPECIFIC_TEMPLATES[f"potential.width.{observation}"].format(**values)
    if display == "electric_field":
        if evidence_type == "hotspot_strength_change" and observation in {"strengthened", "weakened"}: return FIELD_SPECIFIC_TEMPLATES[f"electric_field.hotspot.{observation}"].format(**values)
        if evidence_type == "crowding_change" and observation in {"strengthened", "weakened"}: return FIELD_SPECIFIC_TEMPLATES[f"electric_field.crowding.{observation}"].format(**values)
    if display == "electron_density":
        if evidence_type == "regional_level_change" and observation in {"increased", "decreased"}: return FIELD_SPECIFIC_TEMPLATES[f"electron_density.regional.{observation}"].format(**values)
        if evidence_type == "distribution_width_change" and observation in {"widened", "narrowed"}: return FIELD_SPECIFIC_TEMPLATES[f"electron_density.width.{observation}"]
        if evidence_type == "path_connectivity_change" and observation in {"newly_connected", "unchanged"}: return FIELD_SPECIFIC_TEMPLATES["electron_density.connectivity"]
    if display == "hole_density":
        if evidence_type == "distribution_width_change" and observation in {"widened", "narrowed"}: return FIELD_SPECIFIC_TEMPLATES[f"hole_density.width.{observation}"]
        if evidence_type == "high_value_area_change" and observation == "expanded" and item.get("region") == "channel_near_surface": return FIELD_SPECIFIC_TEMPLATES["hole_density.area.expanded"].format(**values)
    if display in {"electron_current_density", "total_current_density"}:
        prefix = display
        if evidence_type == "path_connectivity_change" and observation in {"newly_connected", "unchanged"}: return FIELD_SPECIFIC_TEMPLATES[f"{prefix}.connectivity"].format(**values)
        if evidence_type == "distribution_width_change" and observation in {"widened", "narrowed"}: return FIELD_SPECIFIC_TEMPLATES[f"{prefix}.width.{observation}"]
        if evidence_type == "crowding_change" and observation in {"strengthened", "weakened"}: return FIELD_SPECIFIC_TEMPLATES[f"{prefix}.crowding.{observation}"]
    if display == "hole_current_density" and evidence_type == "regional_level_change" and observation in {"increased", "decreased"}:
        return FIELD_SPECIFIC_TEMPLATES[f"hole_current_density.regional.{observation}"].format(**values)
    if display == "srh_recombination":
        sign_class = item.get("data", {}).get("sign_class")
        if sign_class in {"recombination_dominant", "generation_dominant"} and observation in {"increased", "strengthened"}:
            sign = "recombination" if sign_class.startswith("recombination") else "generation"
            return FIELD_SPECIFIC_TEMPLATES[f"srh_recombination.signed.{sign}"].format(**values)
        if evidence_type == "hotspot_strength_change" and observation in {"strengthened", "weakened"}: return FIELD_SPECIFIC_TEMPLATES[f"srh_recombination.hotspot.{observation}"].format(**values)
        if evidence_type == "high_value_area_change" and observation in {"expanded", "contracted"}: return FIELD_SPECIFIC_TEMPLATES[f"srh_recombination.area.{observation}"].format(**values)
    if display == "energy_band" and evidence_type == "barrier_or_band_change":
        if observation in {"raised", "lowered"}: return FIELD_SPECIFIC_TEMPLATES[f"energy_band.barrier.{observation}"].format(**values)
        if observation in {"band_bending_increased", "band_bending_decreased"}: return FIELD_SPECIFIC_TEMPLATES["energy_band.band_bending." + ("increased" if observation.endswith("increased") else "decreased")]
        if observation in {"slope_increased", "slope_decreased"}: return FIELD_SPECIFIC_TEMPLATES["energy_band.slope." + ("increased" if observation.endswith("increased") else "decreased")]
    return None


def merge_related_field_evidence(evidence: list[dict[str, Any]], candidate: str, display: str) -> tuple[list[str], set[str]]:
    sentences = []; used = set()
    if display == "electron_density":
        regional = next((item for item in evidence if item.get("evidence_type") == "regional_level_change" and item.get("observation") == "increased" and item.get("region") == "channel_near_surface"), None)
        width = next((item for item in evidence if item.get("evidence_type") == "distribution_width_change" and item.get("observation") == "widened" and item.get("region") == "channel_near_surface"), None)
        if regional and width:
            sentences.append(FIELD_SPECIFIC_TEMPLATES["electron_density.inversion.merged"].format(candidate=candidate)); used.update({regional["evidence_id"], width["evidence_id"]})
    if display in {"electron_current_density", "total_current_density"}:
        connectivity = next((item for item in evidence if item.get("evidence_type") == "path_connectivity_change" and item.get("observation") in {"newly_connected", "unchanged"}), None)
        width = next((item for item in evidence if item.get("evidence_type") == "distribution_width_change" and item.get("observation") == "widened"), None)
        if connectivity and width:
            sentences.append(FIELD_SPECIFIC_TEMPLATES[f"{display}.path.merged"].format(candidate=candidate)); used.update({connectivity["evidence_id"], width["evidence_id"]})
    for hotspot in evidence:
        if hotspot["evidence_id"] in used or hotspot.get("evidence_type") != "hotspot_strength_change": continue
        area = next((item for item in evidence if item.get("evidence_type") == "high_value_area_change" and item.get("region") == hotspot.get("region") and item["evidence_id"] not in used), None)
        combination = (hotspot.get("observation"), area.get("observation") if area else None)
        if area and combination in {("strengthened", "expanded"), ("weakened", "contracted")}:
            key = f"hotspot.area.{combination[0]}.{combination[1]}"; values = {"candidate": candidate, "region": _region(hotspot), "feature": _feature(display)}
            sentences.append(FIELD_COMMON_TEMPLATES[key].format(**values)); used.update({hotspot["evidence_id"], area["evidence_id"]})
    return sentences, used


def render_physical_implication_sentence(item: dict[str, Any]) -> str | None:
    implication = item.get("physical_implication")
    policy = FIELD_POLICY_REGISTRY.get(item.get("field_display"))
    if not implication or not policy or implication not in policy.allowed_implications: return None
    return FIELD_COMMON_TEMPLATES.get("implication." + str(implication))


def _consistency_sentence(payload: dict[str, Any], comparison_id: str) -> str | None:
    relationships = [item for item in payload.get("conclusions", []) if item.get("comparison_id") == comparison_id and item.get("conclusion_type") == "physical_relationship" and item.get("eligible_for_output")]
    if not relationships: return None
    item = max(relationships, key=lambda value: value.get("importance_score", 0)); consistency = item.get("physical_consistency")
    if consistency not in {"consistent", "partially_consistent", "inconsistent"}: return None
    return FIELD_COMMON_TEMPLATES[f"consistency.{consistency}"].format(concept=CONCEPT_LABELS.get(item.get("target_concept"), item.get("target_concept")))


def render_field_single(payload: dict[str, Any]) -> dict[str, list[str]]:
    display = payload["context"]["display"]; evidence = select_field_evidence(payload)
    if not evidence: return _fallback(payload.get("output_policy"))
    descriptions = [render_field_condition_sentence(payload)]
    for item in evidence[:2]:
        specific = render_field_specific_observation(item, payload["subjects"][0]["display_name"], display)
        sentence = specific or render_spatial_sentence(item, payload["subjects"][0]["display_name"], display)
        if sentence: descriptions.append(sentence)
        implication = render_physical_implication_sentence(item)
        if implication and not specific and item.get("evidence_type") != "contour_spacing_change" and implication not in descriptions: descriptions.append(implication)
    cautions = _field_cautions(payload, single=True)
    return enforce_output_policy({"descriptions": descriptions, "comparisons": [], "tradeoffs": [], "cautions": cautions}, payload.get("output_policy", {}))


def render_field_comparison(payload: dict[str, Any]) -> dict[str, list[str]]:
    context = payload["context"]; display = context["display"]; comparison = payload["comparisons"][0]
    candidate = next((item["display_name"] for item in payload["subjects"] if item["subject_id"] == comparison["candidate_subject_id"]), comparison["candidate_subject_id"])
    evidence = select_field_evidence(payload, comparison_id=comparison["comparison_id"])
    no_difference = any(item.get("comparison_id") == comparison["comparison_id"] and item.get("conclusion_type") == "no_meaningful_difference" for item in payload.get("conclusions", []))
    lines = []
    if no_difference: lines.append(NO_DIFFERENCE_TEMPLATES.get(display, FIELD_COMMON_TEMPLATES["no_difference.shared"]) if context.get("shared_color_scale") else FIELD_COMMON_TEMPLATES["no_difference.non_shared"])
    merged, used = merge_related_field_evidence(evidence, candidate, display); lines.extend(merged)
    for item in evidence:
        if item["evidence_id"] in used: continue
        specific = render_field_specific_observation(item, candidate, display)
        sentence = specific or render_spatial_sentence(item, candidate, display)
        if sentence and sentence not in lines: lines.append(sentence)
        implication = render_physical_implication_sentence(item)
        if implication and not specific and item.get("evidence_type") != "contour_spacing_change" and implication not in lines: lines.append(implication)
        if len(lines) >= 2: break
    consistency = _consistency_sentence(payload, comparison["comparison_id"])
    if consistency: lines.append(consistency)
    if display == "hole_current_density":
        contribution = next((item for item in payload.get("conclusions", []) if item.get("conclusion_type") == "carrier_contribution" and item.get("eligible_for_output")), None)
        if contribution and contribution.get("dominant_carrier") == "electron": lines.append("전체 Current에서는 Electron contribution이 지배적이며 Hole current 변화는 국부 영역에 제한되어 있습니다.")
    tradeoffs = [render_field_tradeoff_sentence(item) for item in payload.get("conclusions", []) if item.get("conclusion_type") == "tradeoff" and item.get("eligible_for_output")]
    descriptions = [render_field_condition_sentence(payload)]
    multi = next((item for item in payload.get("conclusions", []) if item.get("comparison_id") == comparison["comparison_id"] and item.get("conclusion_type") == "multi_parameter_association"), None)
    if multi:
        phrases = []
        effects = multi.get("parameter_effects", [])
        principle_groups = [item.get("principle_ids", []) for item in effects] if effects else [multi.get("principle_ids", [])]
        for principle_ids in principle_groups:
            group = [FIELD_COMMON_TEMPLATES.get("multi_principle." + principle_id) for principle_id in principle_ids]
            # Keep one display-level principle per changed parameter so an
            # earlier parameter cannot crowd later parameters out.
            phrases.extend(item for item in group[:1] if item)
        phrases = list(dict.fromkeys(item for item in phrases if item))
        if phrases: descriptions.append(" ".join(phrases[:5]))
        dominant = multi.get("dominant_alignment_parameter")
        if dominant:
            other = [item.get("parameter") for item in multi.get("parameter_effects", []) if item.get("parameter") != dominant]
            dominant_label = PARAMETER_LABELS.get(dominant, dominant)
            if other:
                other_labels = ", ".join(PARAMETER_LABELS.get(item, item) for item in other)
                lines.append(f"최종 공간 변화는 {other_labels}의 일반적 영향보다 {dominant_label} 변화의 예상 방향과 더 많이 일치했습니다.")
            else:
                lines.append(f"최종 공간 변화는 {dominant_label} 변화의 일반적 예상 방향과 더 많이 일치했습니다.")
    response = {"descriptions": descriptions, "comparisons": lines, "tradeoffs": tradeoffs, "cautions": _field_cautions(payload, single=False)}
    if not lines and not tradeoffs: return _fallback(payload.get("output_policy"), extra_cautions=response["cautions"])
    return enforce_output_policy(response, payload.get("output_policy", {}))


def _field_cautions(payload: dict[str, Any], *, single: bool) -> list[str]:
    context = payload.get("context", {}); types = {item.get("warning_type") for item in payload.get("warnings", []) if item.get("eligible_for_output", True)}; cautions = []
    if "missing_region" in types: cautions.append(FIELD_COMMON_TEMPLATES["caution.missing_region"])
    if types & {"invalid_numeric_value", "missing_data", "weak_visual_evidence"}: cautions.append(FIELD_COMMON_TEMPLATES["caution.invalid"])
    if not context.get("fixed_bias"): cautions.append(FIELD_COMMON_TEMPLATES["caution.missing_bias"])
    if not single and not context.get("shared_color_scale"): cautions.append(FIELD_COMMON_TEMPLATES["caution.non_shared"])
    if "extrapolation" in types: cautions.append(FIELD_COMMON_TEMPLATES["caution.extrapolation"])
    if not single and any(item.get("effective_claim_level") == "multi_parameter_association" for item in payload.get("comparisons", [])): cautions.append(FIELD_COMMON_TEMPLATES["caution.multiple"])
    if context.get("display") == "srh_recombination" and (context.get("scale") in {"log_magnitude", "symlog"} or any(item.get("data", {}).get("value_mode") == "signed" for item in payload.get("evidence", []))): cautions.append(FIELD_COMMON_TEMPLATES["caution.signed"])
    if context.get("display") == "energy_band": cautions.append(FIELD_COMMON_TEMPLATES["caution.energy_band"])
    if context.get("display") in {"electron_density", "hole_density"}: cautions.append(FIELD_COMMON_TEMPLATES["caution.density_current"])
    if context.get("display") in {"electron_current_density", "hole_current_density", "total_current_density"}: cautions.append(FIELD_COMMON_TEMPLATES["caution.local_terminal_current"])
    if context.get("display") == "electric_field": cautions.append(FIELD_COMMON_TEMPLATES["caution.field_reliability"])
    if single: cautions.append(FIELD_COMMON_TEMPLATES["caution.single"])
    elif payload.get("output_policy", {}).get("include_model_limitation", True): cautions.append(FIELD_COMMON_TEMPLATES["caution.model"])
    return cautions


def render_field_tradeoff_sentence(conclusion: dict[str, Any]) -> str:
    label = conclusion.get("label") or conclusion.get("conclusion_label")
    return FIELD_COMMON_TEMPLATES.get("tradeoff." + str(label), "서로 다른 Field 관련 경향이 반대 방향으로 나타나 Trade-off가 관찰되었습니다.")


def _fallback(policy: dict[str, Any] | None = None, *, extra_cautions: list[str] | None = None) -> dict[str, list[str]]:
    cautions = list(extra_cautions or []) or [FIELD_COMMON_TEMPLATES["fallback.caution"]]
    return enforce_output_policy({"descriptions": [FIELD_COMMON_TEMPLATES["fallback.description"]], "comparisons": [], "tradeoffs": [], "cautions": cautions}, policy or {})


def _unsupported(policy: dict[str, Any] | None = None) -> dict[str, list[str]]:
    return enforce_output_policy({"descriptions": [], "comparisons": [], "tradeoffs": [], "cautions": [FIELD_COMMON_TEMPLATES["unsupported.caution"]]}, policy or {})


def render_field_explanation(payload: dict[str, Any]) -> dict[str, list[str]]:
    try:
        valid, reasons = validate_field_context(payload)
        if "unsupported_display" in reasons: return _unsupported(payload.get("output_policy"))
        if not valid: return _fallback(payload.get("output_policy"))
        result = render_field_single(payload) if payload.get("analysis_type") == "field_single" else render_field_comparison(payload)
        return validate_explanation_response(result)
    except (KeyError, TypeError, ValueError, OverflowError, IndexError):
        return _fallback(payload.get("output_policy", {}))
