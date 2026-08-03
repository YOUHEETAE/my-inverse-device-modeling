from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from backend.answer_contract import normalize_public_text, validate_public_answer_text
from backend.answer_quality import validate_answer_quality
from backend.learning.knowledge_base import load_theory_knowledge_base
from backend.public_presentation import public_ai_failure_message

from .field_analyzer import build_field_payload
from .field_conclusions import build_focused_field_conclusions
from .field_links import build_cross_domain_links
from .comparison_focus import (
    ComparisonFocus,
    compact_context_comparisons,
    compact_device_conditions,
    focus_allows_item,
    focus_clarification_text,
    focused_comparisons,
    resolve_comparison_focus,
    validate_focused_claim_text,
)
from .field_renderer import render_field_explanation
from .cross_domain_audit import build_field_iv_audit, validate_field_iv_audit
from .curve_analyzer import build_curve_payload
from .iv_chat import IVChatService


FIELD_CHAT_CONTEXT_BYTE_BUDGET = 14_000
FIELD_CHAT_INTENTS = {
    "explain_overall",
    "explain_region",
    "explain_hotspot",
    "explain_physical_meaning",
    "compare_maps",
    "cross_check_iv",
    "define_display",
    "evaluate_claim",
    "hypothetical",
    "new_experiment",
    "out_of_scope",
    "clarify",
}
FIELD_CHAT_STRUCTURES = {
    "overview",
    "spatial_cause_and_effect",
    "region_by_region",
    "observation_to_iv_check",
    "definition",
    "claim_review",
    "comparison",
    "concise",
}
KNOWN_REGIONS = {
    "channel_near_surface",
    "source_side_ldd_near_surface",
    "drain_side_ldd_near_surface",
    "source_near_surface",
    "drain_near_surface",
    "deep_bulk",
    "oxide",
    "gate",
    "global",
}
DISPLAY_THEORY = {
    "potential": ("potential", "source_barrier", "threshold_voltage"),
    "electric_field": ("electric_field", "short_channel_effect", "dibl"),
    "electron_density": ("on_current", "threshold_voltage"),
    "hole_density": ("depletion_region", "threshold_voltage"),
    "electron_current_density": ("on_current", "on_resistance"),
    "hole_current_density": ("off_current",),
    "total_current_density": ("on_current", "on_resistance"),
    "srh_recombination": ("off_current",),
    "energy_band": ("source_barrier", "threshold_voltage", "dibl"),
}
_NUMBER = re.compile(
    r"(?<![A-Za-z_])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?(?![A-Za-z_])"
)
_UNSUPPORTED_ELECTRICAL_CLAIM = re.compile(
    r"(?P<metric>DIBL|Ioff|Ion|Vth|SS|Ron|gds|gm(?:\s*max)?)"
    r".{0,28}(?P<direction>증가|감소|개선|악화|커졌|작아졌|높아졌|낮아졌)"
    r".{0,18}(?:확인|나타났|보였|입니다|했다|합니다)",
    flags=re.IGNORECASE | re.DOTALL,
)
_UNSUPPORTED_BREAKDOWN_CLAIM = re.compile(
    r"(?:breakdown|항복).{0,20}(?:발생|확인|일어났)",
    flags=re.IGNORECASE | re.DOTALL,
)
_BREAKDOWN_LIMIT_CUES = (
    "않", "없", "못", "여부", "가능성", "단정", "확정할 수",
    "추가 확인", "확인해야", "검증해야",
)


@dataclass(frozen=True)
class FieldQuestionIntent:
    intent: str
    requested_concepts: tuple[str, ...] = ()
    requested_regions: tuple[str, ...] = ()
    requested_iv_metrics: tuple[str, ...] = ()
    needs_current_result: bool = True
    needs_new_experiment: bool = False
    references_previous: bool = False
    answer_structure: str = "spatial_cause_and_effect"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FieldAnalysisSnapshot:
    analysis_id: str
    field_labels: tuple[str, ...]
    display: str
    payload: dict[str, Any]
    automatic_explanation: dict[str, list[str]]
    selection_signature: tuple[Any, ...] = ()
    iv_payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class FieldChatResponse:
    answer: str
    source: str
    intent: FieldQuestionIntent | None = None
    used_evidence_ids: tuple[str, ...] = ()
    suggested_followup: str | None = None
    needs_new_experiment: bool = False
    diagnostic: dict[str, Any] = field(default_factory=dict)
    pipeline_stage: str | None = None
    intent_checkpoint: dict[str, Any] = field(default_factory=dict)


