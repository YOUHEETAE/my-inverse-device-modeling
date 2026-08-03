from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Any

from .interpretation_contract import CURVE_ASSESSMENTS, INTERACTION_TYPES, SUPPORT_LEVELS, build_interpretation_scaffold
from .iv_mechanisms import build_iv_mechanism_chains
from .physical_principles import PHYSICAL_PRINCIPLES


PERFORMANCE_AREAS: dict[str, tuple[str, ...]] = {
    "off_state_control": ("ioff", "ion_ioff_ratio"),
    "short_channel_control": ("dibl",),
    "subthreshold_behavior": ("ss",),
    "drive_performance": ("ion", "gm_max", "ron"),
    "threshold_behavior": ("vth_at_vd_0_05", "vth_at_vd_1_5"),
    "saturation_behavior": ("gds", "lambda_clm"),
    "curve_shape": ("drain_current", "idvg_transition_position"),
}
DESCRIPTIVE_AREAS = {"threshold_behavior", "curve_shape"}
MAGNITUDE_RANK = {"negligible": 0, "minor": 1, "moderate": 2, "major": 3, "critical": 4, "not_applicable": 0}
CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


def _comparison_evidence(evidence: list[dict[str, Any]], comparison_id: str) -> list[dict[str, Any]]:
    return [
        item for item in evidence
        if item.get("comparison_id") == comparison_id
        and item.get("evidence_type") in {"metric_change", "curve_shape_change"}
        and item.get("confidence") in {"medium", "high"}
        and not set(item.get("suppression_reasons", [])).intersection({"invalid_data", "low_confidence", "physically_ambiguous_sign"})
    ]


def _support_level(items: list[dict[str, Any]], *, conflicting: bool = False) -> str:
    if not items:
        return "insufficient"
    if conflicting:
        return "conflicting"
    strong = [
        item for item in items
        if CONFIDENCE_RANK.get(item.get("confidence"), 0) >= 2
        and MAGNITUDE_RANK.get(item.get("magnitude_class"), 0) >= 2
    ]
    if len(strong) >= 2:
        return "strongly_supported"
    return "supported" if len(items) >= 2 or strong else "tentative"


