from __future__ import annotations

from collections import defaultdict
from typing import Any

from .physical_principles import FORBIDDEN_CLAIM_TERMS, PHYSICAL_PRINCIPLES

CLAIM_LEVELS = {"descriptive_only", "multi_parameter_association", "controlled_association", "cross_validated_controlled_association"}
CONSISTENCIES = {"consistent", "partially_consistent", "inconsistent", "insufficient_evidence", "not_evaluated"}
CLAIM_REDUCTION_REASONS = {"extrapolation", "low_confidence", "missing_critical_region", "parameter_extraction_failure",
                           "conflicting_evidence", "negligible_change", "model_derived_approximation", "insufficient_evidence",
                           "invalid_data", "multiple_parameter_change"}
CROSS_VALIDATION_BONUS = .05


def determine_declared_claim_level(changed_parameter_count: int) -> str:
    if changed_parameter_count == 0:
        return "descriptive_only"
    if changed_parameter_count == 1:
        return "controlled_association"
    return "multi_parameter_association"


def match_evidence_to_principle(evidence: list[dict[str, Any]], principle: dict[str, Any]) -> dict[str, Any]:
    supporting, contradicting, neutral, unavailable = [], [], [], []
    support_score = contradict_score = neutral_score = 0.0
    context_dependent = True
    for expected in principle["expected_evidence"]:
        expected_observation = expected["expected_observation"]
        if expected_observation == "context_dependent":
            continue
        context_dependent = False
        candidates = [item for item in evidence if item.get("quantity") == expected["quantity"]
                      and (not expected.get("evidence_type") or item.get("evidence_type") == expected["evidence_type"])
                      and (not expected.get("region_contains") or expected["region_contains"] in (item.get("region") or ""))]
        if not candidates:
            unavailable.append(expected["quantity"]); continue
        for item in candidates:
            weight = float(expected.get("weight", 1.0))
            if item.get("confidence") == "low" or "invalid_data" in item.get("suppression_reasons", []):
                unavailable.append(item["evidence_id"]); continue
            if item.get("magnitude_class") == "negligible" or item.get("observation") == "unchanged":
                neutral.append(item["evidence_id"]); neutral_score += weight
            elif item.get("observation") == expected_observation:
                supporting.append(item["evidence_id"]); support_score += weight
            else:
                contradicting.append(item["evidence_id"]); contradict_score += weight
    consistency = evaluate_physical_consistency(support_score, contradict_score, context_dependent=context_dependent)
    return {"supporting_evidence_ids": list(dict.fromkeys(supporting)), "contradicting_evidence_ids": list(dict.fromkeys(contradicting)),
            "neutral_evidence_ids": list(dict.fromkeys(neutral)), "unavailable_evidence": unavailable,
            "support_score": support_score, "contradict_score": contradict_score, "neutral_score": neutral_score,
            "physical_consistency": consistency}


def evaluate_physical_consistency(support_score: float, contradict_score: float, *, context_dependent: bool = False) -> str:
    if context_dependent:
        return "not_evaluated"
    if support_score and contradict_score:
        return "partially_consistent"
    if support_score:
        return "consistent"
    if contradict_score:
        return "inconsistent"
    return "insufficient_evidence"


def _warnings_for_comparison(warnings: list[dict[str, Any]], comparison: dict[str, Any]) -> set[str]:
    subject_ids = {comparison["baseline_subject_id"], comparison["candidate_subject_id"]}
    result = set()
    for warning in warnings:
        linked = set(warning.get("subject_ids", []))
        details_comparison = warning.get("details", {}).get("comparison_id")
        if not linked or linked & subject_ids or details_comparison == comparison["comparison_id"]:
            result.add(warning["warning_type"])
            if warning.get("severity") == "critical":
                result.add("__critical__")
    return result