def validate_field_intent(
    data: Any,
    *,
    available_concepts: set[str],
    question: str = "",
) -> FieldQuestionIntent:
    if not isinstance(data, dict):
        raise ValueError("invalid_field_intent")
    # The intent is the only indispensable classification result. Some models
    # add harmless metadata such as ``confidence`` or omit empty arrays even
    # after a format-repair request. Project the response onto the public
    # contract and derive conservative defaults for those non-critical fields
    # instead of rejecting an otherwise usable classification.
    intent = str(data.get("intent", ""))
    default_structures = {
        "explain_overall": "overview",
        "explain_region": "region_by_region",
        "explain_hotspot": "spatial_cause_and_effect",
        "explain_physical_meaning": "spatial_cause_and_effect",
        "compare_maps": "comparison",
        "cross_check_iv": "observation_to_iv_check",
        "define_display": "definition",
        "evaluate_claim": "claim_review",
        "hypothetical": "spatial_cause_and_effect",
        "new_experiment": "concise",
        "out_of_scope": "concise",
        "clarify": "concise",
    }
    structure = str(
        data.get("answer_structure") or default_structures.get(intent, "")
    )
    concepts = data.get("requested_concepts", [])
    regions = data.get("requested_regions", [])
    metrics = data.get("requested_iv_metrics", [])
    default_needs_result = intent != "out_of_scope"
    default_needs_experiment = intent in {"hypothetical", "new_experiment"}
    flags = (
        data.get("needs_current_result", default_needs_result),
        data.get("needs_new_experiment", default_needs_experiment),
        data.get("references_previous", False),
    )
    if (
        intent not in FIELD_CHAT_INTENTS
        or structure not in FIELD_CHAT_STRUCTURES
        or not all(isinstance(value, (list, tuple)) for value in (concepts, regions, metrics))
        or any(not isinstance(value, bool) for value in flags)
    ):
        raise ValueError("invalid_field_intent_content")
    clean_concepts = tuple(dict.fromkeys(str(value) for value in concepts))
    if not set(clean_concepts).issubset(available_concepts):
        raise ValueError("unknown_field_concept")
    clean_regions = tuple(dict.fromkeys(str(value) for value in regions))
    if not set(clean_regions).issubset(KNOWN_REGIONS):
        raise ValueError("unknown_field_region")
    clean_metrics = tuple(dict.fromkeys(str(value) for value in metrics))
    allowed_metrics = {"vth", "dibl", "ioff", "ion", "ss", "gm_max", "ron", "gds"}
    if not set(clean_metrics).issubset(allowed_metrics):
        raise ValueError("unknown_field_iv_metric")
    if intent in {"hypothetical", "new_experiment"} and not flags[1]:
        raise ValueError("field_new_experiment_flag_required")
    if intent == "out_of_scope" and flags[0]:
        raise ValueError("field_out_of_scope_uses_result")
    lowered = question.lower()
    current_cues = (
        "현재", "이번", "지금", "이 field", "이 map", "분포", "영역", "hotspot",
        "핫스팟", "비교", "변화", "강해", "약해", "왜",
    )
    experiment_cues = (
        "바꾸면", "변경하면", "추가해", "추가하면", "다시 계산",
        "새 조건", "일 때는",
    )
    if intent != "out_of_scope" and any(cue in lowered for cue in current_cues) and not flags[0]:
        raise ValueError("field_current_result_cue_mismatch")
    if any(cue in lowered for cue in experiment_cues) and not flags[1]:
        raise ValueError("field_experiment_cue_mismatch")
    return FieldQuestionIntent(
        intent=intent,
        requested_concepts=clean_concepts,
        requested_regions=clean_regions,
        requested_iv_metrics=clean_metrics,
        needs_current_result=flags[0],
        needs_new_experiment=flags[1],
        references_previous=flags[2],
        answer_structure=structure,
    )


