from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from .safety import FORBIDDEN_CAUSAL_TERMS, RESPONSE_KEYS, validate_provider_response


LANGUAGE_POLISH_VERSION = "polish-v3"
PROTECTED_TERMS = (
    "Channel length", "Oxide thickness", "Tox", "Bulk doping", "Source/Drain doping", "LDD doping",
    "Ion", "Ioff", "Ion/Ioff", "SS", "DIBL", "gm", "gds", "Ron", "Vth", "Trade-off",
    "Potential", "Electric field", "Electron density", "Hole density", "current density", "SRH",
    "Gate", "Oxide", "Channel", "Source", "Drain", "LDD", "Deep bulk",
    "increased", "decreased", "strengthened", "weakened", "expanded", "contracted",
    "증가", "감소", "강화", "완화", "확대", "축소", "개선", "저하", "단정", "prediction", "TCAD",
)

POLISH_SYSTEM_PROMPT = """당신은 MOSFET 분석 초안의 한국어 문장 교정기입니다.
입력의 content_blocks가 분석 내용의 유일한 권위입니다. 분석, 계산, 선택 또는 물리 판단을 새로 수행하지 마세요.
각 block의 source_sentences를 개별 문장이 아니라 하나의 의미 단위로 이해하고, 섹션당 하나의 자연스러운 문단으로 다시 구성하세요.
수치, 단위, 증감 방향, 성능 판정, region, 원인 한계, Trade-off 및 주의사항을 추가·삭제·변경하지 마세요.
각 block 안의 관찰 결과와 종합 판정 사이의 관계가 자연스럽게 드러나도록 어순과 연결 표현을 구성하세요.
block 사이로 내용을 이동하거나 내용을 생략하지 마세요. 입력에 없는 mechanism이나 인과관계를 만들지 마세요.
목록 기호, 번호, 소제목 또는 문장별 머릿글을 넣지 마세요.
반드시 descriptions, comparisons, tradeoffs, cautions 네 key만 갖는 한국어 JSON object를 반환하고, 내용이 있는 각 배열에는 문단 문자열 하나만 넣으세요."""

BLOCK_PURPOSES = {
    "descriptions": "조건 변화와 일반적인 물리 방향을 하나의 배경 문단으로 설명",
    "comparisons": "관찰된 정량 결과와 종합 판정을 논리적으로 연결",
    "tradeoffs": "동시에 관찰된 이득과 손실을 하나의 Trade-off 문단으로 설명",
    "cautions": "인과 분리, 데이터 유효성 및 모델 한계를 하나의 주의 문단으로 설명",
}


def _all_text(response: dict[str, list[str]]) -> str:
    return " ".join(sentence for key in RESPONSE_KEYS for sentence in response.get(key, []))


def _number_tokens(text: str) -> list[str]:
    # Curve/Field ordinals are labels, and unit exponents are notation rather
    # than analysis values. Neither should make a valid prose rewrite fail.
    text = re.sub(r"(?<![A-Za-z])(?:Curve|Field)\s+\d+(?!\d)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bcm\s*\^\s*[-+]?\d+", "cm", text, flags=re.IGNORECASE)
    raw = re.findall(r"(?<![A-Za-z_])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", text)
    # Normalize 1.2e+03, 1200 and 1200.0 to the same semantic value.
    return [format(float(token), ".15g") for token in raw]


def _coalesce_section_paragraphs(response: dict[str, Any]) -> dict[str, list[str]]:
    """Accept valid multi-item JSON and normalize each section to one paragraph."""
    clean = validate_provider_response(response)
    result: dict[str, list[str]] = {}
    for key in RESPONSE_KEYS:
        sentences = [re.sub(r"^\s*(?:[•*-]|\d+[.)])\s*", "", item).strip() for item in clean[key]]
        result[key] = [" ".join(item for item in sentences if item)] if sentences else []
    return result


