from __future__ import annotations

import re

from backend.explanation.language_polish import (
    LANGUAGE_POLISH_VERSION,
    _number_tokens,
    build_interactive_analysis_brief,
    build_interactive_analysis_prompt,
    build_language_polish_package,
    build_language_polish_prompt,
    validate_language_polish_response,
    validate_mock_draft_coverage,
)
from backend.explanation.providers.config import ProviderSettings
from backend.explanation.providers.external import ProviderHTTPError
from backend.explanation.providers.mock import MockExplanationProvider
from backend.explanation.errors import ExplanationPipelineError
from backend.explanation.service import ExplanationService
from backend.answer_contract import find_internal_references, normalize_public_text
from tests.test_final_audit import _channel_length_payload
from tests.test_curve_interpretation import curve, payload_many


def _draft_and_package():
    payload = _channel_length_payload().to_dict()
    mock = MockExplanationProvider()
    draft = mock.generate("", "", payload)
    return payload, draft, build_language_polish_package(payload, draft, mock_model=mock.model)


def test_public_text_converts_double_escaped_model_line_breaks() -> None:
    assert normalize_public_text(
        "첫 문장입니다.\\n- 첫 항목\\n- 둘째 항목"
    ) == "첫 문장입니다.\n- 첫 항목\n- 둘째 항목"
    assert normalize_public_text("4.2e16 cm⁻³에서 증가") == (
        "4.2e16 cm^-3에서 증가"
    )


def test_mock_draft_is_complete_before_language_polish() -> None:
    payload, draft, package = _draft_and_package()
    validate_mock_draft_coverage(payload, draft)
    assert draft["descriptions"] and draft["comparisons"] and draft["tradeoffs"] and draft["cautions"]
    assert package["task"] == "language_polish_only"
    assert package["analysis_authority"] == "python_payload_and_deterministic_mock"
    assert set(package["content_blocks"]) == {"descriptions", "comparisons", "tradeoffs", "cautions"}


def test_polish_prompt_contains_draft_but_not_full_analysis_payload() -> None:
    _payload, draft, package = _draft_and_package()
    system, user = build_language_polish_prompt(package)
    assert "문장 교정기" in system and "새로 수행하지 마세요" in system
    assert "<LANGUAGE_POLISH_PACKAGE>" in user
    assert "Channel length" in user and "__NUM_" in user
    assert "100 nm에서 120 nm" not in user
    assert "_local_number_restore" not in user
    assert "preservation_manifest" not in user
    assert "performance_summaries" not in user and "spatial_features" not in user
    assert "관찰 결과와 종합 판정 사이의 관계" in system
    assert "같은 주어" not in system


def test_polish_validator_preserves_structure_numbers_and_terms() -> None:
    _payload, draft, package = _draft_and_package()
    paragraphs = {key: ([" ".join(value)] if value else []) for key, value in draft.items()}
    assert validate_language_polish_response(paragraphs, package) == paragraphs
    changed_number = {key: list(value) for key, value in paragraphs.items()}
    changed_number["descriptions"][0] = changed_number["descriptions"][0].replace("100", "101", 1)
    try: validate_language_polish_response(changed_number, package)
    except ValueError as error: assert str(error) == "language_polish_changed_numbers"
    else: raise AssertionError("changed number accepted")


def test_polish_validator_ignores_subject_ordinals_and_numeric_notation_style() -> None:
    _payload, draft, package = _draft_and_package()
    coalesced = validate_language_polish_response(draft, package)
    assert all(len(coalesced[key]) <= 1 for key in coalesced)

    comparison = coalesced["comparisons"][0]
    if comparison.count("Curve 2") > 1:
        first, *rest = comparison.split("Curve 2")
        coalesced["comparisons"][0] = first + "Curve 2" + "".join("해당 조건" + item for item in rest)
    assert validate_language_polish_response(coalesced, package) == coalesced
    assert _number_tokens("Curve 2: 1.00e+16 cm^-3") == _number_tokens("해당 조건: 10000000000000000 cm⁻³")


