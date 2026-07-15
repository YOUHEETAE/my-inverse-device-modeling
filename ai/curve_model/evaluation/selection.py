from __future__ import annotations


def kind_selection_score(kind: str, metrics: dict[str, object]) -> dict[str, float]:
    """Return the validation-tail score fixed before model optimization."""
    if kind not in {"idvd", "idvg"}:
        raise ValueError(f"Unknown curve kind: {kind}")
    distributions = metrics["per_curve_distributions"]
    p95_nrmse = float(distributions["nrmse"]["p95"])
    p95_decade = float(distributions["decade_mae"]["p95"])
    score = (
        p95_nrmse + 0.25 * p95_decade
        if kind == "idvd"
        else p95_decade + 0.10 * p95_nrmse
    )
    return {
        "p95_nrmse": p95_nrmse,
        "p95_decade_mae": p95_decade,
        "score": score,
    }


def combined_selection_score(curve_metrics: dict[str, object]) -> dict[str, object]:
    per_kind = {
        kind: kind_selection_score(kind, curve_metrics[kind])
        for kind in ("idvd", "idvg")
    }
    score = sum(item["score"] for item in per_kind.values()) / len(per_kind)
    return {"score": score, "direction": "minimize", "per_kind": per_kind}
