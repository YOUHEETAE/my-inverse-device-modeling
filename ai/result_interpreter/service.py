from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai.curve_model.inference import CurvePrediction
    from ai.visualization.field_data import GeneratedFieldMap

from .cache import JsonExplanationCache
from .staged_explanation import STAGED_PROMPT_VERSION, build_staged_payload, build_staged_prompt
from .prompts import LLM_PROMPT_VERSION, RESPONSE_SCHEMA_VERSION, build_prompt
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

    def explain_curves_staged(self, results: list[tuple[str, "CurvePrediction", "CurvePrediction"]], configs: list[dict[str, str]], stage: str) -> ExplanationResult:
        from .curve_analyzer import build_curve_payload
        return self._explain_staged(build_staged_payload(build_curve_payload(results, configs).to_dict(), stage), stage)

    def explain_fields_staged(self, outputs: list[tuple[str, "GeneratedFieldMap"]], display: str, scale_mode: str, range_mode: str, stage: str) -> ExplanationResult:
        from .field_analyzer import build_field_payload
        return self._explain_staged(build_staged_payload(build_field_payload(outputs, display, scale_mode, range_mode).to_dict(), stage), stage)

    @staticmethod
    def _prompt_text(system_prompt: str, user_prompt: str) -> str:
        return "=== SYSTEM PROMPT ===\n" + system_prompt + "\n\n=== USER PROMPT ===\n" + user_prompt

    def build_curves_prompt(self, results: list[tuple[str, "CurvePrediction", "CurvePrediction"]], configs: list[dict[str, str]], mode: str) -> str:
        from .curve_analyzer import build_curve_payload
        payload = build_curve_payload(results, configs).to_dict()
        stages = {"Extracted-only": "extracted_only", "Evidence-assisted": "evidence_assisted"}
        if mode in stages:
            prompts = build_staged_prompt(build_staged_payload(payload, stages[mode]))
        else:
            prompts = build_prompt(payload)
        return self._prompt_text(*prompts)

    def build_fields_prompt(self, outputs: list[tuple[str, "GeneratedFieldMap"]], display: str, scale_mode: str, range_mode: str, mode: str) -> str:
        from .field_analyzer import build_field_payload
        payload = build_field_payload(outputs, display, scale_mode, range_mode).to_dict()
        stages = {"Extracted-only": "extracted_only", "Evidence-assisted": "evidence_assisted"}
        if mode in stages:
            prompts = build_staged_prompt(build_staged_payload(payload, stages[mode]))
        else:
            prompts = build_prompt(payload)
        return self._prompt_text(*prompts)

    def _explain_staged(self, data: dict, stage: str) -> ExplanationResult:
        if self.provider.name != "external_llm":
            response = {"descriptions": ["단계 비교 모드는 외부 LLM provider가 필요합니다."], "comparisons": [], "tradeoffs": [],
                        "cautions": ["Explanation Provider를 external_llm으로 선택해 주세요."]}
            return ExplanationResult.from_dict(response, provider="safe-fallback", model=f"{STAGED_PROMPT_VERSION}/{stage}")
        version = f"{STAGED_PROMPT_VERSION}/{stage}"
        key = self.cache.key(data, self.provider.name, self.provider.model, prompt_version=version, response_schema_version=RESPONSE_SCHEMA_VERSION)
        cached = self.cache.get(key)
        if cached is not None:
            try:
                return ExplanationResult.from_dict(cached, provider=self.provider.name, model=f"{self.provider.model} / {version}", cached=True)
            except (TypeError, ValueError):
                pass
        system_prompt, user_prompt = build_staged_prompt(data)
        try:
            response = self._generate_schema_validated(system_prompt, user_prompt, data)
            caution = f"이 설명은 Python pipeline의 {stage} 단계까지만 사용하고 이후 판단을 LLM이 수행한 비교용 결과입니다."
            response["cautions"] = list(dict.fromkeys([*response["cautions"], caution]))[:2]
        except Exception:
            response = {"descriptions": ["단계별 LLM 해석을 생성하지 못했습니다."], "comparisons": [], "tradeoffs": [],
                        "cautions": ["외부 provider 응답과 추출 결과를 확인해 주세요."]}
            return ExplanationResult.from_dict(response, provider="safe-fallback", model=version)
        self.cache.put(key, response)
        return ExplanationResult.from_dict(response, provider=self.provider.name, model=f"{self.provider.model} / {version}")

    def _explain(self, payload: AnalysisPayload) -> ExplanationResult:
        data, _numeric_warnings = sanitize_payload_for_json(payload.to_dict())
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

    def _generate_schema_validated(self, system_prompt: str, user_prompt: str, data: dict) -> dict[str, list[str]]:
        try:
            return validate_provider_response(self.provider.generate(system_prompt, user_prompt, data))
        except ValueError as first_error:
            if self.provider.name != "external_llm":
                raise
            repair_prompt = system_prompt + (
                "\n\nThe previous output failed JSON validation with code: " + str(first_error) + ". "
                "Regenerate once as one JSON object with exactly descriptions, comparisons, tradeoffs, cautions. "
                "Every value must be an array of Korean strings; use an empty array when a section is not applicable."
            )
            return validate_provider_response(self.provider.generate(repair_prompt, user_prompt, data))

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
