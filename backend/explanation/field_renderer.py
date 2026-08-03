from __future__ import annotations

from typing import Any

from .field_templates import (CONCEPT_LABELS, FIELD_COMMON_TEMPLATES, FIELD_LABELS, PARAMETER_LABELS, REGION_LABELS,
                              STRUCTURED_ASSESSMENT_LABELS, STRUCTURED_CONCEPT_LABELS, STRUCTURED_FIELD_LABELS)
from .field_policies import FIELD_POLICY_REGISTRY
from .field_specific_templates import FIELD_SPECIFIC_TEMPLATES, NO_DIFFERENCE_TEMPLATES
from .iv_renderer import enforce_output_policy, validate_explanation_response

SUPPORTED_DISPLAYS = set(FIELD_LABELS)
SHARED_SCALE_TYPES = {"regional_level_change", "high_value_area_change", "hotspot_strength_change", "distribution_width_change", "path_connectivity_change", "crowding_change"}


def validate_field_context(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    context = payload.get("context", {}); reasons = []
    if context.get("display") not in SUPPORTED_DISPLAYS: reasons.append("unsupported_display")
    if context.get("mode") == "comparison" and len(payload.get("subjects", [])) < 2: reasons.append("invalid_subject_count")
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


def _structured_parameter_principles(comparison: dict[str, Any], display: str) -> str | None:
    phrases = []
    changes = list(comparison.get("changed_parameters", []))
    display_priority = {
        "potential": ("channel_length", "oxide_thickness", "bulk_doping", "ldd_doping", "source_drain_doping"),
        "electric_field": ("channel_length", "ldd_doping", "source_drain_doping", "oxide_thickness", "bulk_doping"),
        "energy_band": ("oxide_thickness", "bulk_doping", "channel_length", "ldd_doping", "source_drain_doping"),
        "electron_density": ("oxide_thickness", "bulk_doping", "channel_length", "ldd_doping", "source_drain_doping"),
        "hole_density": ("bulk_doping", "oxide_thickness", "channel_length", "source_drain_doping", "ldd_doping"),
        "electron_current_density": ("channel_length", "oxide_thickness", "source_drain_doping", "ldd_doping", "bulk_doping"),
        "hole_current_density": ("bulk_doping", "source_drain_doping", "ldd_doping", "oxide_thickness", "channel_length"),
        "total_current_density": ("channel_length", "oxide_thickness", "source_drain_doping", "ldd_doping", "bulk_doping"),
        "srh_recombination": ("source_drain_doping", "ldd_doping", "bulk_doping", "oxide_thickness", "channel_length"),
    }.get(display, ())
    order = {parameter: index for index, parameter in enumerate(display_priority)}
    changes.sort(key=lambda item: order.get(item.get("parameter"), 99))
    if len(changes) > 2:
        changes = changes[:2]
    for change in changes:
        parameter, direction = change.get("parameter"), change.get("direction")
        if parameter == "channel_length":
            phrases.append("Channel length 증가는 Drain 영향과 국부 field 집중을 완화하지만 채널 저항은 높이는 방향을 가집니다" if direction == "increased" else "Channel length 감소는 채널 저항을 낮추지만 Drain 영향과 국부 field 집중을 키울 수 있습니다")
        elif parameter == "oxide_thickness":
            phrases.append("Tox 증가는 Gate–Channel coupling을 약화하는 방향을 가집니다" if direction == "increased" else "Tox 감소는 Gate–Channel coupling을 강화하며 Oxide field도 함께 높일 수 있습니다")
        elif parameter == "bulk_doping":
            if direction == "increased":
                phrases.append(
                    "Bulk doping 증가는 Gate 아래 공핍 전하 조건을 키우고 공핍 폭을 바꿀 수 있으므로 "
                    "Channel near-surface와 Deep bulk의 Potential 및 band bending을 함께 확인해야 합니다"
                )
            else:
                phrases.append(
                    "Bulk doping 감소는 공핍 전하 조건을 낮추는 한편 공핍 폭을 넓힐 수 있으므로 "
                    "Channel near-surface와 Deep bulk의 공간 분포를 함께 확인해야 합니다"
                )
        elif parameter == "source_drain_doping":
            phrases.append("Source/Drain doping 증가는 series resistance를 낮추는 한편 junction field를 높일 수 있습니다" if direction == "increased" else "Source/Drain doping 감소는 junction field를 낮출 수 있지만 series resistance를 높이는 방향을 가집니다")
        elif parameter == "ldd_doping":
            phrases.append("LDD doping 증가는 extension resistance를 낮추는 한편 Drain-side field를 집중시킬 수 있습니다" if direction == "increased" else "LDD doping 감소는 Drain-side potential drop을 분산시키지만 extension resistance를 높이는 방향을 가집니다")
    if not phrases:
        return None
    return "일반적으로 " + ". 또한 ".join(phrases) + "."


def _field_observation_guide(
    display: str,
    conclusions: list[dict[str, Any]],
) -> str:
    regions = list(dict.fromkeys(
        REGION_LABELS.get(item.get("region"), item.get("region"))
        for item in conclusions
        if item.get("region")
    ))
    location = ", ".join(regions[:3]) or "우선순위 named region"
    guides = {
        "potential": (
            f"화면에서는 {location}의 color level과 contour 간격을 먼저 비교하세요. "
            "같은 color scale에서 level 변화는 전위 준위 이동을, contour가 촘촘해지는 변화는 "
            "더 큰 Potential gradient를 뜻합니다."
        ),
        "electric_field": (
            f"화면에서는 {location}의 hotspot 강도와 고전계 색상 영역의 넓이를 함께 비교하세요. "
            "hotspot은 국부 peak, 색상 영역의 넓이는 높은 전계가 퍼진 범위를 보여줍니다."
        ),
        "electron_density": (
            f"화면에서는 {location}의 Electron level뿐 아니라 Gate 아래 분포의 폭과 "
            "Source-Channel-Drain 방향 연결성을 확인하세요. 이 둘이 inversion layer와 "
            "전도 가능한 carrier path를 구분하는 핵심입니다."
        ),
        "hole_density": (
            f"화면에서는 {location}의 Hole level과 surface에서 Deep bulk로 이어지는 분포 폭을 "
            "비교하세요. 이는 depletion이 확장되거나 축소되는 공간적 범위를 읽는 기준입니다."
        ),
        "electron_current_density": (
            f"화면에서는 {location}에서 Source-Channel-Drain current path의 연속성, 폭, "
            "국부 crowding을 구분해 보세요."
        ),
        "hole_current_density": (
            f"화면에서는 {location}의 Hole current activity 위치와 국부 집중을 확인하되, "
            "전체 전류의 지배 성분으로 바로 해석하지 마세요."
        ),
        "total_current_density": (
            f"화면에서는 {location}에서 주 전도 경로가 연속적인지, 넓어졌는지, 특정 접합에 "
            "crowding되는지를 함께 확인하세요."
        ),
        "srh_recombination": (
            f"화면에서는 {location}의 activity 강도와 영역 넓이를 확인하고, signed scale에서는 "
            "recombination과 generation의 부호도 별도로 확인하세요."
        ),
    }
    return guides.get(
        display,
        f"화면에서는 {location}에서 같은 color scale 기준의 강도와 공간 범위를 비교하세요.",
    )


def _structured_condition(payload: dict[str, Any], comparison: dict[str, Any] | None = None) -> str:
    display = STRUCTURED_FIELD_LABELS.get(payload["context"]["display"], payload["context"]["display"])
    subjects = {item["subject_id"]: item["display_name"] for item in payload.get("subjects", [])}
    bias = payload.get("context", {}).get("fixed_bias", {})
    bias_text = f"Vg={float(bias['vg_v']):g} V, Vd={float(bias['vd_v']):g} V에서 " if bias.get("vg_v") is not None and bias.get("vd_v") is not None else ""
    if comparison is None:
        name = next(iter(subjects.values()), "선택 조건")
        return f"{bias_text}{name}의 {display} 공간 분포를 named region과 정규화 좌표 기준으로 분석했습니다."
    baseline = subjects.get(comparison["baseline_subject_id"], comparison["baseline_subject_id"])
    candidate = subjects.get(comparison["candidate_subject_id"], comparison["candidate_subject_id"])
    changes = []
    for item in comparison.get("changed_parameters", []):
        label = PARAMETER_LABELS.get(item["parameter"], item["parameter"])
        changes.append(f"{label} {float(item['baseline']):g}→{float(item['candidate']):g} {item.get('unit') or ''}".strip())
    changed = ", ".join(changes) if changes else "동일한 device parameter"
    return f"{bias_text}{baseline} 대비 {candidate}의 {display} 분포를 비교했으며, 변경 조건은 {changed}입니다."


def _group_structured_conclusions(conclusions: list[dict[str, Any]], candidate: str) -> list[str]:
    groups: dict[tuple[str, str], list[str]] = {}
    for item in conclusions:
        key = (item.get("concept", ""), item.get("assessment", ""))
        groups.setdefault(key, []).append(REGION_LABELS.get(item.get("region"), item.get("region") or "해당 영역"))
    lines = []
    for (concept, assessment), regions in groups.items():
        concept_label = STRUCTURED_CONCEPT_LABELS.get(concept, concept)
        assessment_label = STRUCTURED_ASSESSMENT_LABELS.get(assessment, assessment)
        lines.append(f"{candidate}에서는 {', '.join(dict.fromkeys(regions))}의 {concept_label} 변화가 {assessment_label}되는 방향으로 나타났습니다.")
    concepts: dict[str, set[str]] = {}
    for item in conclusions:
        concepts.setdefault(item.get("concept", ""), set()).add(item.get("assessment", ""))
    mixed = [STRUCTURED_CONCEPT_LABELS.get(concept, concept) for concept, directions in concepts.items() if len(directions) > 1]
    if mixed:
        lines.append(f"{', '.join(mixed)} 변화는 영역별로 반대 방향을 보여 소자 전체에서 일률적으로 증가하거나 감소한 것으로 해석할 수 없습니다.")
    return lines


def _structured_energy_band_conclusions(
    conclusions: list[dict[str, Any]],
    candidate: str,
) -> list[str]:
    lines = []
    barrier_rendered = False
    for item in conclusions:
        concept = item.get("concept")
        assessment = item.get("assessment")
        if concept == "channel_entry_barrier":
            template = FIELD_SPECIFIC_TEMPLATES.get(
                f"energy_band.barrier.{assessment}"
            )
            if template:
                barrier_rendered = True
                sentence = template.format(candidate=candidate)
                if sentence not in lines:
                    lines.append(
                        sentence
                        + " Horizontal cut에서 Source plateau 대비 Source-side Channel의 "
                        "국부 Ec maximum과 그 위치를 비교하면 됩니다. 이 값은 Carrier가 "
                        "Channel에 주입될 때 넘어야 하는 상대적 에너지 장벽을 나타냅니다."
                    )
        elif concept == "vertical_band_bending":
            direction = "강화" if assessment == "strengthened" else "완화"
            lines.append(
                f"Vertical Gate-Oxide-Bulk cut에서는 Channel surface와 Deep bulk 사이의 "
                f"Ec separation이 {direction}되어 수직 band bending이 {direction}된 방향입니다. "
                "surface와 Deep bulk의 band 간격 및 굽힘 방향을 함께 확인하세요."
            )
        elif concept == "channel_band_slope":
            direction = "가팔라진" if assessment == "strengthened" else "완만해진"
            lines.append(
                f"Horizontal Channel cut에서는 Source-side에서 Drain-side로 이어지는 Ec 기울기가 "
                f"{direction} 방향입니다. 채널 양 끝의 band 높이 차와 기울기가 집중되는 위치를 "
                "비교하면 채널 방향 Potential drop 변화를 볼 수 있습니다."
            )
    if not barrier_rendered:
        lines.append(
            "Channel 진입 barrier는 Horizontal Source-to-Channel cut에서 Source plateau보다 높은 "
            "Source-side 국부 Ec maximum으로 비교합니다. 현재 유의 기준에서 뚜렷한 barrier "
            "상승·하강이 선택되지 않았으므로 band slope와 수직 band bending을 중심으로 해석합니다."
        )
    return lines


def _single_energy_band_description(payload: dict[str, Any]) -> list[str] | None:
    profiles = payload.get("interpretation", {}).get("energy_band_profiles", [])
    if not profiles:
        return None
    profile = profiles[0]
    channel = profile.get("channel_cut", {})
    vertical = profile.get("vertical_gate_oxide_bulk_cut", {}).get("Bulk", {})
    if not channel.get("finite"):
        return None
    descriptions = [
        _structured_condition(payload),
        (
            (
                "Horizontal Source-to-Channel cut에서는 Source plateau를 기준으로 Source-side "
                "Channel의 국부 Ec maximum이 확인되어 이를 Channel 진입 barrier로 추출했습니다. "
            )
            if channel.get("positive_barrier_resolved")
            else
            (
                "Horizontal Source-to-Channel cut에서는 Source plateau보다 높은 뚜렷한 positive "
                "Channel barrier가 현재 해상도에서 분리되지 않았습니다. "
            )
        )
        + (
            "국부 maximum 위치와 Channel source-edge·center·drain-edge의 band 높이를 함께 확인합니다."
        ),
    ]
    tilt = channel.get("channel_tilt_eV")
    if tilt is not None:
        tilt_direction = (
            "Drain 방향으로 낮아지는"
            if float(tilt) < 0 else
            "Drain 방향으로 높아지는"
            if float(tilt) > 0 else
            "거의 평탄한"
        )
        bending = vertical.get("surface_minus_deep_Ec_eV")
        bending_text = ""
        if bending is not None:
            surface_direction = (
                "surface band가 Deep bulk보다 높은"
                if float(bending) > 0 else
                "surface band가 Deep bulk보다 낮은"
                if float(bending) < 0 else
                "surface와 Deep bulk band 차가 작은"
            )
            bending_text = (
                f" Vertical Gate-Oxide-Bulk cut은 {surface_direction} 형태이며, "
                "두 위치의 Ec separation으로 수직 band bending을 읽습니다."
            )
        descriptions.append(
            f"현재 Horizontal Channel cut은 Ec가 {tilt_direction} 형태입니다. "
            "Channel 양 끝의 높이 차는 채널 방향 Potential drop과 band slope를 보여줍니다."
            + bending_text
        )
    return descriptions


def _structured_iv_verification(
    links: list[dict[str, Any]],
) -> str | None:
    if not links:
        return None
    metrics = []
    meanings = []
    for item in links[:3]:
        meanings.append(str(item.get("physical_interpretation", "")).strip())
        for metric in item.get("iv_metrics_to_check", []):
            label = {
                "vth": "Vth", "dibl": "DIBL", "ioff": "Ioff",
                "ion": "Ion", "ss": "SS", "gm_max": "gm max",
                "ron": "Ron", "gds": "gds",
            }.get(str(metric), str(metric))
            if label not in metrics:
                metrics.append(label)
    meaning = " ".join(value for value in meanings if value)
    check = ", ".join(metrics)
    if not check:
        return meaning or None
    return (
        f"{meaning} 이 Field 관찰이 실제 전기 특성 변화로 이어졌는지는 "
        f"I-V의 {check}를 함께 비교해야 확정할 수 있습니다."
    )


def _structured_field_caution(payload: dict[str, Any], comparison: dict[str, Any] | None) -> str:
    display = payload.get("context", {}).get("display")
    parts = []
    if comparison and comparison.get("changed_parameter_count", 0) > 1:
        parts.append("여러 parameter가 동시에 변경되어 각 parameter의 개별 기여도를 분리해 단정할 수 없습니다")
    if display == "electric_field": parts.append("Electric field 분포만으로 breakdown이나 lifetime을 판단하지 않습니다")
    elif display in {"electron_density", "hole_density"}: parts.append("Carrier density 분포만으로 terminal current 변화를 판단하지 않습니다")
    elif display in {"electron_current_density", "hole_current_density", "total_current_density"}: parts.append("국부 current density는 terminal Drain current와 동일하지 않습니다")
    elif display == "srh_recombination": parts.append("절대 크기만으로 recombination과 generation의 부호를 구분하지 않습니다")
    elif display == "energy_band": parts.append("Energy band는 model-derived approximation입니다")
    parts.append("이 결과는 학습 모델의 prediction이므로 실제 측정 또는 TCAD 검증을 대체하지 않습니다")
    return ". ".join(parts) + "."


def _representative_comparison(
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    representative = set(
        payload.get("comparison_plan", {}).get(
            "representative_subject_ids", []
        )
    )
    if len(representative) != 2:
        return None
    return next(
        (
            item for item in payload.get("comparisons", [])
            if set(item.get("subject_ids", [])) == representative
        ),
        None,
    )


def _multi_field_scope_sentence(
    payload: dict[str, Any],
    comparison: dict[str, Any] | None,
) -> str:
    context = payload.get("context", {})
    plan = payload.get("comparison_plan", {})
    subjects = {
        item["subject_id"]: item["display_name"]
        for item in payload.get("subjects", [])
    }
    display = STRUCTURED_FIELD_LABELS.get(
        context.get("display"), context.get("display")
    )
    bias = context.get("fixed_bias", {})
    bias_text = (
        f"Vg={float(bias['vg_v']):g} V, Vd={float(bias['vd_v']):g} V에서 "
        if bias.get("vg_v") is not None and bias.get("vd_v") is not None
        else ""
    )
    representative_names = [
        subjects.get(subject_id, subject_id)
        for subject_id in plan.get("representative_subject_ids", [])
    ]
    representative_text = "와 ".join(representative_names)
    if plan.get("analysis_mode") == "controlled_sweep":
        parameter = PARAMETER_LABELS.get(
            plan.get("sweep_parameter"), plan.get("sweep_parameter")
        )
        values = "→".join(
            f"{float(value):g}" for value in plan.get("sweep_values", [])
        )
        return (
            f"{bias_text}{len(subjects)}개 조건의 {display} 특징을 모두 "
            f"분석했습니다. {parameter} sweep {values}의 전체 추세를 "
            f"계산하고, 화면에는 양 끝 조건인 {representative_text}를 "
            "대표 Map으로 표시합니다."
        )
    controlled = bool(plan.get("controlled_pair_ids"))
    basis = (
        "한 parameter만 다른 controlled pair"
        if controlled else
        "변경 폭이 큰 대표 복합 pair"
    )
    return (
        f"{bias_text}{len(subjects)}개 조건의 {display} 영역별 특징과 "
        f"모든 pair를 분석했습니다. 화면에는 {basis}인 "
        f"{representative_text}를 표시하며, 나머지 조건도 분석 범위에는 "
        "포함됩니다."
    )


def _multi_field_trend_sentence(
    trend: dict[str, Any],
    display: str,
) -> str:
    direction = trend.get("direction")
    direction_text = {
        "monotonic_increase": "단조 증가했습니다",
        "monotonic_decrease": "단조 감소했습니다",
        "stable": "유의한 변화 없이 유지됐습니다",
        "non_monotonic": (
            "단조 경향을 보이지 않아 중간 조건에서 방향이 바뀌었습니다"
        ),
    }.get(direction, "일관된 추세를 확인하기 어렵습니다")
    quantity = trend.get("quantity")
    if quantity == "channel_entry_barrier":
        return (
            f"Channel 진입 barrier는 sweep 전반에서 {direction_text}. "
            "Horizontal Source-to-Channel cut에서 Source plateau 대비 "
            "Source-side 국부 Ec maximum을 조건 순서대로 비교하세요."
        )
    if quantity == "channel_band_slope":
        return (
            f"Horizontal Channel band slope는 sweep 전반에서 "
            f"{direction_text}. Source-edge와 Drain-edge의 Ec 높이 차와 "
            "기울기 집중 위치를 비교하세요."
        )
    if quantity == "vertical_band_bending":
        return (
            f"수직 band bending 크기는 sweep 전반에서 {direction_text}. "
            "Vertical Gate-Oxide-Bulk cut의 surface와 Deep bulk Ec "
            "separation을 조건 순서대로 확인하세요."
        )
    region = REGION_LABELS.get(
        trend.get("region"), trend.get("region") or "해당 영역"
    )
    feature = {
        "potential": "Potential 분포 강도",
        "electric_field": "Electric field 강도",
        "electron_density": "Electron density 크기",
        "hole_density": "Hole density 크기",
        "electron_current_density": "Electron current density 크기",
        "hole_current_density": "Hole current density 크기",
        "total_current_density": "Total current density 크기",
        "srh_recombination": "SRH activity 절대 크기",
    }.get(display, "공간 분포 강도")
    return (
        f"{region}의 {feature}는 sweep 전반에서 {direction_text}. "
        "같은 color scale에서 해당 영역의 색상 강도와 고값 영역의 "
        "범위를 조건 순서대로 확인하세요."
    )


def _render_multi_field_explanation(
    payload: dict[str, Any],
) -> dict[str, list[str]]:
    context = payload["context"]
    display = context["display"]
    plan = payload.get("comparison_plan", {})
    representative = _representative_comparison(payload)
    descriptions = [
        _multi_field_scope_sentence(payload, representative)
    ]
    if representative:
        principle = _structured_parameter_principles(
            representative, display
        )
        if principle:
            descriptions.append(principle)

    lines: list[str] = []
    trends = payload.get("interpretation", {}).get(
        "multi_condition_trends", []
    )
    if plan.get("analysis_mode") == "controlled_sweep" and trends:
        lines.extend(
            _multi_field_trend_sentence(item, display)
            for item in trends[:3]
        )
    elif representative:
        conclusions = [
            item
            for item in payload.get("interpretation", {}).get(
                "field_specific_conclusions", []
            )
            if item.get("comparison_id")
            == representative.get("comparison_id")
        ]
        subjects = {
            item["subject_id"]: item["display_name"]
            for item in payload.get("subjects", [])
        }
        candidate = subjects.get(
            representative["candidate_subject_id"],
            representative["candidate_subject_id"],
        )
        if display == "energy_band":
            lines.extend(
                _structured_energy_band_conclusions(
                    conclusions, candidate
                )
            )
        else:
            lines.extend(
                _group_structured_conclusions(conclusions, candidate)
            )

    guide_source = [
        item
        for item in payload.get("interpretation", {}).get(
            "field_specific_conclusions", []
        )
        if (
            representative is None
            or item.get("comparison_id")
            == representative.get("comparison_id")
        )
    ]
    if display != "energy_band":
        lines.append(_field_observation_guide(display, guide_source))
    if not lines:
        lines.append(
            "전체 조건의 공간 특징은 분석했지만 현재 유의 기준에서 "
            "일관된 추세가 선택되지 않았습니다. 대표 Map의 named region을 "
            "같은 scale에서 비교하고 중간 조건이 양 끝 조건 사이에 놓이는지 "
            "확인하세요."
        )

    caution = _structured_field_caution(payload, representative)
    caution = (
        "화면에는 대표 2개 Map만 표시되며 전체 추세는 선택된 모든 "
        "조건의 구조화된 특징으로 계산했습니다. " + caution
    )
    response = {
        "descriptions": descriptions,
        "comparisons": lines,
        "tradeoffs": [],
        "cautions": [caution],
    }
    return enforce_output_policy(
        response, payload.get("output_policy", {})
    )


def render_structured_field_explanation(payload: dict[str, Any]) -> dict[str, list[str]]:
    interpretation = payload.get("interpretation", {})
    comparisons = payload.get("comparisons", [])
    if len(payload.get("subjects", [])) > 2:
        return _render_multi_field_explanation(payload)
    if not comparisons:
        if payload.get("context", {}).get("display") == "energy_band":
            descriptions = _single_energy_band_description(payload)
            if descriptions:
                return enforce_output_policy(
                    {
                        "descriptions": descriptions,
                        "comparisons": [],
                        "tradeoffs": [],
                        "cautions": [_structured_field_caution(payload, None)],
                    },
                    payload.get("output_policy", {}),
                )
        regional = interpretation.get("regional_summaries", [])
        if not regional: return _fallback(payload.get("output_policy"))
        policy = FIELD_POLICY_REGISTRY.get(payload["context"]["display"])
        allowed = set(policy.region_priority) if policy else set()
        ranked = sorted((item for item in regional if not allowed or item.get("region") in allowed), key=lambda item: -float(item.get("magnitude_p95", 0)))
        regions = [REGION_LABELS.get(item["region"], item["region"]) for item in ranked[:2]]
        description = f"현재 조건에서는 {', '.join(regions)}에서 상대적으로 큰 공간 분포가 나타났습니다."
        guide = _field_observation_guide(
            payload["context"]["display"],
            [{"region": item.get("region")} for item in ranked[:2]],
        )
        response = {"descriptions": [_structured_condition(payload), description, guide], "comparisons": [], "tradeoffs": [],
                    "cautions": [_structured_field_caution(payload, None)]}
        return enforce_output_policy(response, payload.get("output_policy", {}))
    comparison = comparisons[0]
    conclusions = [item for item in interpretation.get("field_specific_conclusions", []) if item.get("comparison_id") == comparison["comparison_id"]]
    if not conclusions: return render_field_comparison(payload)
    subjects = {item["subject_id"]: item["display_name"] for item in payload.get("subjects", [])}
    candidate = subjects.get(comparison["candidate_subject_id"], comparison["candidate_subject_id"])
    descriptions = [_structured_condition(payload, comparison)]
    principle = _structured_parameter_principles(comparison, payload["context"]["display"])
    if principle: descriptions.append(principle)
    if payload["context"]["display"] == "energy_band":
        lines = _structured_energy_band_conclusions(conclusions, candidate)
        if not lines:
            lines = _group_structured_conclusions(conclusions, candidate)
    else:
        lines = _group_structured_conclusions(conclusions, candidate)
    if payload["context"]["display"] != "energy_band":
        lines.append(_field_observation_guide(
            payload["context"]["display"],
            conclusions,
        ))
    verification = _structured_iv_verification([
        item for item in interpretation.get("cross_domain_links", [])
        if item.get("comparison_id") == comparison["comparison_id"]
    ])
    if verification:
        lines.append(verification)
    tradeoffs = [render_field_tradeoff_sentence(item) for item in payload.get("conclusions", []) if item.get("conclusion_type") == "tradeoff" and item.get("eligible_for_output")]
    response = {"descriptions": descriptions, "comparisons": lines, "tradeoffs": tradeoffs,
                "cautions": [_structured_field_caution(payload, comparison)]}
    return enforce_output_policy(response, payload.get("output_policy", {}))


def render_field_explanation(payload: dict[str, Any]) -> dict[str, list[str]]:
    try:
        valid, reasons = validate_field_context(payload)
        if "unsupported_display" in reasons: return _unsupported(payload.get("output_policy"))
        if not valid: return _fallback(payload.get("output_policy"))
        interpretation = payload.get("interpretation", {})
        if interpretation.get("status") in {"partial", "complete"} and (
            interpretation.get("field_specific_conclusions")
            or interpretation.get("regional_summaries")
            or interpretation.get("energy_band_profiles")
        ):
            result = render_structured_field_explanation(payload)
        else:
            result = render_field_single(payload) if payload.get("analysis_type") == "field_single" else render_field_comparison(payload)
        return validate_explanation_response(result)
    except (KeyError, TypeError, ValueError, OverflowError, IndexError):
        return _fallback(payload.get("output_policy", {}))