def build_performance_summaries(comparisons: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries = []
    for comparison in comparisons:
        available = _comparison_evidence(evidence, comparison["comparison_id"])
        for area, quantities in PERFORMANCE_AREAS.items():
            items = [item for item in available if item.get("quantity") in quantities]
            if not items:
                continue
            improved = [item for item in items if item.get("assessment") == "improved"]
            degraded = [item for item in items if item.get("assessment") == "degraded"]
            unchanged = [item for item in items if item.get("observation") == "unchanged"]
            if area in DESCRIPTIVE_AREAS:
                assessment = "unchanged" if len(unchanged) == len(items) else "mixed"
                evaluation_mode = "descriptive"
            else:
                assessment = "mixed" if improved and degraded else ("improved" if improved else ("degraded" if degraded else "unchanged"))
                evaluation_mode = "preference_based"
            significant = [item for item in items if item.get("magnitude_class") != "negligible"]
            summaries.append({
                "summary_id": f"summary_{comparison['comparison_id']}_{area}",
                "comparison_id": comparison["comparison_id"],
                "performance_area": area,
                "evaluation_mode": evaluation_mode,
                "assessment": assessment,
                "support_level": _support_level(significant, conflicting=bool(improved and degraded)),
                "supporting_quantities": [item["quantity"] for item in significant],
                "improved_quantities": [item["quantity"] for item in improved],
                "degraded_quantities": [item["quantity"] for item in degraded],
                "unchanged_quantities": [item["quantity"] for item in unchanged],
                "evidence_ids": [item["evidence_id"] for item in items],
                "importance_score": max((float(item.get("importance_score", 0)) for item in items), default=0.0),
            })
    return summaries


def _expected_effects(parameter: str, direction: str) -> list[dict[str, Any]]:
    effects = []
    seen = set()
    for principle in PHYSICAL_PRINCIPLES.get((parameter, direction), []):
        for expected in principle.get("expected_evidence", []):
            key = (expected.get("quantity"), expected.get("expected_observation"), expected.get("evidence_type"), expected.get("region_contains"))
            if key in seen:
                continue
            seen.add(key)
            effects.append({
                "quantity": expected.get("quantity"),
                "expected_direction": expected.get("expected_observation"),
                "weight": float(expected.get("weight", 1.0)),
                "evidence_type": expected.get("evidence_type"),
                "region_contains": expected.get("region_contains"),
                "principle_id": principle["principle_id"],
                "target_concept": principle["target_concept"],
            })
    return effects


def _matches_expected(item: dict[str, Any], expected: dict[str, Any]) -> bool:
    if item.get("quantity") != expected["quantity"]:
        return False
    if expected.get("evidence_type") and item.get("evidence_type") != expected["evidence_type"]:
        return False
    region = item.get("region") or ""
    return not expected.get("region_contains") or expected["region_contains"] in region


def build_parameter_effects(comparisons: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for comparison in comparisons:
        available = [item for item in evidence if item.get("comparison_id") == comparison["comparison_id"] and item.get("eligible_for_output")]
        for change in comparison.get("changed_parameters", []):
            expected = _expected_effects(change["parameter"], change["direction"])
            support, conflict, unavailable, context = [], [], [], []
            for effect in expected:
                matches = [item for item in available if _matches_expected(item, effect)]
                if effect["expected_direction"] == "context_dependent":
                    context.append(effect["quantity"])
                elif not matches:
                    unavailable.append(effect["quantity"])
                elif any(item.get("observation") == effect["expected_direction"] for item in matches):
                    support.extend(item["evidence_id"] for item in matches if item.get("observation") == effect["expected_direction"])
                else:
                    conflict.extend(item["evidence_id"] for item in matches if item.get("observation") != "unchanged")
            support = list(dict.fromkeys(support)); conflict = list(dict.fromkeys(conflict))
            if support and conflict: alignment = "partial"
            elif support: alignment = "consistent"
            elif conflict: alignment = "conflicting"
            elif context: alignment = "context_dependent"
            else: alignment = "insufficient"
            results.append({
                "effect_id": f"effect_{comparison['comparison_id']}_{change['parameter']}",
                "comparison_id": comparison["comparison_id"],
                "parameter": change["parameter"],
                "change_direction": change["direction"],
                "expected_effects": expected,
                "supporting_evidence_ids": support,
                "conflicting_evidence_ids": conflict,
                "unobserved_quantities": sorted(set(unavailable)),
                "context_dependent_quantities": sorted(set(context)),
                "alignment": alignment,
                "claim_level": comparison.get("effective_claim_level", "descriptive_only"),
            })
    return results


def _observed_direction(items: list[dict[str, Any]], quantity: str) -> tuple[str | None, list[str]]:
    matched = [item for item in items if item.get("quantity") == quantity and item.get("eligible_for_output")]
    directions = {item.get("observation") for item in matched if item.get("observation") != "unchanged"}
    return (next(iter(directions)) if len(directions) == 1 else ("conflicting" if len(directions) > 1 else None), [item["evidence_id"] for item in matched])


def build_parameter_interactions(comparisons: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for comparison in comparisons:
        changes = comparison.get("changed_parameters", [])
        if len(changes) < 2:
            continue
        available = [item for item in evidence if item.get("comparison_id") == comparison["comparison_id"]]
        by_quantity: dict[str, list[dict[str, str]]] = defaultdict(list)
        expected_by_parameter: dict[str, list[dict[str, Any]]] = {}
        for change in changes:
            effects = _expected_effects(change["parameter"], change["direction"])
            expected_by_parameter[change["parameter"]] = effects
            for effect in effects:
                if effect["expected_direction"] != "context_dependent":
                    by_quantity[effect["quantity"]].append({"parameter": change["parameter"], "expected_direction": effect["expected_direction"]})
        covered_pairs = set()
        for quantity, contributors in sorted(by_quantity.items()):
            parameters = {item["parameter"] for item in contributors}
            if len(parameters) < 2:
                continue
            directions = {item["expected_direction"] for item in contributors}
            interaction_type = "reinforcing" if len(directions) == 1 else "competing"
            observed, ids = _observed_direction(available, quantity)
            if observed is None: consistency = "insufficient"
            elif observed == "conflicting": consistency = "conflicting"
            elif interaction_type == "reinforcing": consistency = "consistent" if observed in directions else "conflicting"
            else: consistency = "consistent_with_one_contributor" if observed in directions else "conflicting"
            for pair in combinations(sorted(parameters), 2): covered_pairs.add(pair)
            results.append({
                "interaction_id": f"interaction_{comparison['comparison_id']}_{quantity}",
                "comparison_id": comparison["comparison_id"], "quantity": quantity,
                "interaction_type": interaction_type, "contributors": contributors,
                "observed_direction": observed, "observation_consistency": consistency,
                "evidence_ids": ids, "claim_level": "combined_association",
            })
        for left, right in combinations(changes, 2):
            pair = tuple(sorted((left["parameter"], right["parameter"])))
            if pair in covered_pairs:
                continue
            left_targets = sorted({item["target_concept"] for item in expected_by_parameter[left["parameter"]]})
            right_targets = sorted({item["target_concept"] for item in expected_by_parameter[right["parameter"]]})
            results.append({
                "interaction_id": f"interaction_{comparison['comparison_id']}_{pair[0]}_{pair[1]}",
                "comparison_id": comparison["comparison_id"], "quantity": None,
                "interaction_type": "independent", "contributors": [
                    {"parameter": left["parameter"], "target_concepts": left_targets},
                    {"parameter": right["parameter"], "target_concepts": right_targets},
                ],
                "observed_direction": None, "observation_consistency": "not_applicable",
                "evidence_ids": [], "claim_level": "combined_association",
            })
    return results


OBSERVED_TRADEOFF_PATTERNS = (
    ("off_state_control", "drive_performance", "leakage_reduction_with_drive_loss"),
    ("short_channel_control", "drive_performance", "short_channel_improvement_with_drive_loss"),
    ("drive_performance", "off_state_control", "drive_gain_with_leakage_penalty"),
    ("drive_performance", "saturation_behavior", "drive_gain_with_saturation_loss"),
)


def build_observed_tradeoffs(summaries: list[dict[str, Any]], conclusions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    by_comparison: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for summary in summaries:
        by_comparison[summary["comparison_id"]][summary["performance_area"]] = summary
    for comparison_id, areas in by_comparison.items():
        for gain, loss, pattern in OBSERVED_TRADEOFF_PATTERNS:
            if areas.get(gain, {}).get("assessment") == "improved" and areas.get(loss, {}).get("assessment") == "degraded":
                ids = list(dict.fromkeys(areas[gain]["evidence_ids"] + areas[loss]["evidence_ids"]))
                results.append({
                    "tradeoff_id": f"observed_tradeoff_{comparison_id}_{pattern}",
                    "comparison_id": comparison_id, "tradeoff_type": "observed_performance_tradeoff",
                    "result_pattern": pattern, "gain": gain, "loss": loss,
                    "claim_level": "descriptive", "evidence_ids": ids,
                    "confidence": "high" if all(areas[name]["support_level"] in {"supported", "strongly_supported"} for name in (gain, loss)) else "medium",
                })
    for conclusion in conclusions:
        if conclusion.get("conclusion_type") != "tradeoff" or not conclusion.get("eligible_for_output"):
            continue
        results.append({
            "tradeoff_id": "mechanism_" + conclusion["conclusion_id"],
            "comparison_id": conclusion["comparison_id"], "tradeoff_type": "mechanism_supported_tradeoff",
            "result_pattern": conclusion.get("label"), "gain": conclusion.get("positive_target"), "loss": conclusion.get("negative_target"),
            "claim_level": "controlled_association", "evidence_ids": list(dict.fromkeys(conclusion.get("positive_evidence_ids", []) + conclusion.get("negative_evidence_ids", []))),
            "confidence": conclusion.get("confidence", "medium"),
        })
    return results


def build_overall_assessment(summaries: list[dict[str, Any]], tradeoffs: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not summaries:
        return None
    by_comparison: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for summary in summaries:
        if summary["evaluation_mode"] == "preference_based": by_comparison[summary["comparison_id"]].append(summary)
    comparison_results = []
    for comparison_id, items in by_comparison.items():
        improved = [item for item in items if item["assessment"] == "improved"]
        degraded = [item for item in items if item["assessment"] == "degraded"]
        tradeoff = next((item for item in tradeoffs if item["comparison_id"] == comparison_id and item["tradeoff_type"] == "observed_performance_tradeoff"), None)
        if tradeoff: pattern = tradeoff["result_pattern"]
        elif improved and not degraded: pattern = "predominantly_improved"
        elif degraded and not improved: pattern = "predominantly_degraded"
        elif improved and degraded: pattern = "mixed_without_clear_priority"
        elif items and all(item["assessment"] == "unchanged" for item in items): pattern = "no_meaningful_change"
        else: pattern = "insufficient_for_overall_assessment"
        ranked_gain = sorted(improved, key=lambda item: (-item["importance_score"], item["performance_area"]))
        ranked_loss = sorted(degraded, key=lambda item: (-item["importance_score"], item["performance_area"]))
        comparison_results.append({
            "comparison_id": comparison_id, "result_pattern": pattern,
            "primary_gain": ranked_gain[0]["performance_area"] if ranked_gain else None,
            "primary_loss": ranked_loss[0]["performance_area"] if ranked_loss else None,
            "improved_areas": [item["performance_area"] for item in improved],
            "degraded_areas": [item["performance_area"] for item in degraded],
            "supporting_summary_ids": [item["summary_id"] for item in items],
            "confidence": "high" if items and all(item["support_level"] in {"supported", "strongly_supported"} for item in improved + degraded) else "medium",
        })
    return {"comparison_results": comparison_results, "primary_comparison_id": comparison_results[0]["comparison_id"] if comparison_results else None}


def _effect_size(summary: dict[str, Any], evidence_by_id: dict[str, dict[str, Any]]) -> float:
    values = []
    for evidence_id in summary.get("evidence_ids", []):
        item = evidence_by_id.get(evidence_id, {})
        data = item.get("data", {})
        if data.get("decade_difference") is not None:
            values.append(abs(float(data["decade_difference"])) * 100.0)
        elif data.get("percent_difference") is not None:
            values.append(abs(float(data["percent_difference"])))
        else:
            values.append(float(MAGNITUDE_RANK.get(item.get("magnitude_class"), 0)) * 10.0)
    return max(values, default=0.0)


def build_variant_rankings(comparisons: list[dict[str, Any]], summaries: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    primary = {item["comparison_id"]: item for item in comparisons if item.get("comparison_role") == "primary_baseline_to_variant"}
    if len(primary) < 2:
        return []
    evidence_by_id = {item["evidence_id"]: item for item in evidence}
    by_area: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for summary in summaries:
        if summary["comparison_id"] not in primary or summary["evaluation_mode"] != "preference_based":
            continue
        comparison = primary[summary["comparison_id"]]
        strength = _effect_size(summary, evidence_by_id)
        assessment = summary["assessment"]
        category = {"improved": 3, "unchanged": 2, "mixed": 1, "degraded": 0, "insufficient": -1}[assessment]
        within = strength if assessment == "improved" else (-strength if assessment == "degraded" else 0.0)
        by_area[summary["performance_area"]].append({
            "comparison_id": summary["comparison_id"],
            "candidate_subject_id": comparison["candidate_subject_id"],
            "assessment": assessment,
            "effect_size_score": strength,
            "ranking_score": category * 10000.0 + within,
            "summary_id": summary["summary_id"],
        })
    results = []
    for area, variants in sorted(by_area.items()):
        if len(variants) < 2:
            continue
        ordered = sorted(variants, key=lambda item: (-item["ranking_score"], item["candidate_subject_id"]))
        for rank, item in enumerate(ordered, 1): item["rank"] = rank
        clear = len(ordered) == 1 or ordered[0]["ranking_score"] != ordered[1]["ranking_score"]
        results.append({
            "ranking_id": f"ranking_{area}", "performance_area": area,
            "baseline_subject_id": primary[ordered[0]["comparison_id"]]["baseline_subject_id"],
            "variants": ordered,
            "best_candidate_subject_id": ordered[0]["candidate_subject_id"] if clear else None,
            "worst_candidate_subject_id": ordered[-1]["candidate_subject_id"] if clear else None,
            "ranking_basis": "assessment_then_observed_effect_magnitude",
        })
    return results


def build_curve_interpretation(comparisons: list[dict[str, Any]], evidence: list[dict[str, Any]], conclusions: list[dict[str, Any]]) -> dict[str, Any]:
    result = build_interpretation_scaffold("iv_curve_comparison" if comparisons else "iv_curve_single")
    if not comparisons:
        result["status"] = "insufficient"
        return result
    summaries = build_performance_summaries(comparisons, evidence)
    effects = build_parameter_effects(comparisons, evidence)
    mechanisms = build_iv_mechanism_chains(comparisons, evidence)
    interactions = build_parameter_interactions(comparisons, evidence)
    tradeoffs = build_observed_tradeoffs(summaries, conclusions)
    overall = build_overall_assessment(summaries, tradeoffs)
    rankings = build_variant_rankings(comparisons, summaries, evidence)
    result.update({
        "status": "complete" if summaries else "insufficient",
        "performance_summaries": summaries,
        "parameter_effects": effects,
        "mechanism_chains": mechanisms,
        "parameter_interactions": interactions,
        "observed_tradeoffs": tradeoffs,
        "variant_rankings": rankings,
        "overall_assessment": overall,
    })
    return result


def validate_curve_interpretation(value: dict[str, Any], comparisons: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> None:
    comparison_ids = {item["comparison_id"] for item in comparisons}
    evidence_ids = {item["evidence_id"] for item in evidence}
    for summary in value.get("performance_summaries", []):
        if summary.get("comparison_id") not in comparison_ids:
            raise ValueError("Performance summary references an unknown comparison.")
        if summary.get("assessment") not in CURVE_ASSESSMENTS or summary.get("support_level") not in SUPPORT_LEVELS:
            raise ValueError("Invalid performance summary classification.")
        if not set(summary.get("evidence_ids", [])).issubset(evidence_ids):
            raise ValueError("Performance summary references unknown evidence.")
    for effect in value.get("parameter_effects", []):
        if effect.get("comparison_id") not in comparison_ids:
            raise ValueError("Parameter effect references an unknown comparison.")
        ids = set(effect.get("supporting_evidence_ids", [])) | set(effect.get("conflicting_evidence_ids", []))
        if not ids.issubset(evidence_ids):
            raise ValueError("Parameter effect references unknown evidence.")
    for mechanism in value.get("mechanism_chains", []):
        if mechanism.get("comparison_id") not in comparison_ids:
            raise ValueError("Mechanism chain references an unknown comparison.")
        ids = (
            set(mechanism.get("supporting_evidence_ids", []))
            | set(mechanism.get("conflicting_evidence_ids", []))
        )
        link_ids = {
            item.get("evidence_id")
            for item in mechanism.get("observed_metric_links", [])
        }
        if (
            not ids.issubset(evidence_ids)
            or not link_ids.issubset(evidence_ids)
            or mechanism.get("support_level") not in SUPPORT_LEVELS
        ):
            raise ValueError("Invalid mechanism chain evidence.")
    for interaction in value.get("parameter_interactions", []):
        if interaction.get("comparison_id") not in comparison_ids or interaction.get("interaction_type") not in INTERACTION_TYPES:
            raise ValueError("Invalid parameter interaction.")
        if not set(interaction.get("evidence_ids", [])).issubset(evidence_ids):
            raise ValueError("Parameter interaction references unknown evidence.")
    for tradeoff in value.get("observed_tradeoffs", []):
        if tradeoff.get("comparison_id") not in comparison_ids or not set(tradeoff.get("evidence_ids", [])).issubset(evidence_ids):
            raise ValueError("Invalid observed trade-off references.")
