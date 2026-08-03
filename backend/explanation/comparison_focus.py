from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import re
from typing import Any, Iterable

from .comparison_planner import PARAMETER_VALUE_KEYS


_NUMBER = re.compile(
    r"(?<![A-Za-z_])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
)
_COMPARE_CUES = (
    "비교", "대비", "차이", "둘", "두 조건", "두 curve",
    "두 곡선", "vs", "중에서",
)
_FULL_CUES = (
    "전체", "모든", "전반", "추세", "sweep", "스윕",
    "순서대로",
)
_PREVIOUS_CUES = (
    "그 둘", "그 두", "두 개", "둘 중", "앞의", "방금",
    "이 비교", "해당 비교", "그 조건",
)
_PARAMETER_ALIASES = {
    "channel_length": ("channel length", "채널 길이", "채널길이"),
    "oxide_thickness": ("oxide thickness", "tox", "산화막 두께"),
    "bulk_doping": ("bulk doping", "body doping", "벌크 도핑"),
    "source_drain_doping": (
        "source/drain doping", "source drain doping", "sd doping",
    ),
    "ldd_doping": ("ldd doping", "ldd 도핑"),
}
_STRONG_CAUSAL_CUES = (
    "때문에", "로 인해", "으로 인해", "유발", "결정했",
    "원인입니다", "원인이다", "기여도가 가장",
)
_LIMIT_CUES = (
    "단정할 수 없", "확정할 수 없", "분리할 수 없",
    "입증하지 않", "일반적으로", "가능성", "가설",
)


@dataclass(frozen=True)
class ComparisonFocus:
    focus_mode: str
    subject_ids: tuple[str, ...]
    comparison_ids: tuple[str, ...]
    source: str
    plan_analysis_mode: str
    original_plan_claim_level: str
    focused_claim_level: str
    requires_clarification: bool = False
    clarification_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _subjects(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item for item in payload.get("subjects", [])
        if item.get("subject_id")
    ]


def _explicit_label_subjects(
    question: str,
    subjects: list[dict[str, Any]],
) -> set[str]:
    lowered = question.lower()
    result: set[str] = set()
    for index, subject in enumerate(subjects, start=1):
        subject_id = str(subject["subject_id"])
        label = str(subject.get("display_name") or "").strip().lower()
        patterns = [
            rf"(?<!\d){index}\s*번째\s*(?:선택|조건|곡선)",
            rf"(?<!\d){index}\s*번\s*(?:조건|곡선)",
        ]
        curve_label = re.fullmatch(r"curve\s*(\d+)", label)
        if curve_label:
            patterns.append(
                rf"(?<![a-z0-9])curve\s*{curve_label.group(1)}(?!\d)"
            )
        elif label:
            patterns.append(re.escape(label))
        if any(re.search(pattern, lowered) for pattern in patterns):
            result.add(subject_id)
    if (
        ("curve" in lowered or "곡선" in lowered)
        and any(cue in lowered for cue in _COMPARE_CUES)
    ):
        label_numbers = {}
        for subject in subjects:
            match = re.fullmatch(
                r"curve\s*(\d+)",
                str(subject.get("display_name") or "").strip().lower(),
            )
            if match:
                label_numbers[int(match.group(1))] = str(
                    subject["subject_id"]
                )
        for token in _NUMBER.findall(question):
            value = float(token)
            if value.is_integer() and int(value) in label_numbers:
                result.add(label_numbers[int(value)])
    return result


