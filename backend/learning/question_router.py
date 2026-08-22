from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .analysis_schemas import LearningAnalysisContext
from .intent_interpreter import QuestionIntent
from .schemas import TopicConfig


QUESTION_TYPES = {
    "current_result",
    "case_theory",
    "adjacent_theory",
    "hypothetical",
    "new_experiment",
    "out_of_scope",
}
RELEVANCE_LEVELS = {"direct", "related", "domain_adjacent", "unrelated"}


@dataclass(frozen=True)
class QuestionRoute:
    question_type: str
    relevance_to_case: str
    matched_concepts: tuple[str, ...] = ()
    uses_current_result: bool = False
    needs_clarification: bool = False
    clarification_question: str | None = None
    needs_new_experiment: bool = False
    inherited_context: bool = False
    requested_action: str = "explain"
    answer_structure: str = "cause_and_effect"
    intent_source: str = "deterministic"
    aggregate_result: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_type": self.question_type,
            "relevance_to_case": self.relevance_to_case,
            "matched_concepts": list(self.matched_concepts),
            "uses_current_result": self.uses_current_result,
            "needs_clarification": self.needs_clarification,
            "clarification_question": self.clarification_question,
            "needs_new_experiment": self.needs_new_experiment,
            "inherited_context": self.inherited_context,
            "requested_action": self.requested_action,
            "answer_structure": self.answer_structure,
            "intent_source": self.intent_source,
            "aggregate_result": self.aggregate_result,
        }


DEFAULT_CONCEPT_ALIASES: dict[str, tuple[str, ...]] = {
    "channel_length": (
        "channel length", "채널 길이", "채널길이", "게이트 길이",
        "채널 줄", "채널이 줄", "채널을 줄", "채널 짧", "채널이 짧",
        "길이만",
    ),
    "short_channel_effect": ("sce", "short channel", "short-channel", "단채널", "짧은 채널"),
    "threshold_voltage": ("vth", "threshold voltage", "문턱전압", "문턱 전압", "임계전압"),
    "dibl": (
        "dibl", "drain induced barrier lowering", "드레인 유도 장벽",
        "drain 제어", "드레인 제어",
    ),
    "subthreshold_swing": ("subthreshold swing", "subthreshold slope", "ss", "서브스레시홀드"),
    "on_current": (
        "ion", "on current", "온전류", "구동 전류", "구동전류", "구동 이득",
    ),
    "off_current": ("ioff", "off current", "오프전류", "누설 전류", "누설전류"),
    "transconductance": ("gm", "transconductance", "트랜스컨덕턴스"),
    "output_conductance": ("gds", "output conductance", "출력 컨덕턴스"),
    "on_resistance": ("ron", "on resistance", "온저항"),
    "potential": ("potential", "전위", "포텐셜"),
    "electric_field": ("electric field", "field map", "전기장", "전계", "필드맵"),
    "source_barrier": ("source barrier", "소스 장벽", "source 장벽"),
    "pn_junction": ("pn junction", "p-n junction", "pn접합", "pn 접합", "접합"),
    "depletion_region": ("depletion", "공핍층", "공핍 영역", "공핍영역"),
    "punch_through": ("punch-through", "punch through", "펀치스루", "펀치 스루"),
    "body_doping": ("body doping", "bulk doping", "바디 도핑", "기판 도핑", "벌크 도핑"),
    "source_drain_doping": (
        "source/drain doping", "source drain doping", "s/d doping", "sd doping",
        "high sd", "low sd", "sd 농도",
        "소스 드레인 도핑", "소스/드레인 도핑", "source/drain 도핑",
    ),
    "oxide_thickness": (
        "oxide thickness", "gate oxide", "oxide", "tox",
        "산화막 두께", "옥사이드 두께",
    ),
    "ldd": ("ldd", "lightly doped drain"),
    "design_target": (
        "설계 목표", "목표 사양", "통합 설계", "최적 조건", "후보",
        "balanced", "drive", "leakage", "control",
    ),
}

