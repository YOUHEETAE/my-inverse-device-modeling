from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum


class ProviderMode(str, Enum):
    MOCK = "mock"
    EXTERNAL = "external_llm"
    AUTO = "auto"


GROQ_API_KEY_ENV = "GROQ_API_KEY"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_DEFAULT_MODEL = "openai/gpt-oss-120b"


@dataclass(frozen=True)
class ProviderSettings:
    provider: ProviderMode = ProviderMode.MOCK
    model: str | None = None
    api_key_env: str = "LLM_API_KEY"
    base_url: str | None = None
    timeout_seconds: float = 30.0
    max_retries: int = 1
    # None이면 요청에서 temperature를 아예 뺀다. 기본값 외의 값을 거부하는
    # 모델이 있어서 필요하다 — 자세한 이유는 external.py의 generate 참고.
    temperature: float | None = 0.2
    allow_mock_fallback: bool = True
    allow_safe_fallback: bool = True
    cache_enabled: bool = True

    @classmethod
    def from_environment(cls, provider: str | ProviderMode = ProviderMode.MOCK) -> "ProviderSettings":
        mode = ProviderMode(provider)
        if mode is ProviderMode.MOCK:
            return cls(provider=mode)
        return cls(provider=mode,
                   model=os.getenv("LLM_MODEL") or GROQ_DEFAULT_MODEL,
                   api_key_env=os.getenv("LLM_API_KEY_ENV") or GROQ_API_KEY_ENV,
                   base_url=os.getenv("LLM_BASE_URL") or GROQ_BASE_URL,
                   temperature=_temperature_from_environment())

    def api_key(self) -> str | None:
        return os.getenv(self.api_key_env) or None


def _temperature_from_environment() -> float | None:
    """LLM_TEMPERATURE를 읽는다. 비워두면 파라미터를 보내지 않는다.

    설명의 일관성을 위해 낮은 값을 쓰는 것이 기본이지만, 기본값(1) 외의
    temperature를 거부하는 모델이 있다. 그런 모델에서는 값을 고르는 대신
    파라미터 자체를 빼야 한다.
    """
    raw = os.getenv("LLM_TEMPERATURE")
    if raw is None:
        return 0.2
    raw = raw.strip()
    if not raw or raw.lower() in {"default", "none"}:
        return None
    return float(raw)
