from __future__ import annotations

from typing import Any


MAX_CROSS_DOMAIN_FACTS = 10


def _metric_matches(quantity: str, requested: set[str]) -> bool:
    if quantity in requested:
        return True
    return "vth" in requested and quantity.startswith("vth_")


def build_field_iv_audit(
    field_payload: dict[str, Any],
    iv_payload: dict[str, Any] | None,
    *,
    requested_metrics: set[str] | None = None,
    comparison_ids: set[str] | None = None,
    field_links: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Join two already-validated analyses without inventing causality.

    Field observations remain spatial evidence. I-V observations remain
    electrical evidence. The audit only establishes that the corresponding
    electrical metric is available for the same selected device comparison.
    """
    links = (
        list(field_links)
        if field_links is not None
        else list(
            (field_payload.get("interpretation") or {}).get(
                "cross_domain_links", []
            )
        )
    )
    linked_metrics = {
        str(metric)
        for link in links
        for metric in link.get("iv_metrics_to_check", [])
    }
    if requested_metrics:
        linked_metrics &= set(requested_metrics)
    result = {
        "status": "iv_result_unavailable",
        "subject_alignment": "not_checked",
        "verified_iv_facts": [],
        "linked_metrics": sorted(linked_metrics),
        "claim_boundary": (
            "Field and I-V observations may be discussed together, but the "
            "Field pattern does not prove that it caused the I-V change."
        ),
    }
    if not iv_payload:
        return result
    field_subjects = [
        (
            str(item.get("display_name")),
            item.get("device_parameters", {}),
        )
        for item in field_payload.get("subjects", [])
    ]
    iv_subjects = [
        (
            str(item.get("display_name")),
            item.get("device_parameters", {}),
        )
        for item in iv_payload.get("subjects", [])
    ]
    if field_subjects != iv_subjects:
        result["status"] = "subject_mismatch"
        result["subject_alignment"] = "mismatch"
        return result
    result["subject_alignment"] = "exact"
    facts = []
    for item in iv_payload.get("evidence", []):
        quantity = str(item.get("quantity", ""))
        if (
            item.get("eligible_for_output", True)
            and item.get("evidence_type") == "metric_change"
            and item.get("evidence_id")
            and (
                comparison_ids is None
                or item.get("comparison_id") in comparison_ids
            )
            and _metric_matches(quantity, linked_metrics)
        ):
            data = item.get("data", {})
            facts.append({
                "evidence_id": str(item["evidence_id"]),
                "quantity": quantity,
                "observation": item.get("observation"),
                "assessment": item.get("assessment"),
                "confidence": item.get("confidence"),
                "baseline": data.get("baseline"),
                "candidate": data.get("candidate"),
                "unit": data.get("unit"),
                "source_domain": "iv_curve",
            })
    facts.sort(key=lambda item: (item["quantity"], item["evidence_id"]))
    result["verified_iv_facts"] = facts[:MAX_CROSS_DOMAIN_FACTS]
    result["status"] = (
        "verified_iv_evidence_available" if facts else "linked_metric_not_available"
    )
    return result


def validate_field_iv_audit(audit: dict[str, Any]) -> None:
    allowed_status = {
        "iv_result_unavailable",
        "subject_mismatch",
        "verified_iv_evidence_available",
        "linked_metric_not_available",
    }
    if audit.get("status") not in allowed_status:
        raise ValueError("invalid_cross_domain_status")
    facts = audit.get("verified_iv_facts")
    if not isinstance(facts, list) or len(facts) > MAX_CROSS_DOMAIN_FACTS:
        raise ValueError("invalid_cross_domain_facts")
    if audit.get("status") == "verified_iv_evidence_available" and not facts:
        raise ValueError("cross_domain_status_without_evidence")
    for item in facts:
        if (
            item.get("source_domain") != "iv_curve"
            or not item.get("evidence_id")
            or item.get("observation") not in {
                "increased", "decreased", "negligible", "changed",
            }
        ):
            raise ValueError("invalid_cross_domain_fact")
