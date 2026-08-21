from __future__ import annotations

from dataclasses import dataclass

from .analysis_schemas import LearningAnalysisContext
from .knowledge_base import TheoryConcept
from .knowledge_layers import (
    METRIC_PERFORMANCE_AREAS,
    metric_directional_implication,
    metric_preference,
)
from .question_router import QuestionRoute
from .schemas import TopicConfig


@dataclass(frozen=True)
class TheoryAnswerDraft:
    answer: str
    evidence_ids: tuple[str, ...] = ()
    theory_concepts: tuple[str, ...] = ()
    case_connection: str | None = None
    distinguishes_current_result: bool = False
    suggested_action_id: str | None = None


_METRICS_BY_CONCEPT: dict[str, tuple[tuple[str, str, str], ...]] = {
    "threshold_voltage": (("vth_high", "Vth (Vd=1.5 V)", "V"),),
    "dibl": (("dibl", "DIBL", "mV/V"),),
    "subthreshold_swing": (("ss", "SS", "mV/dec"),),
    "on_current": (("ion", "Ion", "mA/µm"),),
    "off_current": (("ioff", "Ioff", "mA/µm"),),
    "transconductance": (("gm_max", "gm max", "mS/µm"),),
    "output_conductance": (("gds", "gds", "mS/µm"),),
    "on_resistance": (("ron", "Ron", "kΩ·µm"),),
    "short_channel_effect": (
        ("dibl", "DIBL", "mV/V"),
        ("ss", "SS", "mV/dec"),
        ("ioff", "Ioff", "mA/µm"),
    ),
}
_DIRECTION = {
    "increase": "증가",
    "decrease": "감소",
    "stable": "큰 변화 없음",
    "unknown": "방향 불명확",
}
_METRIC_LABELS = {
    "vth": "Vth",
    "vth_low": "Vth (low Vd)",
    "vth_high": "Vth (high Vd)",
    "ion": "Ion",
    "ioff": "Ioff",
    "ion_ioff_ratio": "Ion/Ioff ratio",
    "ss": "SS",
    "dibl": "DIBL",
    "gm_max": "gm max",
    "gds": "gds",
    "ron": "Ron",
    "lambda_clm": "lambda",
}
_PERFORMANCE_AREA_LABELS = {
    "threshold_target": "목표 문턱전압과 구동·누설 균형",
    "drive_performance": "구동 성능",
    "off_state_leakage": "꺼짐 상태 누설",
    "current_separation": "켜짐·꺼짐 전류 분리",
    "subthreshold_control": "subthreshold 제어",
    "short_channel_control": "단채널·정전기적 제어",
    "gate_response": "Gate 제어에 대한 전류 응답",
    "output_saturation_control": "포화 영역 출력 제어",
    "conduction_loss": "켜짐 상태 전도 손실",
}
_DEFINITION_METRICS_BY_CONCEPT = {
    "threshold_voltage": ("vth_low", "vth_high"),
    "on_current": ("ion",),
    "off_current": ("ioff",),
    "subthreshold_swing": ("ss",),
    "dibl": ("dibl",),
    "transconductance": ("gm_max",),
    "output_conductance": ("gds", "lambda_clm"),
    "on_resistance": ("ron",),
}
_DEFINITION_CUES = (
    "언제", "어떤 조건", "무슨 조건", "어떻게 구", "어떻게 추출",
    "추출", "정의", "기준",
)


def _sentences(values: list[str], *, maximum: int) -> str:
    selected = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in selected:
            selected.append(normalized)
        if len(selected) >= maximum:
            break
    return " ".join(selected)