def _deterministic_field_intent(
    question: str,
) -> FieldQuestionIntent | None:
    """Handle high-confidence Field quantification questions locally."""
    lowered = " ".join(question.lower().split())
    field_cue = any(
        cue in lowered
        for cue in ("fieldmap", "field map", "필드맵", "분포")
    )
    quantification_cue = any(
        cue in lowered
        for cue in (
            "수치화", "정량", "어떤 파라미터", "어떤 값",
            "무슨 파라미터", "변화하는 파라미터",
        )
    )
    if field_cue and quantification_cue:
        return FieldQuestionIntent(
            intent="compare_maps",
            needs_current_result=True,
            answer_structure="comparison",
        )
    return None


def _intent_prompt(payload: dict[str, Any]) -> tuple[str, str]:
    system = """당신은 MOSFET Field Map 학습 질문 해석기다.
답변하지 말고 질문의 의도만 분류한다. 제공된 concept, named region, I-V metric
이름만 사용한다. 현재 보이는 분포·영역·비교·원인을 묻는 질문은
needs_current_result=true다. 새로운 조건 또는 재계산 요청은
needs_new_experiment=true다. Field 관찰을 I-V와 연결해 확인하려는 질문은
cross_check_iv다. Field Map을 어떤 값으로 정량화하는지, 현재 무엇이 변했는지
묻는 질문은 compare_maps 또는 explain_overall이며 clarify로 분류하지 않는다.
clarify는 질문의 지시 대상을 현재 화면과 대화에서도 결정할 수 없을 때만 쓴다.
응답은 지정된 여덟 키만 가진 JSON object다."""
    return system, (
        "<FIELD_QUESTION_CONTEXT>\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + "\n</FIELD_QUESTION_CONTEXT>"
    )


def _answer_prompt(payload: dict[str, Any]) -> tuple[str, str]:
    system = """당신은 반도체 소자 학습용 Field Map 튜터다.
Python이 검증한 context_pack만 사용해 자연스럽고 충분한 한국어 답변을 작성한다.
현재 공간 관찰→물리적 의미→I-V에서 확인할 항목→해석 한계 순서로 연결한다.
Field Map만으로 DIBL, Vth, Ioff, Ion, SS 등의 실제 증가·감소를 확정하지 않는다.
cross_domain_audit에 verified_iv_facts가 있을 때만, 그것을 별도의 I-V 관찰이라고
명시해 해당 metric의 실제 방향을 말할 수 있다. 이 경우 Field가 I-V 변화를
일으켰다고 단정하지 말고 두 관찰이 물리적으로 함께 해석될 수 있다고 표현한다.
verified_iv_facts가 없으면 어떤 가능성과 일치하며 어떤 I-V 지표를 확인해야 하는지만
말한다. Electric field만으로 breakdown 발생을 확정하지 않는다. 국부 current
density와 terminal current를 동일시하지 않는다. 여러 parameter가 동시에 바뀌면
개별 원인을 단정하지 않는다. 수치와 변화 방향을 만들거나 재계산하지 않는다.
정량화 질문에는 device input parameter와 Field에서 계산한 spatial metric을
구분한다. quantification_guide의 method_catalog로 계산 방법을 설명하고,
current_spatial_changes로 현재 검증된 방향을 설명한다. exact numeric value는
numeric_values_allowed=true인 항목과 changed_parameters에 대해서만 말한다.
numeric_values_allowed=false이면 내부 raw value를 추정하지 말고 통계량의 이름과
검증된 정성 방향만 설명한다.
comparison_focus는 기존 Comparison Plan의 분석 초점만 좁힌다. 지정된 subject와
comparison 밖의 공간 근거를 섞지 않고, original_plan_claim_level보다 강한 인과
주장으로 승격하지 않는다.
evidence ID는 used_evidence_ids JSON 필드에만 넣고 answer 본문에 노출하지 않는다.
응답은 answer, used_evidence_ids, needs_new_experiment, suggested_followup만 가진
JSON object다."""
    return system, (
        "<GROUNDED_FIELD_QUESTION>\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + "\n</GROUNDED_FIELD_QUESTION>"
    )


