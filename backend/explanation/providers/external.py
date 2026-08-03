from __future__ import annotations

import json
import socket
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Callable

from .config import ProviderSettings

Transport = Callable[[str, dict[str, str], bytes, float], bytes]
_SAFE_ERROR_HEADERS = (
    "retry-after",
    "x-ratelimit-limit-requests",
    "x-ratelimit-limit-tokens",
    "x-ratelimit-remaining-requests",
    "x-ratelimit-remaining-tokens",
    "x-ratelimit-reset-requests",
    "x-ratelimit-reset-tokens",
    "x-request-id",
)


class ProviderHTTPError(RuntimeError):
    """HTTP failure with the safe diagnostic data returned by the provider."""

    def __init__(
        self,
        status: int,
        *,
        message: str,
        error_type: str | None,
        provider_code: str | None,
        request_bytes: int,
        model: str,
        headers: dict[str, str] | None = None,
        attempts: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(f"provider_http_{status}")
        self.status = status
        self.provider_message = message[:1200]
        self.error_type = error_type
        self.provider_code = provider_code
        self.request_bytes = request_bytes
        self.model = model
        self.safe_headers = dict(headers or {})
        self.attempts = list(attempts or [])

    def diagnostic(self) -> dict[str, Any]:
        result = {
            "category": "provider_http",
            "http_status": self.status,
            "message": self.provider_message,
            "error_type": self.error_type,
            "provider_code": self.provider_code,
            "request_bytes": self.request_bytes,
            "model": self.model,
            "headers": self.safe_headers,
        }
        if self.attempts:
            result["attempts"] = self.attempts
        return result


def _http_error_detail(
    error: urllib.error.HTTPError,
    *,
    request_bytes: int,
    model: str,
) -> ProviderHTTPError:
    raw = b""
    try:
        raw = error.read(16_384)
    except (AttributeError, OSError):
        pass
    message = str(getattr(error, "reason", "") or f"HTTP {error.code}")
    error_type = provider_code = None
    if raw:
        try:
            body = json.loads(raw.decode("utf-8", errors="replace"))
            detail = body.get("error", body) if isinstance(body, dict) else {}
            if isinstance(detail, dict):
                message = str(detail.get("message") or message)
                error_type = (
                    str(detail["type"]) if detail.get("type") else None
                )
                provider_code = (
                    str(detail["code"]) if detail.get("code") else None
                )
        except (TypeError, ValueError, json.JSONDecodeError):
            decoded = raw.decode("utf-8", errors="replace").strip()
            if decoded:
                message = decoded
    response_headers = getattr(error, "headers", None)
    safe_headers = {}
    for name in _SAFE_ERROR_HEADERS:
        value = response_headers.get(name) if response_headers else None
        if value is not None:
            safe_headers[name] = str(value)[:300]
    return ProviderHTTPError(
        int(error.code),
        message=message,
        error_type=error_type,
        provider_code=provider_code,
        request_bytes=request_bytes,
        model=model,
        headers=safe_headers,
    )


def _urlopen_transport(url: str, headers: dict[str, str], body: bytes, timeout: float) -> bytes:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


class ExternalLLMProvider:
    name = "external_llm"

    def __init__(self, settings: ProviderSettings, transport: Transport | None = None) -> None:
        self.settings = settings; self.model = settings.model or "unspecified"
        self._api_key = settings.api_key(); self._transport = transport or _urlopen_transport
        self._call_state = threading.local()
        if not self._api_key: raise RuntimeError("provider_unavailable")
        if not settings.base_url or not settings.model: raise RuntimeError("provider_unavailable")

    def _set_last_call_diagnostic(self, value: dict[str, Any]) -> None:
        self._call_state.last_call_diagnostic = dict(value)

    def consume_last_call_diagnostic(self) -> dict[str, Any]:
        """Return metadata for this thread's most recent successful call once."""
        value = dict(
            getattr(self._call_state, "last_call_diagnostic", {}) or {}
        )
        self._call_state.last_call_diagnostic = {}
        return value

    def generate(self, system_prompt: str, user_prompt: str, payload: dict) -> dict:
        del payload
        self._set_last_call_diagnostic({})
        started = time.monotonic()
        request = {"model": self.model, "temperature": self.settings.temperature,
                   "response_format": {"type": "json_object"},
                   "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]}
        endpoint = self.settings.base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Cloudflare may reject urllib's default browser signature with 1010.
            "User-Agent": "inverse-device-modeling/1.0",
        }
        last_error: Exception | None = None
        http_attempts: list[dict[str, Any]] = []
        request_body = json.dumps(
            request,
            ensure_ascii=False,
        ).encode("utf-8")
        for attempt in range(self.settings.max_retries + 1):
            try:
                raw = self._transport(
                    endpoint,
                    headers,
                    request_body,
                    self.settings.timeout_seconds,
                )
                envelope = json.loads(raw.decode("utf-8"))
                content = envelope["choices"][0]["message"]["content"]
                raw_usage = envelope.get("usage", {})
                usage = {}
                if isinstance(raw_usage, dict):
                    for name in (
                        "prompt_tokens",
                        "completion_tokens",
                        "total_tokens",
                    ):
                        value = raw_usage.get(name)
                        if isinstance(value, int) and not isinstance(value, bool):
                            usage[name] = value
                    for name in (
                        "queue_time",
                        "prompt_time",
                        "completion_time",
                        "total_time",
                    ):
                        value = raw_usage.get(name)
                        if isinstance(value, (int, float)) and not isinstance(
                            value, bool
                        ):
                            usage[name] = float(value)
                self._set_last_call_diagnostic({
                    "category": "provider_success",
                    "model": self.model,
                    "request_bytes": len(request_body),
                    "duration_ms": round(
                        (time.monotonic() - started) * 1000, 1
                    ),
                    "usage": usage,
                })
                return json.loads(content) if isinstance(content, str) else content
            except (TimeoutError, socket.timeout) as error:
                last_error = TimeoutError("provider_timeout")
            except urllib.error.HTTPError as error:
                detailed = _http_error_detail(
                    error,
                    request_bytes=len(request_body),
                    model=self.model,
                )
                attempt_detail = detailed.diagnostic()
                attempt_detail["attempt"] = attempt + 1
                http_attempts.append(attempt_detail)
                detailed.attempts = list(http_attempts)
                code = detailed.status
                # A 429 includes the provider's actual retry window. A fixed
                # sub-second retry only repeats the same failure and makes the
                # user-facing wait calculation stale, so return it immediately.
                if code == 429:
                    raise detailed from error
                if code not in {500, 502, 503, 504}:
                    raise detailed from error
                last_error = detailed
            except urllib.error.URLError as error:
                raise RuntimeError("provider_network_error") from error
            except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
                raise ValueError("invalid_provider_response") from error
            if attempt < self.settings.max_retries: time.sleep(min(.25 * (attempt + 1), .5))
        raise last_error or RuntimeError("provider_error")