class GroundedTheoryAnswerer:
    """Compose local answers from atomic theory facts and verified analysis."""

    @staticmethod
    def _primary(
        route: QuestionRoute,
        concepts: tuple[TheoryConcept, ...],
    ) -> tuple[TheoryConcept, ...]:
        matched = set(route.matched_concepts)
        primary = tuple(item for item in concepts if item.concept_id in matched)
        return primary or concepts[:1]

    @staticmethod
    def _metric_evidence(
        route: QuestionRoute,
        context: LearningAnalysisContext,
    ) -> tuple[list[str], tuple[str, ...], tuple[str, ...]]:
        if not route.uses_current_result:
            return [], (), ()
        statements, evidence, implications = [], [], []
        requested_metrics: list[tuple[str, str, str]] = []
        if route.aggregate_result:
            requested_metrics.extend(
                (
                    metric_name,
                    _METRIC_LABELS.get(metric_name, metric_name),
                    change.unit or "",
                )
                for metric_name, change in context.electrical_changes.items()
            )
        else:
            for concept_id in route.matched_concepts:
                requested_metrics.extend(_METRICS_BY_CONCEPT.get(concept_id, ()))
        for metric_name, label, default_unit in dict.fromkeys(requested_metrics):
            change = context.electrical_changes.get(metric_name)
            if (
                not change
                or not change.available
                or change.before is None
                or change.after is None
                or not change.evidence_id
            ):
                continue
            direction = _DIRECTION.get(change.direction, change.direction)
            unit = f" {change.unit or default_unit}"
            statements.append(
                f"이번 결과에서 {label}: {change.before:.4g}에서 "
                f"{change.after:.4g}{unit}로 {direction}했습니다."
            )
            preference = metric_preference(metric_name)
            implication = metric_directional_implication(
                change.direction,
                preference,
            )
            area = _PERFORMANCE_AREA_LABELS.get(
                METRIC_PERFORMANCE_AREAS.get(metric_name, ""),
                "해당 전기적 특성",
            )
            if implication == "favorable_for_metric":
                statements[-1] += f" 이는 {area} 관점의 이득입니다."
            elif implication == "unfavorable_for_metric":
                statements[-1] += f" 이는 {area} 관점의 손실입니다."
            elif implication == "design_target_required":
                statements[-1] += (
                    f" {area}의 목표값이 없으면 유리하거나 불리하다고 "
                    "단정할 수 없습니다."
                )
            elif implication == "no_clear_gain_or_loss":
                statements[-1] += (
                    f" {area} 관점에서 뚜렷한 이득이나 손실로 보기 어렵습니다."
                )
            evidence.append(change.evidence_id)
            implications.append(implication)
            if (
                not route.aggregate_result
                and route.answer_structure != "parameter_by_parameter"
                and "design_target" not in route.matched_concepts
                and len(statements) >= 3
            ):
                break
        return (
            statements,
            tuple(dict.fromkeys(evidence)),
            tuple(implications),
        )

    @staticmethod
    def _field_evidence(
        route: QuestionRoute,
        context: LearningAnalysisContext,
    ) -> tuple[str | None, tuple[str, ...]]:
        requested = set(route.matched_concepts) & {"potential", "electric_field"}
        if not route.uses_current_result or not requested:
            return None, ()
        observations = [
            item
            for item in context.field_observations
            if item.field_display in requested and item.evidence_id
        ]
        if not observations:
            return None, ()
        displays = ", ".join(sorted({item.field_display for item in observations if item.field_display}))
        regions = ", ".join(sorted({item.region for item in observations if item.region})[:3])
        text = f"현재 {displays} 분석에서는 {regions or '주요 소자 영역'}을 관찰 근거로 사용합니다."
        return text, tuple(dict.fromkeys(item.evidence_id for item in observations[:4]))

    def compose(
        self,
        question: str,
        route: QuestionRoute,
        topic: TopicConfig,
        context: LearningAnalysisContext,
        concepts: tuple[TheoryConcept, ...],
        metric_definitions: dict[str, dict] | None = None,
    ) -> TheoryAnswerDraft:
        del topic
        primary = self._primary(route, concepts)
        theory_ids = tuple(item.concept_id for item in concepts)
        case_connection = _sentences(
            [item.case_connection for item in primary],
            maximum=2,
        ) or None
        if any(cue in question.lower() for cue in _DEFINITION_CUES):
            definitions = []
            available_definitions = metric_definitions or {}
            for concept_id in route.matched_concepts:
                for metric in _DEFINITION_METRICS_BY_CONCEPT.get(
                    concept_id,
                    (),
                ):
                    definition = available_definitions.get(metric, {})
                    explanation = str(
                        definition.get("learning_explanation", "")
                    ).strip()
                    if explanation:
                        definitions.append(explanation)
            if definitions:
                caveat = _sentences(
                    [value for item in primary for value in item.caveats],
                    maximum=1,
                )
                return TheoryAnswerDraft(
                    _sentences(
                        [*definitions, caveat],
                        maximum=4,
                    ),
                    theory_concepts=theory_ids,
                    case_connection=case_connection,
                )

        if route.question_type == "out_of_scope":
            return TheoryAnswerDraft(
                "현재 질문은 반도체 소자 학습 범위와 직접 연결하기 어렵습니다. "
                "소자 구조, 전기적 특성 또는 현재 시뮬레이션과 연결해 질문해 주세요.",
                theory_concepts=theory_ids,
                case_connection=case_connection,
            )

        summaries = _sentences([item.summary for item in primary], maximum=2)
        principles = _sentences(
            [value for item in primary for value in item.principles],
            maximum=2,
        )
        effects = _sentences(
            [value for item in primary for value in item.general_effects],
            maximum=3,
        )
        caveat = _sentences(
            [value for item in primary for value in item.caveats],
            maximum=1,
        )

        if route.question_type in {"hypothetical", "new_experiment"}:
            parts = ["일반적인 소자 물리 관점에서는", effects or principles or summaries]
            if caveat:
                parts.append(caveat)
            parts.append(
                "다만 이는 현재 700 nm와 300 nm 비교에서 직접 확인한 결과가 아닙니다. "
                "해당 변수만 변경한 추가 실험이 필요합니다."
            )
            if route.needs_clarification and route.clarification_question:
                parts.append(route.clarification_question)
            return TheoryAnswerDraft(
                _sentences(parts, maximum=6),
                theory_concepts=theory_ids,
                case_connection=case_connection,
                distinguishes_current_result=True,
            )

        (
            metric_statements,
            metric_evidence,
            metric_implications,
        ) = self._metric_evidence(route, context)
        field_statement, field_evidence = self._field_evidence(route, context)
        experiment = context.experiment
        experiment_statement = None
        experiment_evidence: tuple[str, ...] = ()
        if (
            route.uses_current_result
            and experiment.get("changed_parameter")
            and experiment.get("before") is not None
            and experiment.get("after") is not None
        ):
            unit = " nm" if experiment["changed_parameter"] in {"L", "T"} else ""
            experiment_statement = (
                f"현재 비교에서는 {experiment['changed_parameter']}을 "
                f"{float(experiment['before']):g}{unit}에서 "
                f"{float(experiment['after']):g}{unit}로 변경했습니다."
            )
            if (
                set(route.matched_concepts)
                & {
                    "channel_length",
                    "body_doping",
                    "oxide_thickness",
                    "ldd",
                }
                or not metric_evidence
            ):
                experiment_evidence = ("experiment:conditions",)
            if (
                route.aggregate_result
                or "이 실험" in question
                or "길이만" in question
                or "뭐만" in question
                or "무엇만" in question
            ):
                fixed = experiment.get("fixed_parameters", {})
                if isinstance(fixed, dict) and fixed:
                    experiment_statement += (
                        " "
                        + ", ".join(str(name) for name in fixed)
                        + "는 동일하게 고정했습니다."
                    )
        parts = [value for value in (experiment_statement, *metric_statements) if value]
        if field_statement:
            parts.append(field_statement)
        if route.aggregate_result:
            if {
                "favorable_for_metric",
                "unfavorable_for_metric",
            } <= set(metric_implications):
                parts.append(
                    "따라서 이번 결과는 한쪽으로만 좋아지거나 나빠진 것이 아니라, "
                    "서로 다른 성능 관점의 이득과 손실이 함께 나타난 trade-off입니다."
                )
            parts.append(
                "이 평가는 지표별 일반적 의미이며, 소자 전체가 설계 목표에 "
                "적합한지는 목표값과 허용 기준을 함께 확인해야 합니다."
            )
        parts.extend(value for value in (summaries, principles) if value)
        if route.question_type == "adjacent_theory" and case_connection:
            parts.append(case_connection)
        if caveat:
            parts.append(caveat)
        if route.needs_clarification and route.clarification_question:
            parts.append(route.clarification_question)
        if not parts:
            parts.append(
                "현재 검색된 반도체 이론만으로는 충분한 설명을 구성하기 어렵습니다."
            )
        evidence = tuple(dict.fromkeys((
            *experiment_evidence,
            *metric_evidence,
            *field_evidence,
        )))
        return TheoryAnswerDraft(
            _sentences(parts, maximum=20 if route.aggregate_result else 8),
            evidence_ids=evidence,
            theory_concepts=theory_ids,
            case_connection=case_connection,
            distinguishes_current_result=route.uses_current_result,
            suggested_action_id=(
                "observe_potential_map"
                if route.uses_current_result
                and bool({"dibl", "potential", "electric_field", "source_barrier"} & set(route.matched_concepts))
                else None
            ),
        )
