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
    temperature: float = 0.2
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
                   base_url=os.getenv("LLM_BASE_URL") or GROQ_BASE_URL)

    def api_key(self) -> str | None:
        return os.getenv(self.api_key_env) or None