class EchoPolisher:
    name = "external_llm"
    model = "echo-polisher"
    settings = ProviderSettings(cache_enabled=False)

    def generate(self, _system, _user, package):
        assert package["task"] == "language_polish_only"
        assert "content_blocks" in package and "mock_draft" not in package and "interpretation" not in package
        return {
            key: ([" ".join(block["source_sentences"])] if block["source_sentences"] else [])
            for key, block in package["content_blocks"].items()
        }


class UsageEchoPolisher(EchoPolisher):
    model = "usage-polisher"

    def __init__(self):
        self._diagnostic = {}

    def generate(self, system, user, package):
        result = super().generate(system, user, package)
        self._diagnostic = {
            "category": "provider_success",
            "model": self.model,
            "request_bytes": 4_800,
            "duration_ms": 420.0,
            "usage": {
                "prompt_tokens": 900,
                "completion_tokens": 220,
                "total_tokens": 1120,
            },
        }
        return result

    def consume_last_call_diagnostic(self):
        value = self._diagnostic
        self._diagnostic = {}
        return value


def test_analyzer_guided_external_receives_mock_draft_only() -> None:
    result = ExplanationService(EchoPolisher())._explain(_channel_length_payload())
    assert result.provider == "external_llm"
    assert result.model == f"echo-polisher / {LANGUAGE_POLISH_VERSION}"
    assert all(len(getattr(result, key)) <= 1 for key in ("descriptions", "comparisons", "tradeoffs", "cautions"))
    assert "•" not in result.display_text()
    assert result.answer_contract is not None
    assert result.answer_contract.analysis_type == "iv_curve_comparison"
    assert result.answer_contract.summary == result.descriptions
    assert result.answer_contract.interpretations == result.comparisons
    assert result.answer_contract.observations == ()
    assert not find_internal_references(result.display_text())


def _compound_only_mixed_payload(*, vary_contacts: bool = False):
    baseline = curve(
        "Curve 1", length=500, tox=20, bulk=1e16,
        sd=1e20, ldd=7e17 if vary_contacts else 1e18,
        ion=10, ioff=.01, ratio=1000, dibl=.2, ss=80,
        gm=4, ron=2,
    )
    second = curve(
        "Curve 2", length=400, tox=23, bulk=5e15,
        sd=1e20, ldd=1e18,
        ion=14, ioff=.1, ratio=140, dibl=.3, ss=90,
        gm=5, ron=1.5,
    )
    third = curve(
        "Curve 3", length=700, tox=12, bulk=5e16,
        sd=5e19 if vary_contacts else 1e20,
        ldd=2e18 if vary_contacts else 1e18,
        ion=7, ioff=.001, ratio=7000, dibl=.1, ss=70,
        gm=2, ron=3,
    )
    return payload_many([baseline, second, third])


def test_compound_only_mixed_group_reaches_external_polisher() -> None:
    for vary_contacts in (False, True):
        payload = _compound_only_mixed_payload(
            vary_contacts=vary_contacts,
        )
        assert payload.comparison_plan["analysis_mode"] == "mixed_group"
        assert not payload.comparison_plan["controlled_pair_ids"]
        assert payload.interpretation["observed_tradeoffs"]

        draft = MockExplanationProvider().generate(
            "", "", payload.to_dict(),
        )
        validate_mock_draft_coverage(payload.to_dict(), draft)
        assert draft["tradeoffs"]
        assert "특정 parameter의 영향으로 귀속하지 않습니다" in (
            " ".join(draft["tradeoffs"])
        )

        result = ExplanationService(EchoPolisher())._explain(payload)
        assert result.provider == "external_llm"
        assert result.tradeoffs
        assert "controlled pair가 없습니다" in result.descriptions[0]
        assert "controlled pair를 우선 분석" not in result.descriptions[0]


def test_automatic_explanation_keeps_provider_usage_internal() -> None:
    result = ExplanationService(UsageEchoPolisher())._explain(
        _channel_length_payload()
    )
    assert result.usage_diagnostics[0]["stage"] == (
        "automatic_language_polish"
    )
    text = result.display_text()
    assert "입력 900" not in text
    assert "출력 220" not in text
    assert "tokens" not in text
    assert "API 1회" not in text