_RESULT_CUES = (
    "이번", "현재", "이 실험", "실험은", "결과", "그래프",
    "curve", "field map", "여기서", "관찰",
)
_OBSERVATION_CUES = (
    "증가", "감소", "커", "작아", "높아", "낮아", "악화", "개선", "변했", "변화", "먼저",
)
_CHANGE_CUES = ("바꾸", "변경", "높이면", "낮추면", "늘리면", "줄이면", "짧아지", "길어지")
_EXPERIMENT_CUES = (
    "시뮬", "실험해", "실행해", "추가해", "추가해줄",
    "계산해", "예측해", "돌려",
)
_AGGREGATE_SCOPE_CUES = (
    "각 파라미터", "각 지표", "모든 파라미터", "모든 지표",
    "전체 파라미터", "전체 지표", "전체 결과",
)
_RESULT_MEANING_CUES = (
    "무슨 의미", "어떤 의미", "뭐를 의미", "무엇을 의미",
    "의미하는", "의미가 뭐", "정확히 뭐",
)
_METRIC_JUDGMENT_CUES = (
    "좋은 쪽", "좋은쪽", "나쁜 쪽", "나쁜쪽", "유리", "불리",
    "이득", "손실", "장점", "단점", "트레이드오프", "trade-off",
)
_CURRENT_SIMULATION_CUES = (
    "이번 시뮬레이션", "현재 시뮬레이션", "돌린 시뮬레이션",
    "이 시뮬레이션", "이번 실험", "현재 실험", "이 실험",
    "이번 결과", "현재 결과",
)
_FOLLOWUP_CUES = (
    "그럼", "그러면", "그건", "그게", "그거", "그 변화", "그 설명",
    "그 영향", "그 이유", "물리적 이유", "반대로",
)
_DOMAIN_TERMS = (
    "반도체", "mosfet", "mos", "transistor", "트랜지스터", "carrier", "캐리어",
    "electron", "hole", "전자", "정공", "drain", "source", "gate", "드레인", "소스", "게이트",
)
_NUMBER = re.compile(r"(?<![A-Za-z_])[-+]?(?:\d+(?:\.\d+)?|\.\d+)")


def _contains(text: str, candidates: Sequence[str]) -> bool:
    return any(candidate in text for candidate in candidates)