def determine_effective_claim_level(declared: str, *, valid_evidence: list[dict[str, Any]], warning_types: set[str],
                                    conflicting: bool = False, cross_validated: bool = False) -> tuple[str, list[str]]:
    reasons = []
    if declared == "multi_parameter_association":
        reasons.append("multiple_parameter_change")
        if "__critical__" in warning_types:
            reasons.append("invalid_data")
            return "descriptive_only", reasons
        return declared, reasons
    if not valid_evidence:
        reasons.append("insufficient_evidence")
    if valid_evidence and all(item.get("magnitude_class") == "negligible" for item in valid_evidence):
        reasons.append("negligible_change")
    if valid_evidence and all(item.get("confidence") == "low" for item in valid_evidence):
        reasons.append("low_confidence")
    warning_mapping = {"extrapolation": "extrapolation", "missing_region": "missing_critical_region",
                       "parameter_extraction_failed": "parameter_extraction_failure", "invalid_numeric_value": "invalid_data"}
    reasons.extend(reason for warning, reason in warning_mapping.items() if warning in warning_types)
    if "__critical__" in warning_types:
        reasons.append("invalid_data")
    if conflicting:
        reasons.append("conflicting_evidence")
    if valid_evidence and all(item.get("source_type") == "energy_band_analyzer" for item in valid_evidence):
        reasons.append("model_derived_approximation")
    reasons = list(dict.fromkeys(reasons))
    if declared == "descriptive_only" or any(reason in reasons for reason in {"extrapolation", "insufficient_evidence", "low_confidence", "negligible_change", "invalid_data"}):
        return "descriptive_only", reasons
    if cross_validated and not conflicting and "model_derived_approximation" not in reasons:
        return "cross_validated_controlled_association", reasons
    return "controlled_association", reasons


def _importance(ids: list[str], evidence_by_id: dict[str, dict[str, Any]], bonus: float = 0.0, penalty: float = 0.0) -> float:
    values = [float(evidence_by_id[item].get("importance_score", .5)) for item in ids if item in evidence_by_id]
    return max(0.0, min(1.0, (sum(values) / len(values) if values else .5) + bonus - penalty))


def build_no_meaningful_difference_conclusion(comparison: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any] | None:
    relevant = [item for item in evidence if item.get("comparison_id") == comparison["comparison_id"]]
    if not relevant or not all(item.get("magnitude_class") == "negligible" for item in relevant):
        return None
    return {"conclusion_id": f"conclusion_{comparison['comparison_id']}_no_meaningful_difference", "conclusion_type": "no_meaningful_difference",
            "comparison_id": comparison["comparison_id"], "supporting_evidence_ids": [item["evidence_id"] for item in relevant],
            "effective_claim_level": "descriptive_only", "claim_reduction_reasons": ["negligible_change"],
            "importance_score": .7, "eligible_for_output": True}