def test_public_explanation_rejects_internal_evidence_references() -> None:
    _payload, _draft, package = _draft_and_package()
    leaked = {
        key: ([" ".join(block["source_sentences"])] if block["source_sentences"] else [])
        for key, block in package["content_blocks"].items()
    }
    leaked["descriptions"][0] += " evidence_id: ev_cmp_1_2_dibl"
    try:
        validate_language_polish_response(leaked, package)
    except ValueError as error:
        assert str(error) == "internal_evidence_reference_exposed"
    else:
        raise AssertionError("internal evidence reference accepted")


def test_provider_typography_is_normalized_for_tk_rendering() -> None:
    text = normalize_public_text(
        "Drain\u2011side\u202ffield \u25a0 증가, 5e16 cm⁻³"
    )
    assert text == "Drain-side field - 증가, 5e16 cm^-3"
    assert "\u2011" not in text and "\u202f" not in text


def test_polish_accepts_korean_equivalent_protected_terms() -> None:
    draft = {
        "descriptions": [
            "Channel length 감소는 Electric field를 강화할 수 있습니다."
        ],
        "comparisons": [],
        "tradeoffs": [],
        "cautions": [],
    }
    package = build_language_polish_package(
        {"analysis_id": "alias", "analysis_type": "field_comparison"},
        draft,
        mock_model="test",
    )
    response = {
        "descriptions": [
            "채널 길이가 감소하면 전계가 강화될 수 있습니다."
        ],
        "comparisons": [],
        "tradeoffs": [],
        "cautions": [],
    }
    assert validate_language_polish_response(response, package) == response


def test_interactive_prompt_contains_curated_next_stage_brief() -> None:
    payload, draft, _package = _draft_and_package()
    brief = build_interactive_analysis_brief(payload, draft)
    prompt = build_interactive_analysis_prompt(payload, draft)
    for text in ("[ANALYSIS_BRIEF]", '"devices"', '"extracted_values"', '"key_findings"',
                 '"integrated_interpretation"', '"warnings"', '"mock_baseline"'):
        assert text in prompt
    assert "후속 질문" in prompt and "추출값" in prompt
    assert "[전체 분석 Payload]" not in prompt and '"analysis_id"' not in prompt
    assert "output_policy" not in brief and "importance_score" not in prompt


class MeaningChangingPolisher(EchoPolisher):
    model = "bad-polisher"

    def __init__(self): self.calls = 0

    def generate(self, _system, _user, package):
        self.calls += 1
        changed = {
            key: list(block["source_sentences"])
            for key, block in package["content_blocks"].items()
        }
        changed["comparisons"] = []
        return changed


def test_meaning_change_retries_once_then_returns_exact_mock() -> None:
    provider = MeaningChangingPolisher()
    payload = _channel_length_payload()
    expected = MockExplanationProvider().generate("", "", payload.to_dict())
    result = ExplanationService(provider)._explain(payload)
    assert provider.calls == 2
    assert result.provider == "mock" and result.model == MockExplanationProvider.model
    for section in ("descriptions", "comparisons", "tradeoffs", "cautions"):
        assert list(getattr(result, section)) == expected[section]


class StrictMeaningChangingPolisher(MeaningChangingPolisher):
    settings = ProviderSettings(
        cache_enabled=False,
        allow_mock_fallback=False,
        allow_safe_fallback=False,
    )

    def __init__(self):
        super().__init__()
        self._diagnostic = {}

    def generate(self, system, user, package):
        result = super().generate(system, user, package)
        self._diagnostic = {
            "category": "provider_success",
            "model": self.model,
            "request_bytes": 2_000,
            "duration_ms": 100.0,
            "usage": {
                "prompt_tokens": 300,
                "completion_tokens": 100,
                "total_tokens": 400,
            },
        }
        return result

    def consume_last_call_diagnostic(self):
        value = self._diagnostic
        self._diagnostic = {}
        return value


class MissingTradeoffDraft:
    name = "mock"
    model = "missing-tradeoff"

    def generate(self, _system, _user, _payload):
        return {
            "descriptions": ["결과 설명"],
            "comparisons": ["비교 설명"],
            "tradeoffs": [],
            "cautions": ["주의사항"],
        }


class CountingEchoPolisher(EchoPolisher):
    def __init__(self):
        self.calls = 0

    def generate(self, system, user, package):
        self.calls += 1
        return super().generate(system, user, package)