def _collect_numbers(value: Any) -> set[float]:
    result: set[float] = set()
    if isinstance(value, dict):
        for item in value.values():
            result.update(_collect_numbers(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            result.update(_collect_numbers(item))
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isfinite(float(value)):
            result.add(float(value))
    elif isinstance(value, str):
        result.update(float(item) for item in _NUMBER.findall(value))
    return result


def _answer_number_tokens(value: str) -> tuple[str, ...]:
    """Return factual numbers while ignoring list markers and unit exponents."""
    text = re.sub(r"(?m)^\s*\d+[.)]\s+", "", value)
    text = re.sub(
        r"\b(?:cm|mm|nm|um|µm|m)\s*(?:\^|\*\*)\s*[-+]?\d+",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return tuple(_NUMBER.findall(text))


def _claims_breakdown_as_observed(answer: str) -> bool:
    for sentence in re.split(r"(?<=[.!?。！？])\s+|\n+", answer):
        if not _UNSUPPORTED_BREAKDOWN_CLAIM.search(sentence):
            continue
        lowered = sentence.lower()
        if not any(cue in lowered for cue in _BREAKDOWN_LIMIT_CUES):
            return True
    return False


def validate_field_answer(
    data: Any,
    *,
    intent: FieldQuestionIntent,
    context_pack: dict[str, Any],
    question: str,
) -> FieldChatResponse:
    if not isinstance(data, dict) or set(data) != {
        "answer", "used_evidence_ids", "needs_new_experiment", "suggested_followup",
    }:
        raise ValueError("invalid_field_answer_keys")
    answer = normalize_public_text(data.get("answer", ""))
    if not answer or len(answer) > 2800:
        raise ValueError("invalid_field_answer_content")
    validate_public_answer_text(answer)
    used = data.get("used_evidence_ids")
    if not isinstance(used, list) or any(not isinstance(item, str) for item in used):
        raise ValueError("invalid_field_answer_evidence")
    used_ids = tuple(dict.fromkeys(used))
    allowed_ids = set(context_pack.get("allowed_evidence_ids", []))
    if not set(used_ids).issubset(allowed_ids):
        raise ValueError("unknown_field_answer_evidence")
    needs_new = data.get("needs_new_experiment")
    if not isinstance(needs_new, bool) or needs_new != intent.needs_new_experiment:
        raise ValueError("field_answer_experiment_flag_mismatch")
    followup_value = data.get("suggested_followup")
    followup = normalize_public_text(followup_value) if followup_value is not None else None
    if followup == "":
        followup = None
    if followup and len(followup) > 400:
        raise ValueError("invalid_field_followup")
    if followup:
        validate_public_answer_text(followup)
    validate_focused_claim_text(
        answer,
        context_pack,
        error_code="field_answer_exceeds_comparison_claim_level",
    )
    if intent.needs_current_result and not used_ids:
        raise ValueError("current_field_answer_requires_evidence")
    audit = context_pack.get("cross_domain_audit") or {}
    verified_directions: dict[str, tuple[str, str]] = {}
    for item in audit.get("verified_iv_facts", []):
        quantity = str(item.get("quantity", "")).lower()
        metric = "vth" if quantity.startswith("vth_") else quantity
        verified_directions[metric] = (
            str(item.get("observation", "")),
            str(item.get("evidence_id", "")),
        )
    metric_names = {
        "dibl": "dibl", "ioff": "ioff", "ion": "ion", "vth": "vth",
        "ss": "ss", "ron": "ron", "gds": "gds", "gm": "gm_max",
        "gm max": "gm_max",
    }
    direction_names = {
        "증가": "increased", "커졌": "increased", "높아졌": "increased",
        "감소": "decreased", "작아졌": "decreased", "낮아졌": "decreased",
        "개선": "improved", "악화": "degraded",
    }
    for match in _UNSUPPORTED_ELECTRICAL_CLAIM.finditer(answer):
        metric = metric_names.get(match.group("metric").lower())
        claimed = direction_names.get(match.group("direction"))
        verified = verified_directions.get(str(metric))
        # "improved/degraded" is metric-dependent and therefore cannot be
        # mechanically grounded by a raw increase/decrease observation.
        if (
            verified is None
            or claimed in {"improved", "degraded"}
            or verified[0] != claimed
            or verified[1] not in used_ids
        ):
            raise ValueError("field_answer_claims_unverified_electrical_change")
    if _claims_breakdown_as_observed(answer):
        raise ValueError("field_answer_claims_unverified_breakdown")
    allowed_numbers = _collect_numbers(context_pack) | _collect_numbers(question)
    for token in _answer_number_tokens(answer + " " + (followup or "")):
        number = float(token)
        if not any(
            math.isclose(number, allowed, rel_tol=.015, abs_tol=.015)
            for allowed in allowed_numbers
        ):
            raise ValueError("ungrounded_field_answer_number")
    quality = validate_answer_quality(
        domain="field",
        question=question,
        answer=answer,
        route=intent.intent,
        uses_current_result=intent.needs_current_result,
        needs_new_experiment=needs_new,
        evidence_ids=used_ids,
        requested_terms=(
            *intent.requested_concepts,
            *intent.requested_regions,
            *intent.requested_iv_metrics,
        ),
        suggested_followup=followup,
    )
    return FieldChatResponse(
        answer=answer,
        source="external_llm",
        intent=intent,
        used_evidence_ids=used_ids,
        suggested_followup=followup,
        needs_new_experiment=needs_new,
        diagnostic={"quality_report": quality.to_dict()},
    )


def _clean_field_evidence(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": item.get("evidence_id"),
        "observation": item.get("observation"),
        "region": item.get("region"),
        "magnitude": item.get("magnitude_class"),
        "confidence": item.get("confidence"),
    }


def _field_quantification_guide(
    payload: dict[str, Any],
    display: str,
    focus: ComparisonFocus | None = None,
    comparison_ids: set[str] | None = None,
) -> dict[str, Any]:
    method_catalog: list[dict[str, Any]] = []
    current_changes: list[dict[str, Any]] = []
    seen_methods: set[tuple[Any, ...]] = set()
    method_meanings = {
        "regional_level_change": "named region의 대표적인 높은 값 수준 비교",
        "hotspot_strength_change": "같은 통계량으로 국부 hotspot 강도 비교",
        "high_value_area_change": (
            "공통 threshold 이상 영역이 차지하는 면적 비율 비교"
        ),
        "hotspot_location_shift": "hotspot 위치의 이동 거리와 방향 비교",
    }
    for item in payload.get("evidence", []):
        if (
            not item.get("eligible_for_output", True)
            or item.get("field_display") != display
            or not item.get("comparison_id")
            or (focus is not None and not focus_allows_item(item, focus))
            or (
                comparison_ids is not None
                and str(item.get("comparison_id")) not in comparison_ids
            )
        ):
            continue
        data = item.get("data") or {}
        statistic = data.get("statistic") or data.get("comparison_statistic")
        threshold = data.get("threshold_reference")
        method_key = (item.get("evidence_type"), statistic, threshold)
        if method_key not in seen_methods:
            method_catalog.append(
                {
                    "metric": item.get("evidence_type"),
                    "statistic": statistic,
                    "threshold_reference": threshold,
                    "meaning": method_meanings.get(
                        str(item.get("evidence_type")), "공간 분포 변화 비교"
                    ),
                }
            )
            seen_methods.add(method_key)
        if item.get("selected_for_explanation"):
            current_changes.append(
                {
                    "evidence_id": item.get("evidence_id"),
                    "metric": item.get("evidence_type"),
                    "quantity": item.get("quantity"),
                    "region": item.get("region"),
                    "observation": item.get("observation"),
                    "magnitude": item.get("magnitude_class"),
                    "numeric_values_allowed": bool(
                        (item.get("numeric_display") or {}).get("allowed")
                    ),
                }
            )
    return {
        "device_input_source": "comparisons.changed_parameters",
        "method_catalog": method_catalog[:8],
        "current_spatial_changes": current_changes[:6],
        "numeric_policy": (
            "Exact Field values may be stated only when numeric_values_allowed is "
            "true. Otherwise state the statistic and verified qualitative direction."
        ),
    }


def build_field_context_pack(
    snapshot: FieldAnalysisSnapshot,
    intent: FieldQuestionIntent,
    focus: ComparisonFocus | None = None,
) -> dict[str, Any]:
    payload = snapshot.payload
    focus = focus or resolve_comparison_focus(payload, "")
    focused_subject_ids = set(focus.subject_ids)
    comparisons = compact_context_comparisons(payload, focus)
    context_comparison_ids = {
        str(item.get("comparison_id"))
        for item in comparisons if item.get("comparison_id")
    }
    quantification_guide = (
        _field_quantification_guide(
            payload,
            snapshot.display,
            focus,
            (
                context_comparison_ids
                if focus.focus_mode == "full_plan" else None
            ),
        )
        if intent.needs_current_result
        else {}
    )
    interpretation = payload.get("interpretation") or {}
    conclusions = list(interpretation.get("field_specific_conclusions", []))
    conclusions = [
        item for item in conclusions if focus_allows_item(item, focus)
        if (
            focus.focus_mode != "full_plan"
            or item.get("comparison_id") is None
            or str(item.get("comparison_id")) in context_comparison_ids
        )
    ]
    if focus.focus_mode in {"specific_pair", "subject_group"}:
        conclusions = build_focused_field_conclusions(
            payload, set(focus.comparison_ids), maximum=6,
        )
    if intent.requested_concepts:
        conclusions = [
            item for item in conclusions
            if item.get("concept") in intent.requested_concepts
        ]
    if intent.requested_regions:
        conclusions = [
            item for item in conclusions
            if item.get("region") in intent.requested_regions
        ]
    conclusions = conclusions[:6] if intent.needs_current_result else []
    evidence_ids = {
        str(evidence_id)
        for item in conclusions
        for evidence_id in item.get("evidence_ids", [])
    }
    evidence = [
        item for item in payload.get("evidence", [])
        if item.get("eligible_for_output", True)
        and item.get("evidence_id") in evidence_ids
    ]
    available_links = (
        build_cross_domain_links(conclusions)
        if focus.focus_mode in {"specific_pair", "subject_group"}
        else list(interpretation.get("cross_domain_links", []))
    )
    links = [
        item for item in available_links
        if focus_allows_item(item, focus)
        if not intent.requested_concepts
        or item.get("source_concept") in intent.requested_concepts
    ][:4] if intent.needs_current_result else []
    for item in links:
        evidence_ids.update(str(value) for value in item.get("evidence_ids", []))
    audit = build_field_iv_audit(
        payload,
        snapshot.iv_payload,
        requested_metrics=(
            set(intent.requested_iv_metrics)
            if intent.requested_iv_metrics
            else None
        ),
        comparison_ids=(
            context_comparison_ids
            if context_comparison_ids else None
        ),
        field_links=links,
    )
    validate_field_iv_audit(audit)
    evidence_ids.update(
        str(item["evidence_id"])
        for item in audit.get("verified_iv_facts", [])
        if item.get("evidence_id")
    )
    evidence_ids.update(
        str(item["evidence_id"])
        for item in quantification_guide.get("current_spatial_changes", [])
        if item.get("evidence_id")
    )
    allowed_ids = tuple(sorted(evidence_ids))
    concept_ids = list(DISPLAY_THEORY.get(snapshot.display, ()))
    for item in links:
        concept_ids.extend(item.get("theory_concepts", []))
    theory = [
        concept.to_prompt_dict()
        for concept in load_theory_knowledge_base().retrieve(concept_ids, limit=4)
    ]
    subject_names = {
        str(item.get("subject_id")): str(item.get("display_name"))
        for item in payload.get("subjects", [])
    }
    compact_devices, fixed_conditions = compact_device_conditions(
        payload, focus,
    )
    return {
        "analysis_id": snapshot.analysis_id,
        "comparison_focus": focus.to_dict(),
        "original_comparison_plan": {
            key: (payload.get("comparison_plan") or {}).get(key)
            for key in (
                "analysis_mode", "baseline_subject_id",
                "changed_parameters", "sweep_parameter",
                "sweep_subject_ids", "allowed_claim_level",
            )
        },
        "focus_claim_boundary": (
            "The focus filters the existing plan only. It cannot promote "
            "the original claim level or create a new comparison."
        ),
        "field_display": snapshot.display,
        "field_labels": snapshot.field_labels,
        "fixed_bias": payload.get("context", {}).get("fixed_bias", {}),
        "shared_color_scale": payload.get("context", {}).get("shared_color_scale"),
        "devices": compact_devices if intent.needs_current_result else [],
        "fixed_conditions": (
            fixed_conditions if intent.needs_current_result else {}
        ),
        "context_policy": {
            "comparison_count_sent": len(comparisons),
            "all_pair_raw_data_sent": False,
            "fixed_parameters_factored": bool(fixed_conditions),
        },
        "comparisons": [
            {
                "baseline": subject_names.get(str(item.get("baseline_subject_id"))),
                "candidate": subject_names.get(str(item.get("candidate_subject_id"))),
                "changed_parameters": item.get("changed_parameters", []),
                "controlled_single_parameter": item.get(
                    "is_single_parameter_controlled_comparison", False
                ),
            }
            for item in comparisons
        ] if intent.needs_current_result else [],
        "multi_condition_trends": (
            [
                {
                    "quantity": item.get("quantity"),
                    "region": item.get("region"),
                    "ordered_subject_ids": item.get(
                        "ordered_subject_ids", []
                    ),
                    "ordered_sweep_values": item.get(
                        "ordered_sweep_values", []
                    ),
                    "direction": item.get("direction"),
                    "claim_limit": item.get("claim_limit"),
                    "numeric_values_allowed": False,
                }
                for item in interpretation.get(
                    "multi_condition_trends", []
                )
            ]
            if (
                intent.needs_current_result
                and focus.focus_mode == "full_plan"
            )
            else []
        ),
        "quantification_guide": quantification_guide,
        "spatial_observations": [_clean_field_evidence(item) for item in evidence],
        "physical_interpretations": [
            {
                "concept": item.get("concept"),
                "assessment": item.get("assessment"),
                "region": item.get("region"),
                "support_level": item.get("support_level"),
                "claim_limit": item.get("claim_limit"),
                "evidence_ids": item.get("evidence_ids", []),
            }
            for item in conclusions
        ],
        "iv_verification_links": [
            {
                "source_concept": item.get("source_concept"),
                "source_assessment": item.get("source_assessment"),
                "region": item.get("region"),
                "physical_interpretation": item.get("physical_interpretation"),
                "iv_metrics_to_check": item.get("iv_metrics_to_check", []),
                "link_status": item.get("link_status"),
                "evidence_ids": item.get("evidence_ids", []),
            }
            for item in links
        ],
        "cross_domain_audit": audit,
        "theory_facts": theory,
        "field_claim_limits": [
            "Field Map alone does not verify an electrical metric change.",
            "Local current density is not terminal current.",
            "Electric field alone does not verify breakdown or lifetime.",
        ],
        "allowed_evidence_ids": allowed_ids,
    }


class FieldChatService(IVChatService):
    quality_domain = "field"

    def __init__(self, provider: Any | None) -> None:
        super().__init__(provider)

    @staticmethod
    def build_snapshot(
        outputs: list[tuple[str, Any]],
        display: str,
        scale_mode: str,
        range_mode: str,
        *,
        selection_signature: tuple[Any, ...] = (),
        iv_results: list[Any] | None = None,
        iv_configs: list[dict[str, str]] | None = None,
    ) -> FieldAnalysisSnapshot:
        payload = build_field_payload(outputs, display, scale_mode, range_mode).to_dict()
        iv_payload = None
        if iv_results is not None and iv_configs is not None:
            iv_payload = build_curve_payload(iv_results, iv_configs).to_dict()
        return FieldAnalysisSnapshot(
            analysis_id=str(payload["analysis_id"]),
            field_labels=tuple(str(item[0]) for item in outputs),
            display=str(payload.get("context", {}).get("display", display)),
            payload=payload,
            automatic_explanation=render_field_explanation(payload),
            selection_signature=selection_signature,
            iv_payload=iv_payload,
        )

    @classmethod
    def _field_error_response(
        cls,
        failure: str | None,
        diagnostic: dict[str, Any],
        *,
        intent: FieldQuestionIntent | None,
        checkpoint: bool,
    ) -> FieldChatResponse:
        value = dict(diagnostic)
        value["intent_checkpoint_available"] = checkpoint
        wait = cls._retry_seconds(failure, value)
        if wait is not None:
            value["recommended_retry_after_seconds"] = wait
        stage = str(value.get("stage", ""))
        return FieldChatResponse(
            answer=public_ai_failure_message(
                feature="Field Map",
                failure=failure,
                diagnostic=value,
                retry_after_seconds=wait,
                checkpoint_preserved=checkpoint,
            ),
            source="external_error",
            intent=intent,
            needs_new_experiment=bool(intent and intent.needs_new_experiment),
            diagnostic=value,
            pipeline_stage=stage,
            intent_checkpoint=intent.to_dict() if checkpoint and intent else {},
        )

    def answer(
        self,
        snapshot: FieldAnalysisSnapshot,
        question: str,
        *,
        history: list[dict[str, Any]] | None = None,
        intent_checkpoint: dict[str, Any] | None = None,
    ) -> FieldChatResponse:
        clean_question = " ".join(str(question).split())
        if not clean_question or len(clean_question) > 800:
            raise ValueError("invalid_field_question")
        history = [
            {
                "question": " ".join(str(item.get("question", "")).split())[:500],
                "answer": " ".join(str(item.get("answer", "")).split())[:900],
                "comparison_focus": item.get("comparison_focus"),
            }
            for item in (history or [])[-2:]
            if item.get("source") != "external_error"
        ]
        focus = resolve_comparison_focus(
            snapshot.payload,
            clean_question,
            history=history,
        )
        if focus.requires_clarification:
            return FieldChatResponse(
                answer=focus_clarification_text(snapshot.payload, focus),
                source="local_router",
                intent=FieldQuestionIntent(
                    intent="clarify",
                    needs_current_result=False,
                    answer_structure="concise",
                ),
                diagnostic={"comparison_focus": focus.to_dict()},
            )
        available_concepts = {
            str(item.get("concept"))
            for item in (snapshot.payload.get("interpretation") or {}).get(
                "field_specific_conclusions", []
            )
            if item.get("concept")
        }
        provider_calls: list[dict[str, Any]] = []
        intent = _deterministic_field_intent(clean_question)
        if intent is None and intent_checkpoint:
            try:
                intent = validate_field_intent(
                    intent_checkpoint,
                    available_concepts=available_concepts,
                    question=clean_question,
                )
            except ValueError:
                intent = None
        if intent is None:
            intent_payload = {
                "user_question": clean_question,
                "field_display": snapshot.display,
                "field_labels": snapshot.field_labels,
                "allowed_intents": sorted(FIELD_CHAT_INTENTS),
                "allowed_answer_structures": sorted(FIELD_CHAT_STRUCTURES),
                "response_keys": [
                    "intent", "requested_concepts", "requested_regions",
                    "requested_iv_metrics", "needs_current_result",
                    "needs_new_experiment", "references_previous",
                    "answer_structure",
                ],
                "available_concepts": sorted(available_concepts),
                "available_regions": sorted(KNOWN_REGIONS),
                "available_iv_metrics": [
                    "vth", "dibl", "ioff", "ion", "ss", "gm_max", "ron", "gds",
                ],
                "comparison_plan": snapshot.payload.get(
                    "comparison_plan", {}
                ),
                "resolved_comparison_focus": focus.to_dict(),
                "recent_conversation": history,
            }
            intent, diagnostic, failure = self._call(
                _intent_prompt,
                intent_payload,
                lambda data: validate_field_intent(
                    data,
                    available_concepts=available_concepts,
                    question=clean_question,
                ),
                stage="field_intent_interpretation",
            )
            if intent is None:
                return self._field_error_response(
                    failure, diagnostic, intent=None, checkpoint=False,
                )
            provider_calls.extend(diagnostic.get("provider_calls", ()))
        context_pack = build_field_context_pack(snapshot, intent, focus)
        answer_payload = {
            "user_question": clean_question,
            "interpreted_intent": intent.to_dict(),
            "recent_conversation": history if intent.references_previous else [],
            "context_pack": context_pack,
        }
        system, user = _answer_prompt(answer_payload)
        if len((system + user).encode("utf-8")) > FIELD_CHAT_CONTEXT_BYTE_BUDGET:
            context_pack["theory_facts"] = context_pack["theory_facts"][:3]
            context_pack["physical_interpretations"] = context_pack[
                "physical_interpretations"
            ][:4]
            context_pack["spatial_observations"] = context_pack[
                "spatial_observations"
            ][:8]
            answer_payload["recent_conversation"] = []
        response, diagnostic, failure = self._call(
            _answer_prompt,
            answer_payload,
            lambda data: validate_field_answer(
                data,
                intent=intent,
                context_pack=context_pack,
                question=clean_question,
            ),
            stage="field_answer_generation",
        )
        if response is None:
            if provider_calls:
                diagnostic = dict(diagnostic)
                diagnostic["provider_calls"] = [
                    *provider_calls,
                    *diagnostic.get("provider_calls", ()),
                ]
            return self._field_error_response(
                failure, diagnostic, intent=intent, checkpoint=True,
            )
        provider_calls.extend(diagnostic.get("provider_calls", ()))
        response_diagnostic = dict(response.diagnostic)
        response_diagnostic["comparison_focus"] = focus.to_dict()
        return replace(
            response,
            diagnostic={
                **response_diagnostic,
                "provider_calls": tuple(provider_calls),
            },
        )