def _numeric_subjects(
    question: str,
    payload: dict[str, Any],
    subjects: list[dict[str, Any]],
) -> set[str]:
    numbers = [float(value) for value in _NUMBER.findall(question)]
    if not numbers:
        return set()
    changed = set(
        (payload.get("comparison_plan") or {}).get(
            "changed_parameters", []
        )
    )
    if not changed:
        return set()
    parameter_keys = {
        "channel_length": "channel_length_nm",
        "oxide_thickness": "oxide_thickness_nm",
        "bulk_doping": "bulk_doping_cm3",
        "source_drain_doping": "source_drain_doping_cm3",
        "ldd_doping": "ldd_doping_cm3",
    }
    result: set[str] = set()
    matched_number_count = 0
    for number in numbers:
        matches = []
        for subject in subjects:
            parameters = subject.get("device_parameters", {})
            for parameter in changed:
                key = parameter_keys.get(parameter)
                value = parameters.get(key) if key else None
                if (
                    isinstance(value, (int, float))
                    and math.isclose(
                        float(value), number,
                        rel_tol=1e-9, abs_tol=1e-9,
                    )
                ):
                    matches.append(str(subject["subject_id"]))
                    break
        if matches:
            matched_number_count += 1
            result.update(matches)
    # A single bare number is often a bias or metric value. Accept it only
    # when the question also names a Curve/condition comparison.
    lowered = question.lower()
    if matched_number_count == 1 and not any(
        cue in lowered for cue in _COMPARE_CUES
    ):
        return set()
    return result


def _comparison_ids(
    payload: dict[str, Any],
    subject_ids: set[str],
) -> tuple[str, ...]:
    return tuple(
        str(item["comparison_id"])
        for item in payload.get("comparisons", [])
        if item.get("comparison_id")
        and set(item.get("subject_ids", [])) <= subject_ids
    )


def _claim_for_focus(
    payload: dict[str, Any],
    comparison_ids: tuple[str, ...],
    default: str,
) -> str:
    if len(comparison_ids) != 1:
        return default
    comparison = next(
        (
            item for item in payload.get("comparisons", [])
            if item.get("comparison_id") == comparison_ids[0]
        ),
        None,
    )
    return str(
        (comparison or {}).get("effective_claim_level") or default
    )


def _from_previous(
    history: Iterable[dict[str, Any]],
) -> ComparisonFocus | None:
    for item in reversed(list(history)):
        value = item.get("comparison_focus")
        if not isinstance(value, dict):
            continue
        try:
            return ComparisonFocus(
                focus_mode=str(value["focus_mode"]),
                subject_ids=tuple(value.get("subject_ids", [])),
                comparison_ids=tuple(value.get("comparison_ids", [])),
                source="previous_turn",
                plan_analysis_mode=str(value["plan_analysis_mode"]),
                original_plan_claim_level=str(
                    value["original_plan_claim_level"]
                ),
                focused_claim_level=str(value["focused_claim_level"]),
                requires_clarification=bool(
                    value.get("requires_clarification", False)
                ),
                clarification_reason=value.get("clarification_reason"),
            )
        except (KeyError, TypeError):
            continue
    return None


