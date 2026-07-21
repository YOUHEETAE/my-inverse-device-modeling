from __future__ import annotations

from .config import ProviderMode, ProviderSettings
from .external import ExternalLLMProvider, Transport
from .mock import MockExplanationProvider


def create_explanation_provider(settings: ProviderSettings, transport: Transport | None = None):
    if settings.provider is ProviderMode.MOCK: return MockExplanationProvider()
    try: return ExternalLLMProvider(settings, transport)
    except RuntimeError:
        if settings.provider is ProviderMode.AUTO and settings.allow_mock_fallback: return MockExplanationProvider()
        raise
