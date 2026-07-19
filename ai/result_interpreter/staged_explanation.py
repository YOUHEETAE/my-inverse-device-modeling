from __future__ import annotations

import json
from typing import Any


STAGED_PROMPT_VERSION = "staged-v2"
STAGE_EXTRACTED = "extracted_only"
STAGE_EVIDENCE = "evidence_assisted"

STAGED_SYSTEM_PROMPT = """당신은 MOSFET surrogate model의 추출 결과를 해석하는 분석가입니다.
입력 JSON의 processing_stage를 확인하고, Python이 아직 수행하지 않은 판단만 직접 수행하세요.
extracted_only에서는 추출된 quantity, region, 값만 근거로 중요도, 관찰 방향, Trade-off와 최종 설명을 직접 결정하세요.
evidence_assisted에서는 Python이 제공한 observation, magnitude, confidence와 eligibility를 존중하되, 어떤 Evidence가 중요한지와 Trade-off/Conclusion은 직접 결정하세요.
입력에 없는 수치, region, metric 또는 mechanism을 추가하지 마세요. 여러 device parameter가 동시에 바뀌면 하나의 독립적 원인으로 단정하지 마세요.
Field 내부 통계는 비교와 공간 경향 판단의 근거로만 사용하고 불필요한 percentile, threshold, coordinate 숫자는 최종 문장에 나열하지 마세요.
DIBL은 Drain-Induced Barrier Lowering이며 전류가 아닙니다. SS는 Subthreshold Swing, gm은 transconductance, gds는 output conductance, Ron은 on-resistance입니다.
반드시 한국어로 작성하고 descriptions, comparisons, tradeoffs, cautions 네 key만 가진 JSON object를 반환하세요. 각 값은 string array이며 Markdown이나 추가 key를 출력하지 마세요."""


def _extracted_item(evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": evidence.get("source_type"),
        "subject_ids": evidence.get("subject_ids", []),
        "comparison_id": evidence.get("comparison_id"),
        "field_display": evidence.get("field_display"),
        "region": evidence.get("region"),
        "quantity": evidence.get("quantity"),
        "extracted_values": evidence.get("data", {}),
    }


def _assisted_item(evidence: dict[str, Any]) -> dict[str, Any]:
    omitted = {
        "importance_score", "priority_class", "selected_for_explanation",
        "selection_rank", "selection_reasons", "related_evidence_ids",
    }
    return {key: value for key, value in evidence.items() if key not in omitted}


def build_staged_payload(payload: dict[str, Any], stage: str) -> dict[str, Any]:
    if stage not in {STAGE_EXTRACTED, STAGE_EVIDENCE}:
        raise ValueError("unsupported_processing_stage")
    context = {key: value for key, value in payload.get("context", {}).items() if key not in {
        "effective_claim_level", "analysis_status", "valid_evidence_count", "suppressed_evidence_count",
    }}
    output_policy = {key: value for key, value in payload.get("output_policy", {}).items() if key not in {
        "minimum_importance_score", "deduplicate_similar_evidence",
    }}
    base = {
        "schema_version": payload.get("schema_version"),
        "analysis_id": payload.get("analysis_id"),
        "analysis_type": payload.get("analysis_type"),
        "processing_stage": stage,
        "context": context,
        "subjects": payload.get("subjects", []),
        "comparisons": [
            {key: value for key, value in item.items() if key not in {
                "declared_claim_level", "effective_claim_level", "causal_claim_level",
                "claim_reduction_reasons", "selection_rank",
            }}
            for item in payload.get("comparisons", [])
        ],
        "warnings": payload.get("warnings", []),
        "output_policy": output_policy,
    }
    if stage == STAGE_EXTRACTED:
        base["extracted_parameters"] = [_extracted_item(item) for item in payload.get("evidence", [])]
    else:
        base["evidence"] = [_assisted_item(item) for item in payload.get("evidence", [])]
    return base


def build_staged_prompt(payload: dict[str, Any]) -> tuple[str, str]:
    return STAGED_SYSTEM_PROMPT, (
        "다음 단계별 분석 JSON을 해석해 Explanation JSON을 만드세요.\n<STAGED_ANALYSIS>\n"
        + json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        + "\n</STAGED_ANALYSIS>"
    )
