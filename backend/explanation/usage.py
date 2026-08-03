from __future__ import annotations

from typing import Any, Iterable


def consume_provider_diagnostic(
    provider: Any,
    *,
    stage: str,
) -> dict[str, Any]:
    """Consume successful-call metadata without requiring it from test providers."""
    consumer = getattr(provider, "consume_last_call_diagnostic", None)
    if not callable(consumer):
        return {}
    value = consumer()
    if not isinstance(value, dict) or not value:
        return {}
    result = dict(value)
    result["stage"] = stage
    return result


def summarize_usage(
    diagnostics: Iterable[dict[str, Any]],
) -> dict[str, int | float]:
    calls = 0
    usage_reported_calls = 0
    prompt_tokens = completion_tokens = total_tokens = 0
    request_bytes = 0
    duration_ms = 0.0
    for item in diagnostics:
        if not isinstance(item, dict):
            continue
        if item.get("category") == "cache_hit":
            continue
        calls += 1
        value = item.get("request_bytes")
        if isinstance(value, int) and not isinstance(value, bool):
            request_bytes += value
        value = item.get("duration_ms")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            duration_ms += float(value)
        usage = item.get("usage")
        if not isinstance(usage, dict):
            continue
        if any(
            isinstance(usage.get(name), int)
            for name in ("prompt_tokens", "completion_tokens", "total_tokens")
        ):
            usage_reported_calls += 1
        prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens += int(usage.get("completion_tokens", 0) or 0)
        total_tokens += int(usage.get("total_tokens", 0) or 0)
    return {
        "calls": calls,
        "usage_reported_calls": usage_reported_calls,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "request_bytes": request_bytes,
        "duration_ms": round(duration_ms, 1),
    }


def format_usage_summary(
    diagnostics: Iterable[dict[str, Any]],
    *,
    cached: bool = False,
) -> str:
    diagnostics = tuple(
        item for item in diagnostics if isinstance(item, dict)
    )
    if cached:
        return "LLM 사용량: 캐시 재사용 · API 호출 0회 · 토큰 0"
    summary = summarize_usage(diagnostics)
    calls = int(summary["calls"])
    if calls == 0:
        return ""
    models = tuple(dict.fromkeys(
        str(item.get("model"))
        for item in diagnostics
        if item.get("model")
    ))
    model_text = f" · {models[0]}" if len(models) == 1 else ""
    retry_reasons = tuple(dict.fromkeys(
        str(item.get("retry_reason"))
        for item in diagnostics
        if item.get("retry_reason")
    ))
    retry_text = ""
    if retry_reasons:
        retry_text = (
            "\nLLM 재호출: 응답 검증 보완 "
            f"{len(retry_reasons)}회 · 원인 {', '.join(retry_reasons)}"
        )
    if int(summary["usage_reported_calls"]) == calls:
        return (
            "LLM 사용량: "
            f"입력 {summary['prompt_tokens']:,} · "
            f"출력 {summary['completion_tokens']:,} · "
            f"합계 {summary['total_tokens']:,} tokens · "
            f"API {calls}회 · 요청 {summary['request_bytes'] / 1024:.1f} KB · "
            f"{summary['duration_ms'] / 1000:.1f}초"
            + model_text
            + retry_text
        )
    return (
        "LLM 사용량: Groq usage 미제공 · "
        f"API {calls}회 · 요청 {summary['request_bytes'] / 1024:.1f} KB · "
        f"{summary['duration_ms'] / 1000:.1f}초"
        + model_text
        + retry_text
    )
