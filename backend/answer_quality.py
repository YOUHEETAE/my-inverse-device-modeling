from __future__ import annotations

import re
import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from backend.answer_contract import find_internal_references, normalize_public_text


_SENTENCE = re.compile(r"(?<=[.!?。！？])\s+|\n+")
_CAUSE_CUES = ("왜", "이유", "원인", "어떻게 이어", "연결", "메커니즘")
_DETAIL_CUES = ("자세히", "최대한", "한번에", "모두", "각 파라미터", "각 지표")
_CAUSAL_LANGUAGE = (
    "때문", "따라서", "결과적으로", "이로 인해", "이어", "영향",
    "장벽", "전계", "전위", "제어", "결합", "저항", "공핍",
)
_TERM_ALIASES = {
    "vth": ("vth", "문턱전압", "threshold"),
    "threshold_voltage": ("vth", "문턱전압", "threshold"),
    "ion": ("ion", "온 전류", "구동 전류", "on current"),
    "on_current": ("ion", "온 전류", "구동 전류", "on current"),
    "ioff": ("ioff", "오프 전류", "누설 전류", "off current"),
    "off_current": ("ioff", "오프 전류", "누설 전류", "off current"),
    "ss": ("ss", "subthreshold swing", "서브스레시홀드"),
    "subthreshold_swing": ("ss", "subthreshold swing", "서브스레시홀드"),
    "dibl": ("dibl", "drain-induced barrier lowering", "장벽 저하"),
    "ron": ("ron", "온 저항", "on resistance"),
    "on_resistance": ("ron", "온 저항", "on resistance"),
    "gm_max": ("gm", "트랜스컨덕턴스"),
    "transconductance": ("gm", "트랜스컨덕턴스"),
    "gds": ("gds", "출력 컨덕턴스"),
    "output_conductance": ("gds", "출력 컨덕턴스"),
    "channel_length": ("channel length", "채널 길이"),
    "short_channel_effect": ("short-channel", "short channel", "sce", "단채널"),
    "source_barrier": ("source barrier", "source 쪽 장벽", "소스 장벽", "주입 장벽"),
    "potential": ("potential", "전위"),
    "electric_field": ("electric field", "전계", "전기장"),
    "field_concentration": ("field concentration", "전계 집중", "전기장 집중"),
    "pn_junction": ("pn 접합", "p-n 접합"),
}
_HARD_FAILURES = {
    "answer_missing",
    "answer_repeats_sentence",
    "answer_echoes_question",
    "internal_reference_exposed",
    "result_evidence_boundary",
    "experiment_boundary",
    "followup_repeats_question",
}


@dataclass(frozen=True)
class AnswerQualityReport:
    domain: str
    passed: bool
    score: int
    checks: dict[str, bool]
    hard_failures: tuple[str, ...] = ()
    quality_warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationFailureRecord:
    """Privacy-safe failure metadata that can optionally become a replay fixture."""

    domain: str
    stage: str
    validation_code: str
    repair_validation_code: str | None
    question_fingerprint: str
    question_length: int
    model: str
    request_bytes: int | None
    response_keys: tuple[str, ...] = ()
    response_text_length: int = 0
    replay_payload: dict[str, Any] | None = None
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        json.dumps(value, ensure_ascii=False, allow_nan=False)
        return value


def build_validation_failure_record(
    *,
    domain: str,
    stage: str,
    validation_code: str,
    question: str,
    model: str,
    request_bytes: int | None = None,
    repair_validation_code: str | None = None,
    provider_response: Any = None,
    include_replay_content: bool = False,
) -> ValidationFailureRecord:
    clean_question = normalize_public_text(question)
    fingerprint = hashlib.sha256(
        clean_question.encode("utf-8")
    ).hexdigest()[:16]
    response_keys = (
        tuple(sorted(str(key) for key in provider_response))
        if isinstance(provider_response, dict)
        else ()
    )
    response_text = ""
    if isinstance(provider_response, dict):
        for name in ("answer", "suggested_followup", "next_learning_question"):
            if provider_response.get(name) is not None:
                response_text += " " + str(provider_response[name])
    replay_payload = None
    if include_replay_content:
        replay_payload = {
            "question": clean_question,
            "provider_response": provider_response,
        }
        json.dumps(replay_payload, ensure_ascii=False, allow_nan=False)
    return ValidationFailureRecord(
        domain=domain,
        stage=stage,
        validation_code=str(validation_code),
        repair_validation_code=(
            str(repair_validation_code)
            if repair_validation_code is not None
            else None
        ),
        question_fingerprint=fingerprint,
        question_length=len(clean_question),
        model=str(model),
        request_bytes=request_bytes,
        response_keys=response_keys,
        response_text_length=len(normalize_public_text(response_text)),
        replay_payload=replay_payload,
    )