def build_analysis_conclusions(comparisons: list[dict[str, Any]], evidence: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conclusions = []; evidence_by_id = {item["evidence_id"]: item for item in evidence}
    for comparison in comparisons:
        declared = determine_declared_claim_level(comparison["changed_parameter_count"])
        comparison_evidence = [item for item in evidence if item.get("comparison_id") == comparison["comparison_id"]]
        warning_types = _warnings_for_comparison(warnings, comparison)
        comparison["declared_claim_level"] = declared
        if comparison["changed_parameter_count"] >= 2:
            effective, reasons = determine_effective_claim_level(declared, valid_evidence=comparison_evidence, warning_types=warning_types)
            principle_ids = [principle["principle_id"] for change in comparison["changed_parameters"]
                             for principle in PHYSICAL_PRINCIPLES.get((change["parameter"], change["direction"]), [])]
            parameter_effects = []
            for change in comparison["changed_parameters"]:
                principles = PHYSICAL_PRINCIPLES.get((change["parameter"], change["direction"]), [])
                matches = [match_evidence_to_principle(comparison_evidence, principle) for principle in principles]
                supporting = list(dict.fromkeys(item for match in matches for item in match["supporting_evidence_ids"]))
                contradicting = list(dict.fromkeys(item for match in matches for item in match["contradicting_evidence_ids"]))
                support_score = sum(match["support_score"] for match in matches)
                contradict_score = sum(match["contradict_score"] for match in matches)
                parameter_effects.append({
                    "parameter": change["parameter"], "direction": change["direction"],
                    "principle_ids": [item["principle_id"] for item in principles],
                    "supporting_evidence_ids": supporting, "contradicting_evidence_ids": contradicting,
                    "support_score": support_score, "contradict_score": contradict_score,
                    "alignment_score": support_score - contradict_score,
                })
            ranked = sorted(parameter_effects, key=lambda item: (-item["alignment_score"], item["parameter"]))
            expected_by_parameter = []
            for change in comparison["changed_parameters"]:
                directions: dict[str, set[str]] = defaultdict(set)
                for principle in PHYSICAL_PRINCIPLES.get((change["parameter"], change["direction"]), []):
                    for expected_item in principle["expected_evidence"]:
                        direction = expected_item["expected_observation"]
                        if direction != "context_dependent": directions[expected_item["quantity"]].add(direction)
                expected_by_parameter.append(directions)
            reinforcing_quantities, competing_quantities = set(), set()
            if len(expected_by_parameter) >= 2:
                shared = set.intersection(*(set(item) for item in expected_by_parameter))
                for quantity in shared:
                    directions = [item[quantity] for item in expected_by_parameter]
                    combined = set().union(*directions)
                    if len(combined) == 1: reinforcing_quantities.add(quantity)
                    else: competing_quantities.add(quantity)
            dominant_alignment_parameter = None
            if ranked and ranked[0]["support_score"] > 0:
                runner_up = ranked[1]["alignment_score"] if len(ranked) > 1 else 0.0
                if ranked[0]["alignment_score"] - runner_up >= .5:
                    dominant_alignment_parameter = ranked[0]["parameter"]
            conclusion = {"conclusion_id": f"conclusion_{comparison['comparison_id']}_multi_parameter", "conclusion_type": "multi_parameter_association",
                          "comparison_id": comparison["comparison_id"], "changed_parameters": [item["parameter"] for item in comparison["changed_parameters"]],
                          "principle_ids": principle_ids,
                          "parameter_effects": parameter_effects, "dominant_alignment_parameter": dominant_alignment_parameter,
                          "reinforcing_quantities": sorted(reinforcing_quantities), "competing_quantities": sorted(competing_quantities),
                          "supporting_evidence_ids": [item["evidence_id"] for item in comparison_evidence if item.get("eligible_for_output")],
                          "effective_claim_level": effective, "claim_reduction_reasons": reasons, "importance_score": .7, "eligible_for_output": True}
            conclusions.append(conclusion); comparison.update({"effective_claim_level": effective, "claim_reduction_reasons": reasons, "causal_claim_level": effective}); continue
        if comparison["changed_parameter_count"] == 0:
            comparison.update({"effective_claim_level": "descriptive_only", "claim_reduction_reasons": ["insufficient_evidence"], "causal_claim_level": "descriptive_only"}); continue
        change = comparison["changed_parameters"][0]
        principles = PHYSICAL_PRINCIPLES.get((change["parameter"], change["direction"]), [])
        relationship_results = []
        for principle in principles:
            matched = match_evidence_to_principle(comparison_evidence, principle); consistency = matched["physical_consistency"]
            relevant_ids = matched["supporting_evidence_ids"] + matched["contradicting_evidence_ids"] + matched["neutral_evidence_ids"]
            relationship_results.append((principle, matched))
            conclusions.append({"conclusion_id": f"conclusion_{comparison['comparison_id']}_{principle['principle_id']}", "conclusion_type": "physical_relationship",
                                "comparison_id": comparison["comparison_id"], "changed_parameter": change["parameter"], "change_direction": change["direction"],
                                "principle_id": principle["principle_id"], "statement_key": principle["statement_key"], "target_concept": principle["target_concept"],
                                "supporting_evidence_ids": matched["supporting_evidence_ids"], "contradicting_evidence_ids": matched["contradicting_evidence_ids"],
                                "neutral_evidence_ids": matched["neutral_evidence_ids"], "physical_consistency": consistency,
                                "declared_claim_level": declared, "effective_claim_level": "controlled_association" if relevant_ids else "descriptive_only",
                                "claim_reduction_reasons": [] if relevant_ids else ["insufficient_evidence"],
                                "importance_score": _importance(relevant_ids, evidence_by_id, penalty=.05 if matched["contradicting_evidence_ids"] else 0),
                                "eligible_for_output": consistency not in {"insufficient_evidence", "not_evaluated"},
                                "forbidden_claim_terms": FORBIDDEN_CLAIM_TERMS})
        conflicts = [(p, m) for p, m in relationship_results if m["supporting_evidence_ids"] and m["contradicting_evidence_ids"]]
        for principle, matched in conflicts:
            conclusions.append({"conclusion_id": f"conclusion_{comparison['comparison_id']}_{principle['target_concept']}_conflict",
                                "conclusion_type": "conflicting_physical_evidence", "comparison_id": comparison["comparison_id"],
                                "target_concept": principle["target_concept"], "supporting_evidence_ids": matched["supporting_evidence_ids"],
                                "contradicting_evidence_ids": matched["contradicting_evidence_ids"], "physical_consistency": "partially_consistent",
                                "effective_claim_level": "controlled_association", "claim_reduction_reasons": ["conflicting_evidence"],
                                "importance_score": _importance(matched["supporting_evidence_ids"] + matched["contradicting_evidence_ids"], evidence_by_id, penalty=.05), "eligible_for_output": True})
        cross_candidates = []
        for principle, matched in relationship_results:
            support = [evidence_by_id[item] for item in matched["supporting_evidence_ids"] if item in evidence_by_id]
            independent = len({item["source_type"] for item in support}) >= 2
            direct_support = [item for item in support if item["source_type"] != "energy_band_analyzer"]
            if len(support) >= 2 and independent and direct_support and not matched["contradicting_evidence_ids"] and "extrapolation" not in warning_types:
                cross_candidates.append((principle, support))
        for principle, support in cross_candidates:
            ids = [item["evidence_id"] for item in support]
            conclusions.append({"conclusion_id": f"conclusion_{comparison['comparison_id']}_{principle['target_concept']}_cross_validation",
                                "conclusion_type": "cross_validated_physical_trend", "comparison_id": comparison["comparison_id"],
                                "target_concept": principle["target_concept"], "supporting_evidence_ids": ids,
                                "source_types": sorted({item["source_type"] for item in support}), "physical_consistency": "consistent",
                                "declared_claim_level": declared, "effective_claim_level": "cross_validated_controlled_association",
                                "claim_reduction_reasons": [], "importance_score": _importance(ids, evidence_by_id, bonus=CROSS_VALIDATION_BONUS), "eligible_for_output": True})
        valid = [item for item in comparison_evidence if item.get("eligible_for_output")]
        effective, reasons = determine_effective_claim_level(declared, valid_evidence=valid, warning_types=warning_types,
                                                              conflicting=bool(conflicts), cross_validated=bool(cross_candidates))
        comparison.update({"effective_claim_level": effective, "claim_reduction_reasons": reasons, "causal_claim_level": effective})
        for conclusion in conclusions:
            if conclusion.get("comparison_id") == comparison["comparison_id"] and conclusion["conclusion_type"] in {"physical_relationship", "conflicting_physical_evidence"}:
                conclusion["effective_claim_level"] = effective
                conclusion["claim_reduction_reasons"] = reasons
        no_difference = build_no_meaningful_difference_conclusion(comparison, comparison_evidence)
        if no_difference:
            conclusions.append(no_difference)
    return conclusions


build_physical_relationship_conclusions = build_analysis_conclusions
build_cross_validation_conclusions = build_analysis_conclusions
build_conflicting_evidence_conclusions = build_analysis_conclusions
