from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai.curve_model.inference import CurvePrediction
    from ai.shared.field_data import GeneratedFieldMap

from .cache import JsonExplanationCache
from .errors import ExplanationPipelineError
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
from .usage import consume_provider_diagnostic
from .warnings import make_warning


_REPAIRABLE_POLISH_VALIDATION_CODES = {
    "internal_evidence_reference_exposed",
    "invalid_provider_response",
    "language_polish_added_causal_claim",
    "language_polish_changed_section_structure",
    "language_polish_moved_number_between_sections",
    "language_polish_moved_term_between_sections",
    "language_polish_removed_protected_term",
}


def _error_code(error: Exception) -> str:
    return str(error) or type(error).__name__


class ExplanationService:
    def __init__(self, provider: ExplanationProvider, cache: JsonExplanationCache | None = None, fallback_provider: ExplanationProvider | None = None) -> None:
        self.provider = provider
        self.cache = cache or JsonExplanationCache()
        self.fallback_provider = fallback_provider or MockExplanationProvider()

    def explain_curves(self, results: list[tuple[str, "CurvePrediction", "CurvePrediction"]], configs: list[dict[str, str]]) -> ExplanationResult:
        from .curve_analyzer import build_curve_payload
        try:
            payload = build_curve_payload(results, configs)
        except Exception as error:
            raise ExplanationPipelineError(
                "python_analysis",
                _error_code(error),
                retryable=False,
            ) from error
        return self._explain(payload)

    def explain_fields(self, outputs: list[tuple[str, "GeneratedFieldMap"]], display: str, scale_mode: str, range_mode: str) -> ExplanationResult:
        from .field_analyzer import build_field_payload
        try:
            payload = build_field_payload(
                outputs,
                display,
                scale_mode,
                range_mode,
            )
        except Exception as error:
            raise ExplanationPipelineError(
                "python_analysis",
                _error_code(error),
                retryable=False,
            ) from error
        return self._explain(payload)

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
                return ExplanationResult.from_dict(
                    cached, provider=self.provider.name, model=self.provider.model,
                    cached=True, analysis_payload=data,
                )
            except (TypeError, ValueError):
                pass
        system_prompt, user_prompt = build_prompt(data)
        provider_warning = None
        primary_succeeded = False
        try:
            response, usage_diagnostics = self._generate_validated(
                system_prompt, user_prompt, data
            )
            response = enforce_response_policy(response, data.get("output_policy", {}))
            provider, model = self.provider.name, self.provider.model
            primary_succeeded = True
        except TimeoutError:
            if (
                not bool(getattr(settings, "allow_mock_fallback", True))
                and not bool(getattr(settings, "allow_safe_fallback", True))
            ):
                raise
            provider_warning = make_warning("warn_provider_timeout", "provider_timeout", severity="high", fallback_action="return_partial_explanation")
            response, provider, model = self._fallback(data, provider_warning)
        except (Exception,) as error:
            if (
                not bool(getattr(settings, "allow_mock_fallback", True))
                and not bool(getattr(settings, "allow_safe_fallback", True))
            ):
                raise
            warning_type = "invalid_provider_response" if isinstance(error, (TypeError, ValueError)) else "provider_error"
            provider_warning = make_warning(f"warn_{warning_type}", warning_type, severity="high", fallback_action="return_partial_explanation")
            response, provider, model = self._fallback(data, provider_warning)
        result = ExplanationResult.from_dict(
            response, provider=provider, model=model, analysis_payload=data,
            usage_diagnostics=(
                usage_diagnostics if primary_succeeded else ()
            ),
        )
        # A fallback must not be stored under the external provider's cache key;
        # otherwise Mock text is later reported as an external LLM response.
        if cache_enabled and primary_succeeded:
            self.cache.put(key, {name: list(getattr(result, name)) for name in ("descriptions", "comparisons", "tradeoffs", "cautions")})
        return result

    def _explain_via_mock_polish(self, data: dict) -> ExplanationResult:
        """Use Python/Mock as analysis authority and the external model only as a language editor."""
        try:
            mock_draft = validate_provider_response(
                self.fallback_provider.generate("", "", data)
            )
        except Exception as error:
            raise ExplanationPipelineError(
                "deterministic_draft",
                _error_code(error),
                retryable=False,
            ) from error
        try:
            validate_mock_draft_coverage(data, mock_draft)
        except Exception as error:
            raise ExplanationPipelineError(
                "deterministic_draft_validation",
                _error_code(error),
                retryable=False,
            ) from error
        try:
            package = build_language_polish_package(
                data,
                mock_draft,
                mock_model=self.fallback_provider.model,
            )
        except Exception as error:
            raise ExplanationPipelineError(
                "polish_package_build",
                _error_code(error),
                retryable=False,
            ) from error
        settings = getattr(self.provider, "settings", None)
        cache_enabled = bool(getattr(settings, "cache_enabled", True))
        key = self.cache.key(package, self.provider.name, self.provider.model, prompt_version=LANGUAGE_POLISH_VERSION,
                             response_schema_version=RESPONSE_SCHEMA_VERSION, renderer_version=self.fallback_provider.model)
        cached = self.cache.get(key) if cache_enabled else None
        if cached is not None:
            try:
                clean = validate_language_polish_response(cached, package)
                return ExplanationResult.from_dict(
                    clean, provider=self.provider.name,
                    model=f"{self.provider.model} / {LANGUAGE_POLISH_VERSION}",
                    cached=True, analysis_payload=data,
                )
            except (TypeError, ValueError):
                pass
        system_prompt, user_prompt = build_language_polish_prompt(package)
        try:
            response, usage_diagnostics = self._generate_polish_validated(
                system_prompt, user_prompt, package
            )
        except Exception:
            if not bool(getattr(settings, "allow_mock_fallback", True)):
                raise
            return ExplanationResult.from_dict(
                mock_draft, provider=self.fallback_provider.name,
                model=self.fallback_provider.model, analysis_payload=data,
            )
        if cache_enabled:
            self.cache.put(key, response)
        return ExplanationResult.from_dict(
            response, provider=self.provider.name,
            model=f"{self.provider.model} / {LANGUAGE_POLISH_VERSION}",
            analysis_payload=data,
            usage_diagnostics=usage_diagnostics,
        )

    def _generate_polish_validated(
        self,
        system_prompt: str,
        user_prompt: str,
        package: dict,
    ) -> tuple[dict[str, list[str]], tuple[dict, ...]]:
        diagnostics: list[dict] = []
        try:
            try:
                raw = self.provider.generate(
                    system_prompt, user_prompt, package
                )
            finally:
                diagnostic = consume_provider_diagnostic(
                    self.provider, stage="automatic_language_polish",
                )
                if diagnostic:
                    diagnostics.append(diagnostic)
            return (
                validate_language_polish_response(raw, package),
                tuple(diagnostics),
            )
        except ValueError as first_error:
            first_code = _error_code(first_error)
            if first_code not in _REPAIRABLE_POLISH_VALIDATION_CODES:
                raise ExplanationPipelineError(
                    "llm_response_validation",
                    first_code,
                    retryable=True,
                    diagnostics=diagnostics,
                ) from first_error
            repair_prompt = system_prompt + (
                "\n\n이전 응답이 의미 보존 검증에 실패했습니다. 검증 코드: " + first_code + ". "
                "content_blocks의 네 섹션, 모든 수치·단위·핵심 용어·방향·주의사항을 그대로 유지하고 "
                "각 섹션을 목록 없는 문단 하나로 다시 교정하세요."
            )
            try:
                try:
                    raw = self.provider.generate(
                        repair_prompt, user_prompt, package
                    )
                finally:
                    diagnostic = consume_provider_diagnostic(
                        self.provider,
                        stage="automatic_language_polish_repair",
                    )
                    if diagnostic:
                        diagnostic["retry_reason"] = first_code
                        diagnostics.append(diagnostic)
                return (
                    validate_language_polish_response(raw, package),
                    tuple(diagnostics),
                )
            except ValueError as second_error:
                raise ExplanationPipelineError(
                    "llm_response_validation",
                    _error_code(second_error),
                    retryable=True,
                    diagnostics=diagnostics,
                    first_validation_code=first_code,
                ) from second_error
            except Exception as provider_error:
                # Preserve the successful first call and the reason for the
                # repair call even when the repair itself fails at Groq.
                setattr(
                    provider_error,
                    "pipeline_diagnostics",
                    tuple(diagnostics),
                )
                setattr(
                    provider_error,
                    "pipeline_stage",
                    "automatic_language_polish_repair",
                )
                setattr(provider_error, "retry_reason", first_code)
                raise

    def _generate_validated(
        self,
        system_prompt: str,
        user_prompt: str,
        data: dict,
    ) -> tuple[dict[str, list[str]], tuple[dict, ...]]:
        """Generate once, then allow one semantic-format repair before fallback."""
        diagnostics: list[dict] = []
        try:
            try:
                raw = self.provider.generate(
                    system_prompt, user_prompt, data
                )
            finally:
                diagnostic = consume_provider_diagnostic(
                    self.provider, stage="automatic_explanation",
                )
                if diagnostic:
                    diagnostics.append(diagnostic)
            response = validate_provider_response(raw)
            if self.provider.name == "external_llm":
                validate_grounded_response(response, data)
            return response, tuple(diagnostics)
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
            try:
                raw = self.provider.generate(
                    repair_prompt, user_prompt, data
                )
            finally:
                diagnostic = consume_provider_diagnostic(
                    self.provider, stage="automatic_explanation_repair",
                )
                if diagnostic:
                    diagnostics.append(diagnostic)
            repaired = validate_provider_response(raw)
            try:
                validate_grounded_response(repaired, data)
                return repaired, tuple(diagnostics)
            except ValueError:
                return salvage_grounded_response(repaired, data), tuple(
                    diagnostics
                )

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