def resolve_comparison_focus(
    payload: dict[str, Any],
    question: str,
    *,
    history: Iterable[dict[str, Any]] = (),
) -> ComparisonFocus:
    subjects = _subjects(payload)
    all_subject_ids = tuple(str(item["subject_id"]) for item in subjects)
    plan = payload.get("comparison_plan") or {}
    plan_mode = str(plan.get("analysis_mode") or "unknown")
    plan_claim = str(
        plan.get("allowed_claim_level") or "descriptive_only"
    )
    lowered = " ".join(question.lower().split())
    explicit = _explicit_label_subjects(question, subjects)
    explicit.update(_numeric_subjects(question, payload, subjects))

    if not explicit and any(cue in lowered for cue in _PREVIOUS_CUES):
        previous = _from_previous(history)
        if previous and not previous.requires_clarification:
            return previous

    if any(cue in lowered for cue in _FULL_CUES) and not explicit:
        return ComparisonFocus(
            focus_mode="full_plan",
            subject_ids=all_subject_ids,
            comparison_ids=tuple(
                str(item["comparison_id"])
                for item in payload.get("comparisons", [])
                if item.get("comparison_id")
            ),
            source="question_requests_full_plan",
            plan_analysis_mode=plan_mode,
            original_plan_claim_level=plan_claim,
            focused_claim_level=plan_claim,
        )

    if explicit:
        ordered = tuple(
            subject_id for subject_id in all_subject_ids
            if subject_id in explicit
        )
        ids = _comparison_ids(payload, set(ordered))
        if len(ordered) == 1:
            if any(cue in lowered for cue in _COMPARE_CUES):
                return ComparisonFocus(
                    focus_mode="clarification",
                    subject_ids=ordered,
                    comparison_ids=(),
                    source="question_explicit_subject",
                    plan_analysis_mode=plan_mode,
                    original_plan_claim_level=plan_claim,
                    focused_claim_level=plan_claim,
                    requires_clarification=True,
                    clarification_reason="comparison_second_subject_missing",
                )
            mode = "single_subject"
        elif len(ordered) == 2:
            mode = "specific_pair"
        else:
            mode = (
                "full_plan"
                if len(ordered) == len(all_subject_ids)
                else "subject_group"
            )
        return ComparisonFocus(
            focus_mode=mode,
            subject_ids=ordered,
            comparison_ids=ids,
            source="question_explicit_subjects",
            plan_analysis_mode=plan_mode,
            original_plan_claim_level=plan_claim,
            focused_claim_level=_claim_for_focus(
                payload, ids, plan_claim
            ),
        )

    if (
        len(subjects) > 2
        and any(cue in lowered for cue in _COMPARE_CUES)
    ):
        return ComparisonFocus(
            focus_mode="clarification",
            subject_ids=(),
            comparison_ids=(),
            source="ambiguous_comparison_question",
            plan_analysis_mode=plan_mode,
            original_plan_claim_level=plan_claim,
            focused_claim_level=plan_claim,
            requires_clarification=True,
            clarification_reason="comparison_targets_ambiguous",
        )

    return ComparisonFocus(
        focus_mode=(
            "specific_pair" if len(subjects) == 2 else "full_plan"
        ),
        subject_ids=all_subject_ids,
        comparison_ids=tuple(
            str(item["comparison_id"])
            for item in payload.get("comparisons", [])
            if item.get("comparison_id")
        ),
        source="existing_plan_default",
        plan_analysis_mode=plan_mode,
        original_plan_claim_level=plan_claim,
        focused_claim_level=(
            _claim_for_focus(
                payload,
                tuple(
                    str(item["comparison_id"])
                    for item in payload.get("comparisons", [])
                    if item.get("comparison_id")
                ),
                plan_claim,
            )
        ),
    )


def focus_allows_item(
    item: dict[str, Any],
    focus: ComparisonFocus,
) -> bool:
    if focus.focus_mode == "full_plan":
        return True
    comparison_id = item.get("comparison_id")
    if comparison_id is not None:
        return str(comparison_id) in set(focus.comparison_ids)
    subject_ids = set(str(value) for value in item.get("subject_ids", []))
    return bool(subject_ids) and subject_ids <= set(focus.subject_ids)


def focused_comparisons(
    payload: dict[str, Any],
    focus: ComparisonFocus,
) -> list[dict[str, Any]]:
    if focus.focus_mode == "full_plan":
        return list(payload.get("comparisons", []))
    allowed = set(focus.comparison_ids)
    return [
        item for item in payload.get("comparisons", [])
        if item.get("comparison_id") in allowed
    ]


def compact_context_comparisons(
    payload: dict[str, Any],
    focus: ComparisonFocus,
    *,
    maximum: int = 4,
) -> list[dict[str, Any]]:
    """Keep the comparisons needed to explain a plan without all-pairs growth."""
    values = focused_comparisons(payload, focus)
    if focus.focus_mode != "full_plan":
        return values
    plan = payload.get("comparison_plan") or {}
    preferred_ids: list[str] = []
    sweep_ids = tuple(plan.get("sweep_subject_ids") or ())
    if sweep_ids:
        pair_lookup = {
            frozenset(str(value) for value in item.get("subject_ids", [])):
                str(item.get("comparison_id"))
            for item in values
            if item.get("comparison_id")
        }
        for left, right in zip(sweep_ids, sweep_ids[1:]):
            comparison_id = pair_lookup.get(frozenset((str(left), str(right))))
            if comparison_id:
                preferred_ids.append(comparison_id)
    if not sweep_ids:
        for comparison_id in (
            *(plan.get("selected_comparison_ids") or ()),
            *(plan.get("controlled_pair_ids") or ()),
        ):
            value = str(comparison_id)
            if value not in preferred_ids:
                preferred_ids.append(value)
    if not preferred_ids:
        return values[:maximum]
    selected = set(preferred_ids[:maximum])
    compact = [
        item for item in values
        if str(item.get("comparison_id")) in selected
    ]
    return compact or values[:maximum]


