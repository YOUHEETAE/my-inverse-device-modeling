from __future__ import annotations

from typing import Any


def select_observed_tradeoffs_for_output(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return trade-offs that the deterministic renderer is expected to cover."""
    interpretation = payload.get("interpretation") or {}
    observed = list(interpretation.get("observed_tradeoffs") or [])
    if not observed:
        return []

    plan = payload.get("comparison_plan") or {}
    mode = plan.get("analysis_mode")
    if mode == "controlled_sweep":
        # Sweep output derives a single aggregate trade-off from the ordered
        # metric trends. Pairwise trade-offs are not individually rendered.
        return []
    if mode != "mixed_group":
        return observed

    controlled_ids = set(plan.get("controlled_pair_ids") or [])
    controlled = [
        item for item in observed
        if item.get("comparison_id") in controlled_ids
    ]
    if controlled:
        return controlled

    compound_ids = set(plan.get("compound_pair_ids") or [])
    compound = [
        item for item in observed
        if item.get("comparison_id") in compound_ids
    ]
    return compound or observed


def deterministic_draft_requires_tradeoff(payload: dict[str, Any]) -> bool:
    """Apply the same trade-off scope used by the deterministic renderer."""
    interpretation = payload.get("interpretation") or {}
    if (
        str(payload.get("analysis_type", "")).startswith("iv_curve_")
        and interpretation.get("analysis_family") == "curve"
        and interpretation.get("status") in {"partial", "complete"}
    ):
        return bool(select_observed_tradeoffs_for_output(payload))
    return any(
        item.get("conclusion_type") == "tradeoff"
        and item.get("eligible_for_output", True)
        for item in payload.get("conclusions", [])
    )
