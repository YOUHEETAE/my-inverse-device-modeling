from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai.curve_model.inference import CurvePrediction
    from ai.shared.field_data import GeneratedFieldMap

from .cache import JsonExplanationCache
from .prompts import LLM_PROMPT_VERSION, RESPONSE_SCHEMA_VERSION, build_prompt
from .language_polish import (LANGUAGE_POLISH_VERSION, build_language_polish_package,
                              build_language_polish_prompt, build_interactive_analysis_prompt,
                              validate_language_polish_response,
                              validate_mock_draft_coverage)
from .providers.base import ExplanationProvider
from .providers.mock import MockExplanationProvider
from .safety import (build_safe_fallback_response, enforce_response_policy,
                     salvage_grounded_response, sanitize_payload_for_json,
                     validate_grounded_response, validate_provider_response)
from .schemas import AnalysisPayload, ExplanationResult
from .warnings import make_warning


class ExplanationService:
    def __init__(self, provider: ExplanationProvider, cache: JsonExplanationCache | None = None, fallback_provider: ExplanationProvider | None = None) -> None:
        self.provider = provider
        self.cache = cache or JsonExplanationCache()
        self.fallback_provider = fallback_provider or MockExplanationProvider()

    def explain_curves(self, results: list[tuple[str, "CurvePrediction", "CurvePrediction"]], configs: list[dict[str, str]]) -> ExplanationResult:
        from .curve_analyzer import build_curve_payload
        return self._explain(build_curve_payload(results, configs))

    def explain_fields(self, outputs: list[tuple[str, "GeneratedFieldMap"]], display: str, scale_mode: str, range_mode: str) -> ExplanationResult:
        from .field_analyzer import build_field_payload
        return self._explain(build_field_payload(outputs, display, scale_mode, range_mode))

    @staticmethod
    def _prompt_text(system_prompt: str, user_prompt: str) -> str:
        return "=== SYSTEM PROMPT ===\n" + system_prompt + "\n\n=== USER PROMPT ===\n" + user_prompt

    def build_curves_prompt(self, results: list[tuple[str, "CurvePrediction", "CurvePrediction"]], configs: list[dict[str, str]], mode: str = "") -> str:
        from .curve_analyzer import build_curve_payload
        del mode  # Retained for compatibility with older callers.
        return self._build_interactive_prompt(build_curve_payload(results, configs).to_dict())

    def build_fields_prompt(self, outputs: list[tuple[str, "GeneratedFieldMap"]], display: str, scale_mode: str, range_mode: str, mode: str = "") -> str:
        from .field_analyzer import build_field_payload
        del mode  # Retained for compatibility with older callers.
        return self._build_interactive_prompt(build_field_payload(outputs, display, scale_mode, range_mode).to_dict())

    def _build_interactive_prompt(self, data: dict) -> str:
        clean, _warnings = sanitize_payload_for_json(data)
        mock_draft = validate_provider_response(self.fallback_provider.generate("", "", clean))
        validate_mock_draft_coverage(clean, mock_draft)
        return build_interactive_analysis_prompt(clean, mock_draft)

    def _build_mock_polish_prompt(self, data: dict) -> tuple[str, str]:
        mock_draft = validate_provider_response(self.fallback_provider.generate("", "", data))
        validate_mock_draft_coverage(data, mock_draft)
        package = build_language_polish_package(data, mock_draft, mock_model=self.fallback_provider.model)
        return build_language_polish_prompt(package)

    def _explain(self, payload: AnalysisPayload) -> ExplanationResult:
        data, _numeric_warnings = sanitize_payload_for_json(payload.to_dict())
        if self.provider.name == "external_llm" and (data.get("interpretation") or {}).get("status") in {"insufficient", "partial", "complete"}:
            return self._explain_via_mock_polish(data)
        settings = getattr(self.provider, "settings", None)
        cache_enabled = bool(getattr(settings, "cache_enabled", True))
        key = self.cache.key(data, self.provider.name, self.provider.model, prompt_version=LLM_PROMPT_VERSION, response_schema_version=RESPONSE_SCHEMA_VERSION)
        cached = self.cache.get(key) if cache_enabled else None
        if cached is not None:
            try:
                return ExplanationResult.from_dict(cached, provider=self.provider.name, model=self.provider.model, cached=True)
            except (TypeError, ValueError):
                pass
        system_prompt, user_prompt = build_prompt(data)
        provider_warning = None
        primary_succeeded = False
        try:
            response = self._generate_validated(system_prompt, user_prompt, data)
            response = enforce_response_policy(response, data.get("output_policy", {}))
            provider, model = self.provider.name, self.provider.model
            primary_succeeded = True
        except TimeoutError:
            provider_warning = make_warning("warn_provider_timeout", "provider_timeout", severity="high", fallback_action="return_partial_explanation")
            response, provider, model = self._fallback(data, provider_warning)
        except (Exception,) as error:
            warning_type = "invalid_provider_response" if isinstance(error, (TypeError, ValueError)) else "provider_error"
            provider_warning = make_warning(f"warn_{warning_type}", warning_type, severity="high", fallback_action="return_partial_explanation")
            response, provider, model = self._fallback(data, provider_warning)
        result = ExplanationResult.from_dict(response, provider=provider, model=model)
        # A fallback must not be stored under the external provider's cache key;
        # otherwise Mock text is later reported as an external LLM response.
        if cache_enabled and primary_succeeded:
            self.cache.put(key, {name: list(getattr(result, name)) for name in ("descriptions", "comparisons", "tradeoffs", "cautions")})
        return result

    def _explain_via_mock_polish(self, data: dict) -> ExplanationResult:
        """Use Python/Mock as analysis authority and the external model only as a language editor."""
        mock_draft = validate_provider_response(self.fallback_provider.generate("", "", data))
        validate_mock_draft_coverage(data, mock_draft)
        package = build_language_polish_package(data, mock_draft, mock_model=self.fallback_provider.model)
        settings = getattr(self.provider, "settings", None)
        cache_enabled = bool(getattr(settings, "cache_enabled", True))
        key = self.cache.key(package, self.provider.name, self.provider.model, prompt_version=LANGUAGE_POLISH_VERSION,
                             response_schema_version=RESPONSE_SCHEMA_VERSION, renderer_version=self.fallback_provider.model)
        cached = self.cache.get(key) if cache_enabled else None
        if cached is not None:
            try:
                clean = validate_language_polish_response(cached, package)
                return ExplanationResult.from_dict(clean, provider=self.provider.name, model=f"{self.provider.model} / {LANGUAGE_POLISH_VERSION}", cached=True)
            except (TypeError, ValueError):
                pass
        system_prompt, user_prompt = build_language_polish_prompt(package)
        try:
            response = self._generate_polish_validated(system_prompt, user_prompt, package)
        except Exception:
            return ExplanationResult.from_dict(mock_draft, provider=self.fallback_provider.name, model=self.fallback_provider.model)
        if cache_enabled:
            self.cache.put(key, response)
        return ExplanationResult.from_dict(response, provider=self.provider.name, model=f"{self.provider.model} / {LANGUAGE_POLISH_VERSION}")

    def _generate_polish_validated(self, system_prompt: str, user_prompt: str, package: dict) -> dict[str, list[str]]:
        try:
            return validate_language_polish_response(self.provider.generate(system_prompt, user_prompt, package), package)
        except ValueError as first_error:
            repair_prompt = system_prompt + (
                "\n\n이전 응답이 의미 보존 검증에 실패했습니다. 검증 코드: " + str(first_error) + ". "
                "content_blocks의 네 섹션, 모든 수치·단위·핵심 용어·방향·주의사항을 그대로 유지하고 "
                "각 섹션을 목록 없는 문단 하나로 다시 교정하세요."
            )
            return validate_language_polish_response(self.provider.generate(repair_prompt, user_prompt, package), package)

    def _generate_validated(self, system_prompt: str, user_prompt: str, data: dict) -> dict[str, list[str]]:
        """Generate once, then allow one semantic-format repair before fallback."""
        try:
            response = validate_provider_response(self.provider.generate(system_prompt, user_prompt, data))
            if self.provider.name == "external_llm":
                validate_grounded_response(response, data)
            return response
        except ValueError as first_error:
            if self.provider.name != "external_llm":
                raise
            reason = str(first_error)
            repair_prompt = system_prompt + (
                "\n\nYour previous response was rejected by the local validator. "
                f"Validation code: {reason}. Regenerate the entire JSON response once. "
                "Keep exactly the four required array keys. Use Korean. Do not invent or calculate numbers; "
                "if a number may be unsupported, omit it and state only the qualitative direction. "
                "Do not add a trade-off or causal claim unless the supplied Conclusion permits it."
            )
            repaired = validate_provider_response(self.provider.generate(repair_prompt, user_prompt, data))
            try:
                validate_grounded_response(repaired, data)
                return repaired
            except ValueError:
                return salvage_grounded_response(repaired, data)

    def _fallback(self, data: dict, warning: dict) -> tuple[dict, str, str]:
        warnings = [*data.get("warnings", []), warning]
        settings = getattr(self.provider, "settings", None)
        if bool(getattr(settings, "allow_mock_fallback", True)):
            try:
                response = validate_provider_response(self.fallback_provider.generate("", "", data))
                response["cautions"] = list(dict.fromkeys([*response["cautions"], *build_safe_fallback_response(data.get("analysis_type", "unsupported"), warnings, data.get("output_policy"))["cautions"]]))
                response["cautions"] = response["cautions"][:int(data.get("output_policy", {}).get("max_cautions", 1))]
                return response, self.fallback_provider.name, self.fallback_provider.model
            except Exception:
                pass
        if bool(getattr(settings, "allow_safe_fallback", True)):
            return build_safe_fallback_response(data.get("analysis_type", "unsupported"), warnings, data.get("output_policy")), "safe-fallback", "local-v1"
        raise RuntimeError("explanation_provider_failed")