def build_language_polish_package(payload: dict[str, Any], mock_draft: dict[str, Any], *, mock_model: str) -> dict[str, Any]:
    draft = validate_provider_response(mock_draft)
    text = _all_text(draft)
    protected = [term for term in PROTECTED_TERMS if term.lower() in text.lower()]
    return {
        "contract_version": LANGUAGE_POLISH_VERSION,
        "task": "language_polish_only",
        "analysis_authority": "python_payload_and_deterministic_mock",
        "source": {"analysis_id": payload.get("analysis_id"), "analysis_type": payload.get("analysis_type"), "mock_model": mock_model},
        "content_blocks": {
            key: {"purpose": BLOCK_PURPOSES[key], "source_sentences": draft[key]}
            for key in RESPONSE_KEYS
        },
        "preservation_manifest": {
            "source_sentence_counts": {key: len(draft[key]) for key in RESPONSE_KEYS},
            "target_paragraph_counts": {key: 1 if draft[key] else 0 for key in RESPONSE_KEYS},
            "number_tokens": _number_tokens(text),
            "protected_terms": protected,
            "section_number_tokens": {key: _number_tokens(" ".join(draft[key])) for key in RESPONSE_KEYS},
            "section_protected_terms": {
                key: [term for term in protected if term.lower() in " ".join(draft[key]).lower()]
                for key in RESPONSE_KEYS
            },
            "empty_sections": [key for key in RESPONSE_KEYS if not draft[key]],
        },
        "constraints": {
            "preserve_meaning": True, "preserve_sections": True, "one_paragraph_per_section": True,
            "preserve_numbers_and_units": True, "preserve_directions_and_assessments": True,
            "do_not_add_analysis": True, "do_not_remove_supported_findings": True,
        },
    }