class TutorQuestionRouter:
    """Case-agnostic routing authority for free-form learning questions."""

    def __init__(
        self,
        concept_aliases: Mapping[str, Sequence[str]] | None = None,
    ) -> None:
        source = concept_aliases or DEFAULT_CONCEPT_ALIASES
        self.concept_aliases = {
            str(concept): tuple(str(alias).lower() for alias in aliases)
            for concept, aliases in source.items()
        }

    def _match_concepts(self, text: str) -> tuple[str, ...]:
        positioned = []
        for order, (concept, aliases) in enumerate(self.concept_aliases.items()):
            positions = [text.find(alias) for alias in aliases if alias in text]
            if positions:
                positioned.append((min(positions), order, concept))
        length_match = re.search(r"(?<![a-z])l(?![a-z])", text)
        if length_match and not any(item[2] == "channel_length" for item in positioned):
            positioned.append((length_match.start(), -1, "channel_length"))
        return tuple(item[2] for item in sorted(positioned))

    def _case_concepts(self, topic: TopicConfig) -> set[str]:
        joined = " ".join((
            topic.topic_id,
            topic.title,
            topic.description,
            *topic.learning_objectives,
            *topic.expected_concepts,
            *topic.required_outputs,
        )).lower()
        inferred = {
            concept
            for concept, aliases in self.concept_aliases.items()
            if any(
                marker in joined
                for marker in (concept, concept.replace("_", " "), *aliases)
            )
        }
        return {*topic.theory_concepts, *inferred}

    @staticmethod
    def _available_result_concepts(context: LearningAnalysisContext) -> set[str]:
        metric_mapping = {
            "vth_low": "threshold_voltage",
            "vth_high": "threshold_voltage",
            "ion": "on_current",
            "ioff": "off_current",
            "ss": "subthreshold_swing",
            "dibl": "dibl",
            "gm_max": "transconductance",
            "gds": "output_conductance",
            "ron": "on_resistance",
        }
        available = {
            concept
            for metric, concept in metric_mapping.items()
            if metric in context.electrical_changes
            and context.electrical_changes[metric].available
        }
        available.update(
            item.field_display
            for item in context.field_observations
            if item.field_display in {"potential", "electric_field"}
        )
        parameter_mapping = {
            "L": "channel_length",
            "B": "body_doping",
            "T": "oxide_thickness",
            "SD": "source_drain_doping",
            "LDD": "ldd",
        }
        changed = context.experiment.get("changed_parameters", ())
        if not changed and context.experiment.get("changed_parameter"):
            changed = (context.experiment["changed_parameter"],)
        available.update(
            parameter_mapping[item]
            for item in changed
            if item in parameter_mapping
        )
        if context.experiment.get("comparison_design") == "candidate_set":
            available.add("design_target")
        return available

    def _inherit_concepts(
        self,
        text: str,
        history: Sequence[Mapping[str, Any]],
    ) -> tuple[tuple[str, ...], str | None]:
        short_why = text.startswith("왜") and len(text) <= 20
        if not history or not (_contains(text, _FOLLOWUP_CUES) or short_why):
            return (), None
        previous = history[-1]
        concepts = tuple(str(item) for item in previous.get("matched_concepts", ()) if str(item))
        if not concepts:
            concepts = self._match_concepts(str(previous.get("question", "")).lower())
        previous_type = str(previous.get("question_type", "")) or None
        return concepts, previous_type

    @staticmethod
    def _ambiguity(text: str, concepts: set[str]) -> tuple[bool, str | None]:
        if "접합 길이" in text or "junction length" in text:
            return (
                True,
                "PN 접합에서 말한 ‘접합 길이’가 중성영역의 물리적 길이인지, "
                "공핍영역 폭인지 알려주세요.",
            )
        if ("길이" in text or "짧아지" in text or "길어지" in text) and not concepts.intersection(
            {"channel_length", "pn_junction", "depletion_region"}
        ):
            return True, "어떤 구조의 길이를 뜻하는지 알려주세요."
        if ("농도" in text or "도핑" in text) and not concepts.intersection(
            {"body_doping", "source_drain_doping", "ldd"}
        ):
            return True, "어느 영역의 도핑 농도를 뜻하는지 알려주세요."
        return False, None

    def route(
        self,
        question: str,
        topic: TopicConfig,
        context: LearningAnalysisContext,
        history: Sequence[Mapping[str, Any]] | None = None,
        interpreted_intent: QuestionIntent | None = None,
    ) -> QuestionRoute:
        text = str(question).strip().lower()
        if not text:
            raise ValueError("empty_user_text")
        matched = list(self._match_concepts(text))
        metric_concepts = {
            "vth_low": "threshold_voltage",
            "vth_high": "threshold_voltage",
            "vth": "threshold_voltage",
            "ion": "on_current",
            "ioff": "off_current",
            "ss": "subthreshold_swing",
            "dibl": "dibl",
            "gm_max": "transconductance",
            "gds": "output_conductance",
            "ron": "on_resistance",
        }
        if interpreted_intent is not None:
            matched.extend(interpreted_intent.target_concepts)
            matched.extend(
                metric_concepts[item]
                for item in interpreted_intent.requested_metrics
                if item in metric_concepts
            )
            matched = list(dict.fromkeys(matched))
        inherited, previous_type = self._inherit_concepts(text, history or ())
        inherited_context = False
        wants_previous = bool(
            interpreted_intent and interpreted_intent.references_previous
        )
        if not matched and inherited:
            matched.extend(inherited)
            inherited_context = True
        elif not matched and wants_previous and history:
            previous = history[-1]
            matched.extend(
                str(item)
                for item in previous.get("matched_concepts", ())
                if str(item)
            )
            inherited_context = bool(matched)
        concepts = set(matched)
        case_concepts = self._case_concepts(topic)
        available = self._available_result_concepts(context)
        direct = bool(concepts & case_concepts)
        domain_related = bool(concepts) or _contains(text, _DOMAIN_TERMS)
        needs_clarification, clarification = self._ambiguity(text, concepts)
        if interpreted_intent is not None and interpreted_intent.needs_clarification:
            needs_clarification = True
            clarification = (
                interpreted_intent.clarification_question or clarification
            )
        result_cue = _contains(text, _RESULT_CUES)
        observed_change = _contains(text, _OBSERVATION_CUES)
        change_request = _contains(text, _CHANGE_CUES)
        experiment_request = _contains(text, _EXPERIMENT_CUES)
        numeric_values = {float(item) for item in _NUMBER.findall(text)}
        known_conditions = {
            float(value)
            for values in (topic.baseline_conditions, topic.comparison_conditions)
            for value in values.values()
        }
        parameter_concepts = {
            "channel_length", "body_doping", "source_drain_doping",
            "oxide_thickness", "ldd",
        }
        new_numeric_condition = bool(
            numeric_values - known_conditions
            and concepts.intersection(parameter_concepts)
        )

        intent_type = interpreted_intent.intent if interpreted_intent else None
        requested_action = (
            interpreted_intent.requested_action
            if interpreted_intent
            else "explain"
        )
        answer_structure = (
            interpreted_intent.answer_structure
            if interpreted_intent
            else "cause_and_effect"
        )
        intent_source = (
            interpreted_intent.source if interpreted_intent else "deterministic"
        )
        intent_requests_result = bool(
            interpreted_intent
            and interpreted_intent.needs_current_result
            and intent_type in {
                "explain_current_result",
                "compare_results",
                "confirm_experiment_setup",
            }
        )
        aggregate_scope = _contains(text, _AGGREGATE_SCOPE_CUES)
        current_simulation = _contains(text, _CURRENT_SIMULATION_CUES)
        asks_result_meaning = current_simulation and _contains(
            text,
            _RESULT_MEANING_CUES,
        )
        asks_metric_judgment = (
            aggregate_scope
            and _contains(text, _METRIC_JUDGMENT_CUES)
        )
        aggregate_result = bool(
            available
            and (
                asks_result_meaning
                or asks_metric_judgment
                or (aggregate_scope and result_cue and observed_change)
            )
            and not new_numeric_condition
        )
        if (aggregate_result or intent_requests_result) and not matched:
            matched.extend(topic.theory_concepts)
            concepts = set(matched)
            direct = bool(concepts & case_concepts)
        if asks_metric_judgment or aggregate_scope:
            answer_structure = "parameter_by_parameter"
        domain_related = (
            domain_related
            or aggregate_result
            or intent_requests_result
        )
        current_result_reference = current_simulation and intent_requests_result

        if not domain_related and not inherited_context:
            return QuestionRoute(
                "out_of_scope",
                "unrelated",
                tuple(matched),
                needs_clarification=needs_clarification,
                clarification_question=clarification,
                requested_action=requested_action,
                answer_structure=answer_structure,
                intent_source=intent_source,
                aggregate_result=aggregate_result,
            )

        result_capable = bool(concepts & available) or bool(
            available and (aggregate_result or intent_requests_result)
        )
        if (
            not aggregate_result
            and not current_result_reference
            and (
                experiment_request
                or new_numeric_condition
                or intent_type in {"run_experiment", "add_experiment_condition"}
            )
        ):
            question_type = "new_experiment"
            relevance = "direct" if direct else "related"
            uses_result = False
            needs_new = True
        elif (
            (
                result_cue
                or (
                    result_capable
                    and observed_change
                    and not change_request
                )
                or (
                    inherited_context
                    and previous_type == "current_result"
                )
                or intent_type in {
                    "explain_current_result",
                    "compare_results",
                    "confirm_experiment_setup",
                }
                or aggregate_result
                or (
                    result_capable
                    and observed_change
                    and "channel_length" in concepts
                    and "channel_length" in available
                )
            )
            and result_capable
        ):
            question_type = "current_result"
            relevance = (
                "direct"
                if direct or aggregate_result or intent_requests_result
                else "related"
            )
            uses_result = True
            needs_new = False
        elif intent_type == "predict_change":
            question_type = "hypothetical"
            relevance = "direct" if direct else "domain_adjacent"
            uses_result = False
            needs_new = True
        elif intent_type == "explain_theory":
            question_type = "case_theory" if direct else "adjacent_theory"
            relevance = "direct" if direct else "domain_adjacent"
            uses_result = False
            needs_new = False
        elif change_request:
            if direct and concepts <= {"channel_length", "short_channel_effect"}:
                question_type = "case_theory"
                relevance = "direct"
                uses_result = False
                needs_new = False
            else:
                question_type = "hypothetical"
                relevance = "direct" if direct else "domain_adjacent"
                uses_result = False
                needs_new = True
        elif direct:
            question_type = "case_theory"
            relevance = "direct"
            uses_result = False
            needs_new = False
        else:
            question_type = "adjacent_theory"
            relevance = "domain_adjacent"
            uses_result = False
            needs_new = False

        return QuestionRoute(
            question_type=question_type,
            relevance_to_case=relevance,
            matched_concepts=tuple(dict.fromkeys(matched)),
            uses_current_result=uses_result,
            needs_clarification=needs_clarification,
            clarification_question=clarification,
            needs_new_experiment=needs_new,
            inherited_context=inherited_context,
            requested_action=requested_action,
            answer_structure=answer_structure,
            intent_source=intent_source,
            aggregate_result=aggregate_result,
        )