class UnknownFailurePolisher(EchoPolisher):
    settings = ProviderSettings(
        cache_enabled=False,
        allow_mock_fallback=False,
        allow_safe_fallback=False,
    )

    def __init__(self):
        self.calls = 0

    def generate(self, _system, _user, _package):
        self.calls += 1
        raise ValueError("unexpected_polish_invariant")


class MissingNumberPlaceholderPolisher(EchoPolisher):
    settings = ProviderSettings(
        cache_enabled=False,
        allow_mock_fallback=False,
        allow_safe_fallback=False,
    )

    def __init__(self):
        self.calls = 0

    def generate(self, system, user, package):
        self.calls += 1
        result = super().generate(system, user, package)
        for section in ("descriptions", "comparisons", "tradeoffs", "cautions"):
            if result[section]:
                changed = re.sub(
                    r"__NUM_[A-Z]+__",
                    "",
                    result[section][0],
                    count=1,
                )
                if changed != result[section][0]:
                    result[section][0] = changed
                    break
        return result


class RateLimitedRepairPolisher(StrictMeaningChangingPolisher):
    def generate(self, system, user, package):
        if self.calls == 1:
            self.calls += 1
            self._diagnostic = {}
            raise ProviderHTTPError(
                429,
                message="Rate limit reached",
                error_type="tokens",
                provider_code="rate_limit_exceeded",
                request_bytes=3_000,
                model=self.model,
                headers={"retry-after": "2"},
            )
        return super().generate(system, user, package)


def test_local_draft_coverage_failure_is_not_reported_as_groq_failure() -> None:
    provider = CountingEchoPolisher()
    service = ExplanationService(
        provider,
        fallback_provider=MissingTradeoffDraft(),
    )
    try:
        service._explain(_channel_length_payload())
    except ExplanationPipelineError as error:
        assert error.stage == "deterministic_draft_validation"
        assert error.code == "mock_draft_missing_tradeoff"
        assert not error.retryable and error.is_local
        assert error.diagnostics == ()
    else:
        raise AssertionError("local draft failure was accepted")
    assert provider.calls == 0


def test_repairable_polish_failure_reports_two_calls_and_retry_reason() -> None:
    provider = StrictMeaningChangingPolisher()
    try:
        ExplanationService(provider)._explain(_channel_length_payload())
    except ExplanationPipelineError as error:
        assert error.stage == "llm_response_validation"
        assert error.retryable and not error.is_local
        assert error.first_validation_code == (
            "language_polish_changed_section_structure"
        )
        assert len(error.diagnostics) == 2
        assert error.diagnostics[1]["retry_reason"] == (
            "language_polish_changed_section_structure"
        )
    else:
        raise AssertionError("invalid repaired response was accepted")
    assert provider.calls == 2


def test_unknown_polish_failure_does_not_spend_a_repair_call() -> None:
    provider = UnknownFailurePolisher()
    try:
        ExplanationService(provider)._explain(_channel_length_payload())
    except ExplanationPipelineError as error:
        assert error.code == "unexpected_polish_invariant"
        assert error.diagnostics == ()
    else:
        raise AssertionError("unexpected failure was accepted")
    assert provider.calls == 1


def test_missing_numeric_placeholder_does_not_spend_repair_call() -> None:
    provider = MissingNumberPlaceholderPolisher()
    try:
        ExplanationService(provider)._explain(
            _compound_only_mixed_payload(vary_contacts=True)
        )
    except ExplanationPipelineError as error:
        assert error.stage == "llm_response_validation"
        assert error.code == (
            "language_polish_changed_number_placeholders"
        )
        assert error.retryable and not error.is_local
    else:
        raise AssertionError("missing numeric placeholder was accepted")
    assert provider.calls == 1


def test_failed_repair_keeps_first_call_and_retry_reason() -> None:
    provider = RateLimitedRepairPolisher()
    try:
        ExplanationService(provider)._explain(_channel_length_payload())
    except ProviderHTTPError as error:
        assert error.status == 429
        assert error.pipeline_stage == "automatic_language_polish_repair"
        assert error.retry_reason == (
            "language_polish_changed_section_structure"
        )
        assert len(error.pipeline_diagnostics) == 1
    else:
        raise AssertionError("rate-limited repair was accepted")
    assert provider.calls == 2
