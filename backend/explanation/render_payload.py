from __future__ import annotations

from typing import Any


def _referenced_evidence_ids(conclusions: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for conclusion in conclusions:
        for key, value in conclusion.items():
            if key.endswith("evidence_ids") and isinstance(value, list): ids.update(str(item) for item in value)
    return ids


def _compact_interpretation(payload: dict[str, Any]) -> dict[str, Any] | None:
    interpretation = payload.get("interpretation")
    if not isinstance(interpretation, dict) or interpretation.get("status") == "not_computed":
        return None
    common = {key: interpretation.get(key) for key in ("contract_version", "analysis_family", "status", "overall_assessment")}
    if interpretation.get("analysis_family") == "curve":
        return common | {
            "performance_summaries": interpretation.get("performance_summaries", [])[:20],
            "parameter_effects": interpretation.get("parameter_effects", [])[:12],
            "parameter_interactions": interpretation.get("parameter_interactions", [])[:12],
            "observed_tradeoffs": interpretation.get("observed_tradeoffs", [])[:8],
            "variant_rankings": interpretation.get("variant_rankings", [])[:8],
        }
    field_conclusions = interpretation.get("field_specific_conclusions", [])[:8]
    required_features = {
        str(feature_id)
        for item in field_conclusions
        for feature_id in item.get("spatial_feature_ids", [])
    }
    features = [
        item for item in interpretation.get("spatial_features", [])
        if item.get("feature_id") in required_features
    ][:16]
    geometry = interpretation.get("geometry_context") or {}
    return common | {
        "geometry_comparison_policy": geometry.get("comparison", {}),
        "analysis_quality": interpretation.get("analysis_quality", {}),
        "field_specific_conclusions": field_conclusions,
        "supporting_spatial_features": features,
        "cross_domain_links": interpretation.get("cross_domain_links", [])[:6],
    }


def build_llm_render_payload(payload: dict[str, Any], *, max_evidence: int = 20, max_conclusions: int = 12, max_warnings: int = 8) -> dict[str, Any]:
    conclusions = [item for item in payload.get("conclusions", []) if item.get("eligible_for_output", True)][:max_conclusions]
    interpretation = _compact_interpretation(payload)
    interpretation_conclusions = (interpretation or {}).get("field_specific_conclusions", [])
    required = _referenced_evidence_ids([*conclusions, *interpretation_conclusions])
    evidence = [item for item in payload.get("evidence", []) if item.get("selected_for_explanation") or item.get("evidence_id") in required]
    evidence.sort(key=lambda item: (not item.get("selected_for_explanation"), -float(item.get("importance_score", 0))))
    warnings = [item for item in payload.get("warnings", []) if item.get("eligible_for_output", True)][:max_warnings]
    result = {key: payload.get(key) for key in ("schema_version", "analysis_id", "analysis_type", "context", "subjects", "comparisons")} | {
        "evidence": evidence[:max_evidence], "conclusions": conclusions, "warnings": warnings, "output_policy": payload.get("output_policy", {})}
    if interpretation is not None:
        result["interpretation"] = interpretation
    return result