def build_language_polish_prompt(package: dict[str, Any]) -> tuple[str, str]:
    if package.get("task") != "language_polish_only" or package.get("contract_version") != LANGUAGE_POLISH_VERSION:
        raise ValueError("invalid_language_polish_package")
    return POLISH_SYSTEM_PROMPT, (
        "다음 검증된 Mock content block을 바탕으로 각 섹션을 응집된 문단 하나로 재구성하세요. JSON 밖의 텍스트를 출력하지 마세요.\n"
        "<LANGUAGE_POLISH_PACKAGE>\n"
        + json.dumps(package, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        + "\n</LANGUAGE_POLISH_PACKAGE>"
    )


def validate_language_polish_response(response: dict[str, Any], package: dict[str, Any]) -> dict[str, list[str]]:
    clean = _coalesce_section_paragraphs(response)
    manifest = package["preservation_manifest"]
    counts = {key: len(clean[key]) for key in RESPONSE_KEYS}
    if counts != manifest["target_paragraph_counts"]:
        raise ValueError("language_polish_changed_section_structure")
    if Counter(_number_tokens(_all_text(clean))) != Counter(manifest["number_tokens"]):
        raise ValueError("language_polish_changed_numbers")
    lowered = _all_text(clean).lower()
    if any(term.lower() not in lowered for term in manifest["protected_terms"]):
        raise ValueError("language_polish_removed_protected_term")
    for key in RESPONSE_KEYS:
        section_text = " ".join(clean[key])
        if Counter(_number_tokens(section_text)) != Counter(manifest["section_number_tokens"][key]):
            raise ValueError("language_polish_moved_number_between_sections")
        if any(term.lower() not in section_text.lower() for term in manifest["section_protected_terms"][key]):
            raise ValueError("language_polish_moved_term_between_sections")
    source = {
        key: list(package["content_blocks"][key]["source_sentences"])
        for key in RESPONSE_KEYS
    }
    if any(term in _all_text(clean) and term not in _all_text(source) for term in FORBIDDEN_CAUSAL_TERMS):
        raise ValueError("language_polish_added_causal_claim")
    return clean


_BRIEF_DROP_KEYS = {
    "analysis_id", "schema_version", "contract_version", "language", "technical_term_style", "output_policy",
    "evidence_id", "related_evidence_ids", "supporting_evidence_ids", "conflicting_evidence_ids",
    "positive_evidence_ids", "negative_evidence_ids", "affected_evidence_ids", "evidence_ids",
    "summary_id", "supporting_summary_ids", "effect_id", "tradeoff_id", "conclusion_id",
    "importance_score", "selection_rank", "selection_reasons", "priority_class", "numeric_display",
    "eligible_for_output", "selected_for_explanation", "positive_summary_key", "negative_summary_key", "weight",
    "quality_metadata", "suppression_reasons",
}


def _brief_value(value: Any, subject_names: dict[str, str], comparison_names: dict[str, str]) -> Any:
    if isinstance(value, list):
        return [_brief_value(item, subject_names, comparison_names) for item in value]
    if not isinstance(value, dict):
        return value
    result: dict[str, Any] = {}
    for key, item in value.items():
        if key in _BRIEF_DROP_KEYS:
            continue
        if key == "subject_id":
            result["subject"] = subject_names.get(str(item), str(item))
        elif key == "subject_ids":
            result["subjects"] = [subject_names.get(str(name), str(name)) for name in item]
        elif key == "baseline_subject_id":
            result["baseline"] = subject_names.get(str(item), str(item))
        elif key == "candidate_subject_id":
            result["candidate"] = subject_names.get(str(item), str(item))
        elif key == "comparison_id":
            if item is not None:
                result["comparison"] = comparison_names.get(str(item), str(item))
        elif key == "comparison_ids":
            result["comparisons"] = [comparison_names.get(str(name), str(name)) for name in item]
        elif key.endswith("_id") or key.endswith("_ids"):
            continue
        else:
            result[key] = _brief_value(item, subject_names, comparison_names)
    return result


def _prune_empty(value: Any) -> Any:
    if isinstance(value, list):
        return [clean for item in value if (clean := _prune_empty(item)) not in (None, "", [], {})]
    if isinstance(value, dict):
        return {key: clean for key, item in value.items() if (clean := _prune_empty(item)) not in (None, "", [], {})}
    return value


def _compact_evidence(item: dict[str, Any], subject_names: dict[str, str], comparison_names: dict[str, str]) -> dict[str, Any]:
    fields = ["subject_ids", "comparison_id", "field_display", "region", "quantity", "observation", "data"]
    if item.get("evidence_type") != "metric_value":
        fields += ["magnitude_class", "assessment", "physical_implication", "confidence"]
    keep = {key: item.get(key) for key in fields if key in item}
    return _prune_empty(_brief_value(keep, subject_names, comparison_names))


def _compact_subject(item: dict[str, Any], subject_names: dict[str, str], comparison_names: dict[str, str]) -> dict[str, Any]:
    clean = _brief_value(item, subject_names, comparison_names)
    clean.pop("display_name", None)
    return _prune_empty(clean)


def _compact_comparison(item: dict[str, Any], subject_names: dict[str, str], comparison_names: dict[str, str]) -> dict[str, Any]:
    keep = {key: item.get(key) for key in (
        "comparison_id", "baseline_subject_id", "candidate_subject_id", "changed_parameters",
        "is_single_parameter_controlled_comparison", "effective_claim_level", "claim_reduction_reasons",
    ) if key in item}
    return _prune_empty(_brief_value(keep, subject_names, comparison_names))


def _compact_interpretation(value: dict[str, Any], subject_names: dict[str, str], comparison_names: dict[str, str]) -> dict[str, Any]:
    family = value.get("analysis_family")
    if family == "curve":
        cleaned = _brief_value({
            "status": value.get("status"),
            "overall_assessment": value.get("overall_assessment"),
            "performance_summaries": value.get("performance_summaries"),
            "parameter_interactions": value.get("parameter_interactions"),
            "observed_tradeoffs": value.get("observed_tradeoffs"),
            "variant_rankings": value.get("variant_rankings"),
        }, subject_names, comparison_names)
        effects = []
        for raw in value.get("parameter_effects", []):
            unobserved = set(raw.get("unobserved_quantities", []))
            observed_expectations = [{
                "quantity": expected.get("quantity"),
                "expected_direction": expected.get("expected_direction"),
                "target": expected.get("target_concept"),
            } for expected in raw.get("expected_effects", []) if expected.get("quantity") not in unobserved]
            effects.append(_prune_empty({
                "comparison": comparison_names.get(str(raw.get("comparison_id")), str(raw.get("comparison_id"))),
                "parameter": raw.get("parameter"), "change": raw.get("change_direction"),
                "alignment": raw.get("alignment"), "claim_level": raw.get("claim_level"),
                "observed_expectations": observed_expectations,
                "context_dependent_quantities": raw.get("context_dependent_quantities", []),
            }))
        cleaned["parameter_effects"] = effects
        return _prune_empty(cleaned)
    selected = {key: value.get(key) for key in (
        "status", "analysis_quality", "field_specific_conclusions",
    )}
    return _prune_empty(_brief_value(selected, subject_names, comparison_names))


def build_interactive_analysis_brief(payload: dict[str, Any], mock_draft: dict[str, Any]) -> dict[str, Any]:
    """Convert internal Payload v3 into an external-LLM briefing, not a schema dump."""
    draft = validate_provider_response(mock_draft)
    subjects = payload.get("subjects", [])
    subject_names = {
        str(item.get("subject_id")): str(item.get("display_name") or item.get("subject_id"))
        for item in subjects
    }
    comparison_names: dict[str, str] = {}
    for item in payload.get("comparisons", []):
        comparison_id = str(item.get("comparison_id"))
        baseline = subject_names.get(str(item.get("baseline_subject_id")), str(item.get("baseline_subject_id")))
        candidate = subject_names.get(str(item.get("candidate_subject_id")), str(item.get("candidate_subject_id")))
        comparison_names[comparison_id] = f"{baseline} → {candidate}"

    eligible_evidence = [item for item in payload.get("evidence", []) if item.get("eligible_for_output", True)]
    extracted_values = [
        _compact_evidence(item, subject_names, comparison_names)
        for item in eligible_evidence if item.get("evidence_type") == "metric_value"
    ]
    selected_findings = [
        _compact_evidence(item, subject_names, comparison_names)
        for item in eligible_evidence
        if item.get("evidence_type") != "metric_value" and item.get("selected_for_explanation", False)
    ]
    if not selected_findings:
        selected_findings = [
            _compact_evidence(item, subject_names, comparison_names)
            for item in eligible_evidence if item.get("evidence_type") != "metric_value"
        ][:12]
    excluded_evidence = [
        {"quantity": item.get("quantity"), "region": item.get("region"), "suppression_reasons": item.get("suppression_reasons", [])}
        for item in payload.get("evidence", []) if not item.get("eligible_for_output", True)
    ]
    eligible_conclusions = [item for item in payload.get("conclusions", []) if item.get("eligible_for_output", True)]
    brief = {
        "model_context": {
            "analysis_type": payload.get("analysis_type"),
            "result_type": payload.get("context", {}).get("model_result_type", "prediction"),
            "meaning": "예측 모델 결과이며 실제 측정 또는 TCAD 검증을 대체하지 않음",
        },
        "devices": [_compact_subject(item, subject_names, comparison_names) for item in subjects],
        "parameter_changes": [_compact_comparison(item, subject_names, comparison_names) for item in payload.get("comparisons", [])],
        "extracted_values": extracted_values,
        "key_findings": selected_findings,
        "integrated_interpretation": _compact_interpretation(payload.get("interpretation", {}), subject_names, comparison_names),
        "warnings": _brief_value(payload.get("warnings", []), subject_names, comparison_names),
        "excluded_findings": excluded_evidence,
        "mock_baseline": draft,
    }
    if not brief["integrated_interpretation"] and eligible_conclusions:
        brief["supported_conclusions"] = _brief_value(eligible_conclusions, subject_names, comparison_names)
    return _prune_empty(brief)


def build_interactive_analysis_prompt(payload: dict[str, Any], mock_draft: dict[str, Any]) -> str:
    """Build the next-stage prompt for an interactive external-LLM session."""
    brief = build_interactive_analysis_brief(payload, mock_draft)
    analysis_type = str(payload.get("analysis_type", "unknown"))
    brief_lines = [
        "{",
        *[
            f'  {json.dumps(key, ensure_ascii=False)}: {json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))}'
            + ("," if index < len(brief) - 1 else "")
            for index, (key, value) in enumerate(brief.items())
        ],
        "}",
    ]
    return f"""역할: MOSFET {analysis_type} 예측 결과를 해석하고 사용자의 후속 질문에 답하세요.

포함할 내용:
- 설정 변화와 추출값
- 핵심 관찰과 parameter 영향
- 종합 성능과 Trade-off
- 경고와 해석 한계

원칙:
- mock_baseline 및 제공된 데이터와 충돌하거나 없는 수치·인과관계를 만들지 마세요.
- 일반적인 물리 예상과 모델에서 관찰된 결과를 구분하세요.
- 여러 parameter가 바뀌면 개별 기여도를 단정하지 마세요.
- Field Map은 raw pixel이 아닌 물리 region과 정규화 위치로 해석하세요.
- 결과는 prediction이며 측정 또는 TCAD 검증을 대체하지 않습니다.

[ANALYSIS_BRIEF]
{chr(10).join(brief_lines)}
"""


def validate_mock_draft_coverage(payload: dict[str, Any], draft: dict[str, Any]) -> None:
    clean = validate_provider_response(draft)
    if payload.get("context", {}).get("mode") == "comparison" and not clean["comparisons"]:
        raise ValueError("mock_draft_missing_comparison")
    interpretation = payload.get("interpretation") or {}
    has_tradeoff = bool(interpretation.get("observed_tradeoffs")) or any(
        item.get("conclusion_type") == "tradeoff" and item.get("eligible_for_output", True)
        for item in payload.get("conclusions", [])
    )
    if has_tradeoff and not clean["tradeoffs"]:
        raise ValueError("mock_draft_missing_tradeoff")
    warning_types = {item.get("warning_type") for item in payload.get("warnings", []) if item.get("eligible_for_output", True)}
    if warning_types & {"multiple_parameter_change", "model_approximation"} and not clean["cautions"]:
        raise ValueError("mock_draft_missing_caution")
