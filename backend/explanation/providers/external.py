from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from typing import Any, Callable

from .config import ProviderSettings

Transport = Callable[[str, dict[str, str], bytes, float], bytes]


def _urlopen_transport(url: str, headers: dict[str, str], body: bytes, timeout: float) -> bytes:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


class ExternalLLMProvider:
    name = "external_llm"

    def __init__(self, settings: ProviderSettings, transport: Transport | None = None) -> None:
        self.settings = settings; self.model = settings.model or "unspecified"
        self._api_key = settings.api_key(); self._transport = transport or _urlopen_transport
        if not self._api_key: raise RuntimeError("provider_unavailable")
        if not settings.base_url or not settings.model: raise RuntimeError("provider_unavailable")

    def generate(self, system_prompt: str, user_prompt: str, payload: dict) -> dict:
        del payload
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
        for attempt in range(self.settings.max_retries + 1):
            try:
                raw = self._transport(endpoint, headers, json.dumps(request, ensure_ascii=False).encode("utf-8"), self.settings.timeout_seconds)
                envelope = json.loads(raw.decode("utf-8")); content = envelope["choices"][0]["message"]["content"]
                return json.loads(content) if isinstance(content, str) else content
            except (TimeoutError, socket.timeout) as error:
                last_error = TimeoutError("provider_timeout")
            except urllib.error.HTTPError as error:
                code = int(error.code)
                if code not in {429, 500, 502, 503, 504}:
                    raise RuntimeError(f"provider_http_{code}") from error
                last_error = RuntimeError(f"provider_http_{code}")
            except urllib.error.URLError as error:
                raise RuntimeError("provider_network_error") from error
            except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
                raise ValueError("invalid_provider_response") from error
            if attempt < self.settings.max_retries: time.sleep(min(.25 * (attempt + 1), .5))
        raise last_error or RuntimeError("provider_error")
