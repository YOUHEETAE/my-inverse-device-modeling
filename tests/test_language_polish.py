from __future__ import annotations

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
from backend.explanation.providers.mock import MockExplanationProvider
from backend.explanation.service import ExplanationService
from tests.test_final_audit import _channel_length_payload


def _draft_and_package():
    payload = _channel_length_payload().to_dict()
    mock = MockExplanationProvider()
    draft = mock.generate("", "", payload)
    return payload, draft, build_language_polish_package(payload, draft, mock_model=mock.model)


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
    assert draft["descriptions"][0] in user
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


def test_analyzer_guided_external_receives_mock_draft_only() -> None:
    result = ExplanationService(EchoPolisher())._explain(_channel_length_payload())
    assert result.provider == "external_llm"
    assert result.model == f"echo-polisher / {LANGUAGE_POLISH_VERSION}"
    assert all(len(getattr(result, key)) <= 1 for key in ("descriptions", "comparisons", "tradeoffs", "cautions"))
    assert "•" not in result.display_text()


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
