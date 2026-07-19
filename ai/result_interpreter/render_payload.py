from __future__ import annotations

from typing import Any


def _referenced_evidence_ids(conclusions: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for conclusion in conclusions:
        for key, value in conclusion.items():
            if key.endswith("evidence_ids") and isinstance(value, list): ids.update(str(item) for item in value)
    return ids


def build_llm_render_payload(payload: dict[str, Any], *, max_evidence: int = 20, max_conclusions: int = 12, max_warnings: int = 8) -> dict[str, Any]:
    conclusions = [item for item in payload.get("conclusions", []) if item.get("eligible_for_output", True)][:max_conclusions]
    required = _referenced_evidence_ids(conclusions)
    evidence = [item for item in payload.get("evidence", []) if item.get("selected_for_explanation") or item.get("evidence_id") in required]
    evidence.sort(key=lambda item: (not item.get("selected_for_explanation"), -float(item.get("importance_score", 0))))
    warnings = [item for item in payload.get("warnings", []) if item.get("eligible_for_output", True)][:max_warnings]
    return {key: payload.get(key) for key in ("schema_version", "analysis_id", "analysis_type", "context", "subjects", "comparisons")} | {
        "evidence": evidence[:max_evidence], "conclusions": conclusions, "warnings": warnings, "output_policy": payload.get("output_policy", {})}