def compact_device_conditions(
    payload: dict[str, Any],
    focus: ComparisonFocus,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Factor shared parameters out instead of repeating them per Curve."""
    subjects = _subjects(payload)
    if focus.focus_mode != "full_plan":
        allowed = set(focus.subject_ids)
        subjects = [
            item for item in subjects
            if str(item.get("subject_id")) in allowed
        ]
    plan = payload.get("comparison_plan") or {}
    changed = tuple(str(value) for value in plan.get("changed_parameters", []))
    changed_keys = {
        PARAMETER_VALUE_KEYS[value]
        for value in changed if value in PARAMETER_VALUE_KEYS
    }
    if len(subjects) == 1 or not changed_keys:
        changed_keys = set(
            (subjects[0].get("device_parameters") or {}).keys()
        ) if subjects else set()
    devices = [
        {
            "display_name": item.get("display_name"),
            "varied_parameters": {
                key: value
                for key, value in (
                    item.get("device_parameters") or {}
                ).items()
                if key in changed_keys
            },
        }
        for item in subjects
    ]
    fixed_keys = {
        PARAMETER_VALUE_KEYS[value]
        for value in plan.get("fixed_parameters", [])
        if value in PARAMETER_VALUE_KEYS
    }
    first_parameters = (
        subjects[0].get("device_parameters") or {}
        if subjects else {}
    )
    fixed = {
        key: value for key, value in first_parameters.items()
        if key in fixed_keys
    }
    return devices, fixed


def focus_clarification_text(
    payload: dict[str, Any],
    focus: ComparisonFocus,
) -> str:
    names = [
        str(item.get("display_name") or item.get("subject_id"))
        for item in _subjects(payload)
    ]
    if focus.clarification_reason == "comparison_second_subject_missing":
        selected = next(
            (
                str(item.get("display_name") or item.get("subject_id"))
                for item in _subjects(payload)
                if item.get("subject_id") in focus.subject_ids
            ),
            "선택한 조건",
        )
        return (
            f"{selected}와 비교할 다른 조건을 지정해 주세요. "
            f"현재 선택 가능한 조건은 {', '.join(names)}입니다."
        )
    return (
        "비교 대상을 지정하면 해당 pair의 근거만 사용해 답하겠습니다. "
        f"현재 선택 가능한 조건은 {', '.join(names)}입니다. 예: "
        f"“{names[0]}과 {names[1]}만 비교해줘.”"
        if len(names) >= 2 else
        "현재는 비교할 두 번째 조건이 없습니다."
    )


def validate_focused_claim_text(
    answer: str,
    context_pack: dict[str, Any],
    *,
    error_code: str,
) -> None:
    """Reject direct single-parameter attribution in compound comparisons."""
    compound_parameters = {
        str(change.get("parameter"))
        for comparison in context_pack.get("comparisons", [])
        if len(comparison.get("changed_parameters", [])) > 1
        for change in comparison.get("changed_parameters", [])
    }
    if not compound_parameters:
        return
    aliases = tuple(
        alias
        for parameter in compound_parameters
        for alias in _PARAMETER_ALIASES.get(parameter, (parameter,))
    )
    for sentence in re.split(r"(?<=[.!?。！？])\s+|\n+", answer.lower()):
        if (
            any(alias in sentence for alias in aliases)
            and any(cue in sentence for cue in _STRONG_CAUSAL_CUES)
            and not any(cue in sentence for cue in _LIMIT_CUES)
        ):
            raise ValueError(error_code)
