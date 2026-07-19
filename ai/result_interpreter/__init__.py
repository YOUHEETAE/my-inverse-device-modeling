from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .providers.mock import MockExplanationProvider
    from .service import ExplanationService

__all__ = ["ExplanationService", "MockExplanationProvider", "ProviderSettings", "ProviderMode", "create_explanation_provider"]


def __getattr__(name: str) -> Any:
    """Avoid loading ML runtime dependencies when only payload schemas are used."""
    if name == "ExplanationService":
        from .service import ExplanationService
        return ExplanationService
    if name == "MockExplanationProvider":
        from .providers.mock import MockExplanationProvider
        return MockExplanationProvider
    if name in {"ProviderSettings", "ProviderMode", "create_explanation_provider"}:
        from .providers import ProviderMode, ProviderSettings, create_explanation_provider
        return {"ProviderSettings": ProviderSettings, "ProviderMode": ProviderMode, "create_explanation_provider": create_explanation_provider}[name]
    raise AttributeError(name)