def _sentences(text: str) -> tuple[str, ...]:
    return tuple(
        " ".join(item.lower().split())
        for item in _SENTENCE.split(text)
        if item.strip()
    )


def _mentions_term(text: str, term: str) -> bool:
    lowered = text.lower()
    aliases = _TERM_ALIASES.get(term.lower(), (term.replace("_", " "),))
    return any(alias.lower() in lowered for alias in aliases)


def audit_answer_quality(
    *,
    domain: str,
    question: str,
    answer: str,
    route: str,
    uses_current_result: bool,
    needs_new_experiment: bool,
    evidence_ids: Iterable[str] = (),
    requested_terms: Iterable[str] = (),
    suggested_followup: str | None = None,
) -> AnswerQualityReport:
    clean_question = normalize_public_text(question)
    clean_answer = normalize_public_text(answer)
    clean_followup = normalize_public_text(suggested_followup or "")
    sentences = _sentences(clean_answer)
    requested = tuple(dict.fromkeys(
        str(term).strip().lower()
        for term in requested_terms
        if str(term).strip()
    ))
    evidence = tuple(str(item) for item in evidence_ids if str(item))
    lowered_question = clean_question.lower()
    causal_requested = any(cue in lowered_question for cue in _CAUSE_CUES)
    detail_requested = any(cue in lowered_question for cue in _DETAIL_CUES)
    checks = {
        "answer_missing": bool(clean_answer),
        "answer_repeats_sentence": (
            bool(sentences) and len(sentences) == len(set(sentences))
        ),
        "answer_echoes_question": (
            clean_answer.lower().rstrip("?.!")
            != clean_question.lower().rstrip("?.!")
        ),
        "internal_reference_exposed": not find_internal_references(
            clean_answer + " " + clean_followup
        ),
        "result_evidence_boundary": (
            bool(evidence) if uses_current_result else not evidence
        ),
        "experiment_boundary": (
            needs_new_experiment
            if route in {"hypothetical", "new_experiment"}
            else True
        ),
        "followup_repeats_question": (
            not clean_followup
            or clean_followup.lower().rstrip("?.!")
            != clean_question.lower().rstrip("?.!")
        ),
        "requested_term_coverage": (
            not requested
            or any(_mentions_term(clean_answer, term) for term in requested)
        ),
        "causal_depth": (
            not causal_requested
            or (
                len(sentences) >= 2
                and any(term in clean_answer.lower() for term in _CAUSAL_LANGUAGE)
            )
        ),
        "requested_detail_depth": (
            not detail_requested
            or len(clean_answer) >= 140
            or len(sentences) >= 3
        ),
    }
    failures = tuple(name for name, passed in checks.items() if not passed)
    hard = tuple(name for name in failures if name in _HARD_FAILURES)
    warnings = tuple(name for name in failures if name not in _HARD_FAILURES)
    score = round(100 * sum(checks.values()) / max(1, len(checks)))
    return AnswerQualityReport(
        domain=domain,
        passed=not hard,
        score=score,
        checks=checks,
        hard_failures=hard,
        quality_warnings=warnings,
    )


def validate_answer_quality(**kwargs: Any) -> AnswerQualityReport:
    report = audit_answer_quality(**kwargs)
    if report.hard_failures:
        raise ValueError("answer_quality_" + report.hard_failures[0])
    return report
