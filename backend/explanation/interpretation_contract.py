from __future__ import annotations

from typing import Any


INTERPRETATION_CONTRACT_VERSION = "1.0"
CURVE_ASSESSMENTS = {"improved", "degraded", "mixed", "unchanged", "insufficient"}
SUPPORT_LEVELS = {"tentative", "supported", "strongly_supported", "conflicting", "insufficient"}
INTERACTION_TYPES = {"reinforcing", "competing", "independent", "context_dependent", "insufficient"}
FIELD_QUALITY_LEVELS = {"high", "medium", "low", "valid", "invalid", "unknown", "not_applicable"}


def build_interpretation_scaffold(analysis_type: str) -> dict[str, Any]:
    """Create the stable analyzer-to-renderer contract populated in later phases."""
    common: dict[str, Any] = {
        "contract_version": INTERPRETATION_CONTRACT_VERSION,
        "analysis_family": "curve" if analysis_type.startswith("iv_curve_") else "field",
        "status": "not_computed",
        "overall_assessment": None,
    }
    if common["analysis_family"] == "curve":
        return common | {
            "performance_summaries": [],
            "parameter_effects": [],
            "parameter_interactions": [],
            "observed_tradeoffs": [],
            "variant_rankings": [],
        }
    return common | {
        "geometry_context": None,
        "analysis_quality": {},
        "regional_summaries": [],
        "spatial_features": [],
        "field_specific_conclusions": [],
        "cross_domain_links": [],
    }


def validate_interpretation_contract(value: dict[str, Any], analysis_type: str) -> None:
    if not isinstance(value, dict):
        raise ValueError("Interpretation contract must be an object.")
    family = "curve" if analysis_type.startswith("iv_curve_") else "field"
    common = {"contract_version", "analysis_family", "status", "overall_assessment"}
    curve = {"performance_summaries", "parameter_effects", "parameter_interactions", "observed_tradeoffs", "variant_rankings"}
    field_keys = {"geometry_context", "analysis_quality", "regional_summaries", "spatial_features", "field_specific_conclusions", "cross_domain_links"}
    required = common | (curve if family == "curve" else field_keys)
    if not required.issubset(value):
        raise ValueError("Interpretation contract is missing required sections.")
    if value["contract_version"] != INTERPRETATION_CONTRACT_VERSION or value["analysis_family"] != family:
        raise ValueError("Interpretation contract version or family mismatch.")
    if value["status"] not in {"not_computed", "partial", "complete", "insufficient"}:
        raise ValueError("Unsupported interpretation status.")
    list_keys = curve if family == "curve" else field_keys - {"geometry_context", "analysis_quality"}
    if any(not isinstance(value[key], list) for key in list_keys):
        raise ValueError("Interpretation collection sections must be arrays.")
    if family == "field" and not isinstance(value["analysis_quality"], dict):
        raise ValueError("Field analysis_quality must be an object.")

