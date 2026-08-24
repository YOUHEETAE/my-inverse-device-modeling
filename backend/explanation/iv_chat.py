from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from backend.answer_contract import normalize_public_text, validate_public_answer_text
from backend.answer_quality import (
    build_validation_failure_record,
    validate_answer_quality,
)
from backend.learning.knowledge_base import load_theory_knowledge_base
from backend.public_presentation import public_ai_failure_message
from tcad.data_extraction.parameter_extraction_core import (
    PARAMETER_EXTRACTION_DEFINITIONS,
)

from .curve_analyzer import build_curve_payload
from .iv_templates import IV_TEMPLATES
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
from .providers.external import ProviderHTTPError
from .providers.mock import MockExplanationProvider
from .safety import validate_provider_response
from .usage import consume_provider_diagnostic


IV_CHAT_CONTEXT_BYTE_BUDGET = 16_000
IV_CHAT_INTENTS = {
    "explain_overall",
    "explain_metric",
    "explain_mechanism",
    "compare_curves",
    "define_extraction",
    "evaluate_claim",
    "hypothetical",
    "new_experiment",
    "out_of_scope",
    "clarify",
}
IV_CHAT_STRUCTURES = {
    "overview",
    "cause_and_effect",
    "parameter_by_parameter",
    "definition_and_extraction",
    "claim_review",
    "comparison",
    "concise",
}
METRIC_ALIASES = {
    "vth": "vth",
    "threshold": "vth",
    "문턱전압": "vth",
    "ion": "ion",
    "on current": "ion",
    "ioff": "ioff",
    "off current": "ioff",
    "ss": "ss",
    "subthreshold swing": "ss",
    "dibl": "dibl",
    "gm": "gm_max",
    "gm max": "gm_max",
    "gds": "gds",
    "ron": "ron",
    "on resistance": "ron",
    "lambda": "lambda_clm",
    "λ": "lambda_clm",
    "ion/ioff": "ion_ioff_ratio",
}
KNOWN_METRICS = {
    "vth",
    "vth_at_vd_0_05",
    "vth_at_vd_1_5",
    "ion",
    "ioff",
    "ion_ioff_ratio",
    "ss",
    "dibl",
    "gm_max",
    "gds",
    "ron",
    "lambda_clm",
}
METRIC_TO_EXTRACTION = {
    "vth": ("vth_low_v", "vth_high_v"),
    "vth_at_vd_0_05": ("vth_low_v",),
    "vth_at_vd_1_5": ("vth_high_v",),
    "ion": ("ion_ma_per_um",),
    "ioff": ("ioff_ma_per_um",),
    "ion_ioff_ratio": (),
    "ss": ("ss_mv_per_dec",),
    "dibl": ("dibl_gm_v_per_v",),
    "gm_max": ("gm_max_ms_per_um",),
    "gds": ("gds_ms_per_um",),
    "ron": ("ron_kohm_um",),
    "lambda_clm": ("lambda_per_v",),
}
METRIC_TO_CONCEPT = {
    "vth": "threshold_voltage",
    "vth_at_vd_0_05": "threshold_voltage",
    "vth_at_vd_1_5": "threshold_voltage",
    "ion": "on_current",
    "ioff": "off_current",
    "ss": "subthreshold_swing",
    "dibl": "dibl",
    "ron": "on_resistance",
    "gm_max": "transconductance",
    "gds": "output_conductance",
}
MECHANISM_TO_CONCEPTS = {
    "channel_resistance_reduction": ("channel_length", "on_current", "on_resistance"),
    "channel_resistance_increase": ("channel_length", "on_current", "on_resistance"),
    "drain_barrier_coupling_increase": ("short_channel_effect", "source_barrier", "dibl", "threshold_voltage", "off_current"),
    "drain_barrier_coupling_decrease": ("short_channel_effect", "source_barrier", "dibl", "threshold_voltage", "off_current"),
    "subthreshold_control_weakened": ("short_channel_effect", "subthreshold_swing", "off_current"),
    "subthreshold_control_strengthened": ("short_channel_effect", "subthreshold_swing", "off_current"),
    "saturation_control_weakened": ("short_channel_effect",),
    "saturation_control_strengthened": ("short_channel_effect",),
}
_NUMBER = re.compile(r"(?<![A-Za-z_])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


@dataclass(frozen=True)
class IVQuestionIntent:
    intent: str
    requested_metrics: tuple[str, ...] = ()
    requested_mechanisms: tuple[str, ...] = ()
    needs_current_result: bool = True
    needs_new_experiment: bool = False
    references_previous: bool = False
    answer_structure: str = "cause_and_effect"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IVAnalysisSnapshot:
    analysis_id: str
    curve_labels: tuple[str, ...]
    payload: dict[str, Any]
    automatic_explanation: dict[str, list[str]]
    selection_signature: tuple[Any, ...] = ()


@dataclass(frozen=True)
class IVChatResponse:
    answer: str
    source: str
    intent: IVQuestionIntent | None = None
    used_evidence_ids: tuple[str, ...] = ()
    suggested_followup: str | None = None
    needs_new_experiment: bool = False
    diagnostic: dict[str, Any] = field(default_factory=dict)
    pipeline_stage: str | None = None
    intent_checkpoint: dict[str, Any] = field(default_factory=dict)



def _with_model_caution(answer: str, intent: IVQuestionIntent) -> str:
    """Append the model-limitation caution when the answer leans on predicted
    results.

    The analysis path adds this in code rather than asking the provider for it
    (iv_renderer.py, ``policy["include_model_limitation"]``), so it is always
    present. Free-form answers are held to the same standard: a caveat the
    model may or may not remember to write is not a caveat. Answers that do
    not touch the current results — a definition, an out-of-scope reply — say
    nothing about predicted numbers and get no caution.
    """
    if not intent.needs_current_result:
        return answer
    caution = IV_TEMPLATES["caution.model"]
    if caution.rstrip(".") in answer:
        return answer
    return f"{answer}\n\n{caution}"


def _canonical_metrics(values: Any) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise ValueError("invalid_iv_intent_metrics")
    result = []
    for value in values:
        name = str(value).strip().lower()
        name = METRIC_ALIASES.get(name, name)
        if name not in KNOWN_METRICS:
            raise ValueError("unknown_iv_intent_metric")
        if name not in result:
            result.append(name)
    return tuple(result)


def validate_iv_intent(
    data: Any,
    available_mechanisms: set[str],
    *,
    question: str = "",
) -> IVQuestionIntent:
    if not isinstance(data, dict):
        raise ValueError("invalid_iv_intent")
    intent = str(data.get("intent", ""))
    structure = str(data.get("answer_structure", ""))
    mechanisms = data.get("requested_mechanisms", [])
    if (
        intent not in IV_CHAT_INTENTS
        or structure not in IV_CHAT_STRUCTURES
        or not isinstance(mechanisms, (list, tuple))
    ):
        raise ValueError("invalid_iv_intent_content")
    requested_mechanisms = tuple(dict.fromkeys(str(item) for item in mechanisms))
    if not set(requested_mechanisms).issubset(available_mechanisms):
        raise ValueError("unknown_iv_mechanism")
    flags = (
        data.get("needs_current_result"),
        data.get("needs_new_experiment"),
        data.get("references_previous"),
    )
    if any(not isinstance(item, bool) for item in flags):
        raise ValueError("invalid_iv_intent_flags")
    if intent in {"hypothetical", "new_experiment"} and not flags[1]:
        raise ValueError("iv_new_experiment_flag_required")
    if intent == "out_of_scope" and flags[0]:
        raise ValueError("iv_out_of_scope_uses_result")
    lowered_question = question.lower()
    current_cues = (
        "이번 결과", "현재 결과", "curve", "곡선", "비교",
        "증가", "감소", "변화", "달라", "커졌", "작아졌",
        "높아졌", "낮아졌", "늘어", "줄어", "악화", "개선",
    )
    experiment_cues = (
        "추가해", "추가할", "바꾸면", "바꾼", "변경하면",
        "변경할", "새 curve", "새로운 curve", "로 하면",
        "설정하면", "일 때는",
    )
    if (
        intent != "out_of_scope"
        and any(cue in lowered_question for cue in current_cues)
        and not flags[0]
    ):
        raise ValueError("iv_current_result_cue_mismatch")
    if any(cue in lowered_question for cue in experiment_cues) and not flags[1]:
        raise ValueError("iv_experiment_cue_mismatch")
    return IVQuestionIntent(
        intent=intent,
        requested_metrics=_canonical_metrics(data.get("requested_metrics", [])),
        requested_mechanisms=requested_mechanisms,
        needs_current_result=flags[0],
        needs_new_experiment=flags[1],
        references_previous=flags[2],
        answer_structure=structure,
    )


def _intent_prompt(payload: dict[str, Any]) -> tuple[str, str]:
    # 허용값 목록은 검증에 쓰는 상수에서 그대로 만든다. 예전에는 프롬프트에
    # 손으로 적어둔 목록과 검증 상수가 따로 놀았고, answer_structure는 아예
    # 적히지 않아 모델이 목록에 없는 값(value_only 등)을 지어내 매번
    # invalid_iv_intent_content로 거부됐다.
    intents = ", ".join(sorted(IV_CHAT_INTENTS))
    structures = ", ".join(sorted(IV_CHAT_STRUCTURES))
    system = f"""당신은 MOSFET I-V 분석 질문 해석기다.
질문의 의미만 분류하고 답변하지 않는다. 제공된 metric과 mechanism 이름만 쓴다.
intent는 {intents} 중 하나다.
answer_structure는 {structures} 중 하나다.
현재 보이는 결과의 이유·비교·수치를 묻는 질문은
needs_current_result=true다. 새로운 조건 추가·변경 요청은 needs_new_experiment=true다.
응답은 intent, requested_metrics, requested_mechanisms, needs_current_result,
needs_new_experiment, references_previous, answer_structure만 가진 JSON object다."""
    return system, (
        "<IV_QUESTION_CONTEXT>\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + "\n</IV_QUESTION_CONTEXT>"
    )


def _answer_prompt(payload: dict[str, Any]) -> tuple[str, str]:
    system = """당신은 반도체 소자 학습용 I-V 분석 튜터다.
Python이 검증한 context_pack만 근거로 자연스럽고 충분한 한국어 답변을 작성한다.
수치와 변화 방향을 새로 계산하거나 만들지 않는다. context_pack에 없는 숫자는
일반 상식이나 이론 상수(예: 이론적 SS 하한, 상온 온도)라도 쓰지 않는다.
비교나 평가가 필요하면 숫자 없이 서술한다. current_result_facts는 현재
모델 결과이고 theory_facts는 일반 물리 이론이므로 둘을 명확하게 구분한다.
통제된 단일 파라미터 비교의 mechanism_chains는 관찰과 방향이 일치한 경로다.
원인→물리 과정→관찰 지표→성능 의미 순서로 연결하되, 단순 수치 나열로 끝내지 않는다.
여러 parameter가 함께 바뀐 경우 개별 기여를 단정하지 않는다. 가상 조건이나
추가 Curve 요청은 현재 확인된 결과처럼 말하지 않고 새 계산이 필요하다고 밝힌다.
comparison_focus는 기존 Comparison Plan에서 허용된 근거를 좁힌 결과다. 지정된
subject와 comparison 밖의 결과를 섞지 않으며 original_plan_claim_level보다 강한
주장으로 승격하지 않는다.
evidence ID는 used_evidence_ids JSON 필드에만 넣고 answer 본문에는 절대 노출하지 않는다.
used_evidence_ids에는 context_pack의 allowed_evidence_ids에 있는 ID만 넣는다.
현재 결과를 근거로 답할 때는 used_evidence_ids를 비워 두지 않되, 정의나 일반
이론만 묻는 질문처럼 인용할 근거가 없으면 빈 배열로 둔다.
응답은 answer, used_evidence_ids, needs_new_experiment, suggested_followup만 가진 JSON object다."""
    return system, (
        "<GROUNDED_IV_QUESTION>\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + "\n</GROUNDED_IV_QUESTION>"
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


def validate_iv_answer(
    data: Any,
    *,
    intent: IVQuestionIntent,
    context_pack: dict[str, Any],
    question: str,
) -> IVChatResponse:
    if not isinstance(data, dict) or set(data) != {
        "answer", "used_evidence_ids", "needs_new_experiment", "suggested_followup",
    }:
        raise ValueError("invalid_iv_answer_keys")
    answer = normalize_public_text(data.get("answer", ""))
    if not answer or len(answer) > 2600:
        raise ValueError("invalid_iv_answer_content")
    validate_public_answer_text(answer)
    used = data.get("used_evidence_ids")
    if not isinstance(used, list) or any(not isinstance(item, str) for item in used):
        raise ValueError("invalid_iv_answer_evidence")
    used_ids = tuple(dict.fromkeys(used))
    allowed_ids = set(context_pack.get("allowed_evidence_ids", []))
    if not set(used_ids).issubset(allowed_ids):
        raise ValueError("unknown_iv_answer_evidence")
    needs_new = data.get("needs_new_experiment")
    if not isinstance(needs_new, bool) or needs_new != intent.needs_new_experiment:
        raise ValueError("iv_answer_experiment_flag_mismatch")
    followup_value = data.get("suggested_followup")
    followup = normalize_public_text(followup_value) if followup_value is not None else None
    if followup == "":
        followup = None
    if followup and len(followup) > 400:
        raise ValueError("invalid_iv_followup")
    if followup:
        validate_public_answer_text(followup)
    validate_focused_claim_text(
        answer,
        context_pack,
        error_code="iv_answer_exceeds_comparison_claim_level",
    )
    allowed_numbers = _collect_numbers(context_pack) | _collect_numbers(question)
    for token in _NUMBER.findall(answer + " " + (followup or "")):
        number = float(token)
        if not any(
            math.isclose(number, allowed, rel_tol=.015, abs_tol=.015)
            for allowed in allowed_numbers
        ):
            raise ValueError("ungrounded_iv_answer_number")
    if intent.needs_current_result and not used_ids:
        raise ValueError("current_iv_answer_requires_evidence")
    quality = validate_answer_quality(
        domain="iv",
        question=question,
        answer=answer,
        route=intent.intent,
        uses_current_result=intent.needs_current_result,
        needs_new_experiment=needs_new,
        evidence_ids=used_ids,
        requested_terms=(
            *intent.requested_metrics,
            *intent.requested_mechanisms,
        ),
        suggested_followup=followup,
    )
    return IVChatResponse(
        answer=answer,
        source="external_llm",
        intent=intent,
        used_evidence_ids=used_ids,
        suggested_followup=followup,
        needs_new_experiment=needs_new,
        diagnostic={"quality_report": quality.to_dict()},
    )


def _compact_evidence(item: dict[str, Any]) -> dict[str, Any]:
    data = item.get("data", {})
    compact_data = {
        key: data.get(key)
        for key in (
            "baseline", "candidate", "absolute_difference",
            "percent_difference", "decade_difference", "value", "unit",
        )
        if data.get(key) is not None
    }
    return {
        "evidence_id": item.get("evidence_id"),
        "quantity": item.get("quantity"),
        "observation": item.get("observation"),
        "assessment": item.get("assessment"),
        "magnitude": item.get("magnitude_class"),
        "confidence": item.get("confidence"),
        "data": compact_data,
    }


def _metric_matches(requested: set[str], quantity: str) -> bool:
    if not requested:
        return True
    if "vth" in requested and quantity.startswith("vth_"):
        return True
    return quantity in requested


def _concept_ids(intent: IVQuestionIntent, mechanisms: list[dict[str, Any]]) -> tuple[str, ...]:
    result = [
        METRIC_TO_CONCEPT[name]
        for name in intent.requested_metrics
        if name in METRIC_TO_CONCEPT
    ]
    for item in mechanisms:
        result.extend(MECHANISM_TO_CONCEPTS.get(str(item.get("mechanism_key")), ()))
    return tuple(dict.fromkeys(result))


def build_iv_context_pack(
    snapshot: IVAnalysisSnapshot,
    intent: IVQuestionIntent,
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
    compact_devices, fixed_conditions = compact_device_conditions(
        payload, focus,
    )
    subject_names = {
        str(item.get("subject_id")): str(
            item.get("display_name") or item.get("subject_id")
        )
        for item in payload.get("subjects", [])
    }
    requested = set(intent.requested_metrics)
    all_chains = [
        item for item in
        (payload.get("interpretation") or {}).get("mechanism_chains", [])
        if focus_allows_item(item, focus)
    ]
    if not intent.needs_current_result:
        mechanisms = []
    elif intent.requested_mechanisms:
        mechanisms = [
            item for item in all_chains
            if item.get("mechanism_key") in intent.requested_mechanisms
        ]
    elif requested:
        mechanisms = [
            item for item in all_chains
            if any(
                _metric_matches(requested, str(link.get("quantity", "")))
                for link in item.get("observed_metric_links", [])
            )
        ]
    else:
        mechanisms = all_chains
    mechanism_metrics = {
        str(link.get("quantity"))
        for item in mechanisms
        for link in item.get("observed_metric_links", [])
    }
    metric_filter = requested | mechanism_metrics
    evidence = [
        item for item in payload.get("evidence", [])
        if intent.needs_current_result
        and item.get("eligible_for_output", True)
        and item.get("evidence_type") in {"metric_value", "metric_change"}
        and focus_allows_item(item, focus)
        and (
            focus.focus_mode != "full_plan"
            or item.get("comparison_id") is None
            or str(item.get("comparison_id")) in context_comparison_ids
        )
        and _metric_matches(metric_filter, str(item.get("quantity", "")))
    ]
    evidence.sort(
        key=lambda item: (
            item.get("comparison_id") is None,
            -float(item.get("importance_score", 0)),
        )
    )
    evidence = evidence[:16]
    allowed_ids = tuple(
        str(item["evidence_id"]) for item in evidence if item.get("evidence_id")
    )
    clean_mechanisms = [
        {
            "mechanism_key": item.get("mechanism_key"),
            "parameter": item.get("parameter"),
            "change_direction": item.get("change_direction"),
            "target_concept": item.get("target_concept"),
            "process_steps": item.get("process_steps", []),
            "observed_metric_links": [
                {
                    "quantity": link.get("quantity"),
                    "observation": link.get("observation"),
                }
                for link in item.get("observed_metric_links", [])
                if link.get("evidence_id") in allowed_ids
            ],
            "support_level": item.get("support_level"),
            "claim_level": item.get("claim_level"),
        }
        for item in mechanisms[:6]
    ]
    definition_names = (
        set(requested)
        if intent.intent in {"define_extraction", "explain_metric"}
        else set()
    )
    definitions: dict[str, Any] = {}
    for name in definition_names:
        for extraction_name in METRIC_TO_EXTRACTION.get(name, ()):
            definition = PARAMETER_EXTRACTION_DEFINITIONS.get(extraction_name)
            if definition:
                definitions[extraction_name] = dict(definition)
    knowledge_base = load_theory_knowledge_base()
    theory = [
        concept.to_prompt_dict()
        for concept in knowledge_base.retrieve(
            _concept_ids(intent, mechanisms),
            limit=4,
        )
    ]
    pack = {
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
        "curve_labels": snapshot.curve_labels,
        "model_result_type": payload.get("context", {}).get("model_result_type", "prediction"),
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
                "baseline": subject_names.get(
                    str(item.get("baseline_subject_id")),
                    str(item.get("baseline_subject_id")),
                ),
                "candidate": subject_names.get(
                    str(item.get("candidate_subject_id")),
                    str(item.get("candidate_subject_id")),
                ),
                "changed_parameters": item.get("changed_parameters", []),
                "controlled_single_parameter": item.get(
                    "is_single_parameter_controlled_comparison", False
                ),
                "claim_level": item.get("effective_claim_level"),
            }
            for item in comparisons
        ] if intent.needs_current_result else [],
        "current_result_facts": [_compact_evidence(item) for item in evidence],
        "mechanism_chains": clean_mechanisms,
        "metric_definitions": definitions,
        "theory_facts": theory,
        "overall_assessment": [
            {
                "result_pattern": item.get("result_pattern"),
                "primary_gain": item.get("primary_gain"),
                "primary_loss": item.get("primary_loss"),
                "improved_areas": item.get("improved_areas", []),
                "degraded_areas": item.get("degraded_areas", []),
                "confidence": item.get("confidence"),
            }
            for item in (
                ((payload.get("interpretation") or {}).get("overall_assessment") or {})
                .get("comparison_results", [])
            )
            if focus_allows_item(item, focus)
            and (
                focus.focus_mode != "full_plan"
                or item.get("comparison_id") is None
                or str(item.get("comparison_id")) in context_comparison_ids
            )
        ] if intent.needs_current_result else [],
        "tradeoffs": [
            {
                "result_pattern": item.get("result_pattern"),
                "gain": item.get("gain"),
                "loss": item.get("loss"),
                "claim_level": item.get("claim_level"),
                "confidence": item.get("confidence"),
            }
            for item in [
                value
                for value in (payload.get("interpretation") or {}).get(
                    "observed_tradeoffs", []
                )
                if focus_allows_item(value, focus)
                and (
                    focus.focus_mode != "full_plan"
                    or value.get("comparison_id") is None
                    or str(value.get("comparison_id"))
                    in context_comparison_ids
                )
            ][:3]
        ] if intent.needs_current_result else [],
        "warnings": [
            {
                "warning_type": item.get("warning_type"),
                "severity": item.get("severity"),
                "affected_quantities": item.get("affected_quantities", []),
            }
            for item in payload.get("warnings", [])
            if item.get("eligible_for_output", True)
        ][:4] if intent.needs_current_result else [],
        "allowed_evidence_ids": allowed_ids,
    }
    return pack


def _prompt_bytes(builder: Any, payload: dict[str, Any]) -> int:
    system, user = builder(payload)
    return len((system + user).encode("utf-8"))


class IVChatService:
    quality_domain = "iv"

    def __init__(self, provider: Any | None) -> None:
        self.provider = provider

    @staticmethod
    def build_snapshot(
        results: list[Any],
        configs: list[dict[str, str]],
        *,
        selection_signature: tuple[Any, ...] = (),
    ) -> IVAnalysisSnapshot:
        payload = build_curve_payload(results, configs).to_dict()
        automatic = validate_provider_response(
            MockExplanationProvider().generate("", "", payload)
        )
        return IVAnalysisSnapshot(
            analysis_id=str(payload["analysis_id"]),
            curve_labels=tuple(str(item[0]) for item in results),
            payload=payload,
            automatic_explanation=automatic,
            selection_signature=selection_signature,
        )

    @staticmethod
    def _failure_code(error: Exception) -> str:
        code = str(error)
        if code.startswith("provider_http_"):
            return "external_http_" + code.removeprefix("provider_http_")
        if code == "provider_network_error":
            return "external_network_error"
        if isinstance(error, TimeoutError):
            return "external_timeout"
        if isinstance(error, ValueError):
            return "external_validation_failed"
        return "external_request_failed"

    def _call(
        self,
        builder: Any,
        payload: dict[str, Any],
        validator: Any,
        *,
        stage: str,
    ) -> tuple[Any | None, dict[str, Any], str | None]:
        if self.provider is None:
            return None, {
                "stage": stage,
                "category": "provider_unavailable",
                "message": "GROQ_API_KEY가 설정되지 않았습니다.",
            }, "provider_unavailable"
        system, user = builder(payload)
        request_bytes = len((system + user).encode("utf-8"))
        provider_calls: list[dict[str, Any]] = []

        def generate(
            active_system: str,
            failure_stage: str,
        ) -> Any:
            try:
                return self.provider.generate(active_system, user, payload)
            finally:
                value = consume_provider_diagnostic(
                    self.provider, stage=failure_stage,
                )
                if value:
                    provider_calls.append(value)

        def diagnostic(error: Exception, failure_stage: str) -> dict[str, Any]:
            if isinstance(error, ProviderHTTPError):
                value = error.diagnostic()
            else:
                value = {
                    "category": "response_validation" if isinstance(error, ValueError) else "provider",
                    "message": str(error)[:1200],
                    "request_bytes": request_bytes,
                    "model": str(getattr(self.provider, "model", "unknown")),
                }
            value["stage"] = failure_stage
            if provider_calls:
                value["provider_calls"] = list(provider_calls)
            return value

        first_raw = None
        try:
            first_raw = generate(system, stage)
            result = validator(first_raw)
            return result, {"provider_calls": provider_calls}, None
        except ValueError as first_error:
            repair_system = (
                system
                + "\n이전 JSON 응답이 로컬 검증에 실패했다. 검증 코드: "
                + str(first_error)
                + ". 같은 근거만 사용해 전체 JSON을 한 번 다시 생성하라."
            )
            repair_raw = None
            try:
                repair_raw = generate(repair_system, stage + "_repair")
                return validator(repair_raw), {
                    "provider_calls": provider_calls
                }, None
            except Exception as error:
                value = diagnostic(error, stage + "_repair")
                value["repair_trigger"] = str(first_error)
                value["quality_failure"] = (
                    build_validation_failure_record(
                        domain=self.quality_domain,
                        stage=stage + "_repair",
                        validation_code=str(first_error),
                        repair_validation_code=str(error),
                        question=str(payload.get("user_question", "")),
                        model=str(
                            getattr(self.provider, "model", "unknown")
                        ),
                        request_bytes=request_bytes,
                        provider_response=(
                            repair_raw
                            if repair_raw is not None
                            else first_raw
                        ),
                    ).to_dict()
                )
                return None, value, self._failure_code(error)
        except Exception as error:
            return None, diagnostic(error, stage), self._failure_code(error)

    @staticmethod
    def _retry_seconds(failure: str | None, diagnostic: dict[str, Any]) -> int | None:
        status = diagnostic.get("http_status")
        if status == 413 or failure == "external_http_413":
            return None
        if status == 429 or failure == "external_http_429":
            headers = diagnostic.get("headers", {})
            if (
                not diagnostic.get("intent_checkpoint_available")
                and isinstance(headers, dict)
            ):
                reset = str(headers.get("x-ratelimit-reset-tokens", "")).strip()
                match = re.fullmatch(
                    r"(?:(\d+(?:\.\d+)?)m)?(?:(\d+(?:\.\d+)?)s)?",
                    reset,
                )
                if match and any(match.groups()):
                    minutes = float(match.group(1) or 0)
                    seconds = float(match.group(2) or 0)
                    return max(1, math.ceil(minutes * 60 + seconds) + 1)
            retry = headers.get("retry-after") if isinstance(headers, dict) else None
            try:
                return max(1, math.ceil(float(retry)) + 1)
            except (TypeError, ValueError):
                match = re.search(
                    r"try again in\s+([0-9]+(?:\.[0-9]+)?)s",
                    str(diagnostic.get("message", "")),
                    flags=re.IGNORECASE,
                )
                return math.ceil(float(match.group(1))) + 1 if match else 60
        if failure == "external_timeout":
            return 5
        if failure == "external_network_error":
            return 10
        return 1

    @classmethod
    def _error_response(
        cls,
        failure: str | None,
        diagnostic: dict[str, Any],
        *,
        intent: IVQuestionIntent | None,
        checkpoint: bool,
    ) -> IVChatResponse:
        value = dict(diagnostic)
        value["intent_checkpoint_available"] = checkpoint
        wait = cls._retry_seconds(failure, value)
        if wait is not None:
            value["recommended_retry_after_seconds"] = wait
        stage = str(value.get("stage", ""))
        return IVChatResponse(
            answer=public_ai_failure_message(
                feature="I-V",
                failure=failure,
                diagnostic=value,
                retry_after_seconds=wait,
                checkpoint_preserved=checkpoint,
            ),
            source="external_error",
            intent=intent,
            needs_new_experiment=bool(
                intent and intent.needs_new_experiment
            ),
            diagnostic=value,
            pipeline_stage=stage,
            intent_checkpoint=intent.to_dict() if checkpoint and intent else {},
        )

    def answer(
        self,
        snapshot: IVAnalysisSnapshot,
        question: str,
        *,
        history: list[dict[str, Any]] | None = None,
        intent_checkpoint: dict[str, Any] | None = None,
    ) -> IVChatResponse:
        clean_question = " ".join(str(question).split())
        if not clean_question or len(clean_question) > 800:
            raise ValueError("invalid_iv_question")
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
            return IVChatResponse(
                answer=focus_clarification_text(snapshot.payload, focus),
                source="local_router",
                intent=IVQuestionIntent(
                    intent="clarify",
                    needs_current_result=False,
                    answer_structure="concise",
                ),
                diagnostic={"comparison_focus": focus.to_dict()},
            )
        mechanisms = {
            str(item.get("mechanism_key"))
            for item in (snapshot.payload.get("interpretation") or {}).get("mechanism_chains", [])
        }
        provider_calls: list[dict[str, Any]] = []
        intent: IVQuestionIntent | None = None
        if intent_checkpoint:
            try:
                intent = validate_iv_intent(
                    intent_checkpoint, mechanisms, question=clean_question,
                )
            except ValueError:
                intent = None
        if intent is None:
            intent_payload = {
                "user_question": clean_question,
                "curve_labels": snapshot.curve_labels,
                "available_metrics": sorted(KNOWN_METRICS),
                "available_mechanisms": sorted(mechanisms),
                "current_parameter_changes": [
                    item.get("changed_parameters", [])
                    for item in snapshot.payload.get("comparisons", [])
                ][:3],
                "comparison_plan": snapshot.payload.get(
                    "comparison_plan", {}
                ),
                "resolved_comparison_focus": focus.to_dict(),
                "recent_conversation": history,
            }
            intent, diagnostic, failure = self._call(
                _intent_prompt,
                intent_payload,
                lambda data: validate_iv_intent(
                    data, mechanisms, question=clean_question,
                ),
                stage="iv_intent_interpretation",
            )
            if intent is None:
                return self._error_response(
                    failure, diagnostic, intent=None, checkpoint=False,
                )
            provider_calls.extend(diagnostic.get("provider_calls", ()))
        context_pack = build_iv_context_pack(snapshot, intent, focus)
        answer_payload = {
            "user_question": clean_question,
            "interpreted_intent": intent.to_dict(),
            "recent_conversation": history if intent.references_previous else [],
            "context_pack": context_pack,
        }
        request_size = _prompt_bytes(_answer_prompt, answer_payload)
        if request_size > IV_CHAT_CONTEXT_BYTE_BUDGET:
            # Preserve current facts and mechanisms; optional related theory is
            # reduced before the provider call.
            context_pack["theory_facts"] = context_pack.get("theory_facts", [])[:3]
            context_pack["warnings"] = context_pack.get("warnings", [])[:2]
            answer_payload["context_pack"] = context_pack
        if _prompt_bytes(_answer_prompt, answer_payload) > IV_CHAT_CONTEXT_BYTE_BUDGET:
            context_pack["current_result_facts"] = context_pack.get(
                "current_result_facts", []
            )[:10]
            context_pack["allowed_evidence_ids"] = tuple(
                str(item["evidence_id"])
                for item in context_pack["current_result_facts"]
                if item.get("evidence_id")
            )
            context_pack["mechanism_chains"] = context_pack.get(
                "mechanism_chains", []
            )[:4]
            context_pack["theory_facts"] = context_pack.get(
                "theory_facts", []
            )[:2]
            answer_payload["recent_conversation"] = []
            answer_payload["context_pack"] = context_pack
        response, diagnostic, failure = self._call(
            _answer_prompt,
            answer_payload,
            lambda data: validate_iv_answer(
                data,
                intent=intent,
                context_pack=context_pack,
                question=clean_question,
            ),
            stage="iv_answer_generation",
        )
        if response is None:
            if provider_calls:
                diagnostic = dict(diagnostic)
                diagnostic["provider_calls"] = [
                    *provider_calls,
                    *diagnostic.get("provider_calls", ()),
                ]
            return self._error_response(
                failure, diagnostic, intent=intent, checkpoint=True,
            )
        provider_calls.extend(diagnostic.get("provider_calls", ()))
        response_diagnostic = dict(response.diagnostic)
        response_diagnostic["comparison_focus"] = focus.to_dict()
        return replace(
            response,
            answer=_with_model_caution(response.answer, intent),
            diagnostic={
                **response_diagnostic,
                "provider_calls": tuple(provider_calls),
            },
        )
