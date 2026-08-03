from __future__ import annotations

import math
import re
from dataclasses import asdict, replace
from typing import Any, Callable

from backend.explanation.providers.config import ProviderMode, ProviderSettings
from backend.explanation.providers.external import (
    ExternalLLMProvider,
    ProviderHTTPError,
    Transport,
)
from backend.explanation.usage import consume_provider_diagnostic
from backend.answer_quality import build_validation_failure_record
from backend.public_presentation import public_ai_failure_message

from .analysis_schemas import LearningAnalysisContext
from .answer_evaluation import evaluate_structured_answer, parse_answer
from .knowledge_base import (
    TheoryConcept,
    TheoryKnowledgeBase,
    load_theory_knowledge_base,
)
from .intent_interpreter import QuestionIntent
from .dialogue_state import DialogueStateManager
from .followup_context import (
    compact_answer_plan,
    compact_dialogue_state,
    compact_history,
    compact_knowledge_layers,
    compact_simulation_facts,
    fit_followup_prompt_budget,
    select_definition_metrics,
    select_result_metrics,
    selected_evidence_ids,
)
from .knowledge_layers import LearningKnowledgeAssembler
from .model_answer import build_grounded_model_answer
from .question_router import QuestionRoute, TutorQuestionRouter
from .response_planner import LearningResponsePlan, build_response_plan
from .theory_answerer import GroundedTheoryAnswerer
from .prompts import (
    answer_evaluation as answer_evaluation_prompt,
    followup_qa as followup_prompt,
    learning_feedback as feedback_prompt,
    next_action_selection as next_action_prompt,
    session_summary as summary_prompt,
    question_intent as question_intent_prompt,
)
from .schemas import FollowupTurn, LearningSession, QuestionSpec, TopicConfig, UnderstandingLevel, utc_now
from .tutor_schemas import (
    AnswerEvaluation,
    FeedbackEvidence,
    FollowupResponse,
    LearningFeedback,
    LearningSessionSummary,
    NextActionDecision,
)
from .tutor_validation import (
    evidence_ids,
    sanitize_user_text,
    validate_evaluation,
    validate_feedback,
    validate_followup,
    validate_question_intent,
    validate_next_action,
    validate_summary,
)


CONCEPT_METRICS = {
    "ion_can_increase": "ion",
    "ioff_increases": "ioff",
    "vth_decreases": "vth_high",
    "dibl_increases": "dibl",
    "ss_increases": "ss",
}


class LearningLLMService:
    """Grounded learning-tutor operations with deterministic local fallbacks."""

    def __init__(
        self,
        provider: Any | None = None,
        question_router: TutorQuestionRouter | None = None,
        knowledge_base: TheoryKnowledgeBase | None = None,
        theory_answerer: GroundedTheoryAnswerer | None = None,
    ) -> None:
        self.provider = provider
        self.question_router = question_router or TutorQuestionRouter()
        self.knowledge_base = knowledge_base or load_theory_knowledge_base()
        self.theory_answerer = theory_answerer or GroundedTheoryAnswerer()
        self.last_provider_failure: str | None = None
        self.last_provider_failure_detail: str | None = None
        self.last_provider_diagnostic: dict[str, Any] = {}
        self.last_provider_call_diagnostics: tuple[dict[str, Any], ...] = ()
        self._provider_call_log: list[dict[str, Any]] = []

    def usage_checkpoint(self) -> int:
        """Return a marker used to measure a bounded learning operation."""
        return len(self._provider_call_log)

    def usage_since(self, checkpoint: int) -> tuple[dict[str, Any], ...]:
        start = max(0, min(int(checkpoint), len(self._provider_call_log)))
        return tuple(dict(item) for item in self._provider_call_log[start:])

    @classmethod
    def from_environment(cls, transport: Transport | None = None) -> "LearningLLMService":
        settings = ProviderSettings.from_environment(ProviderMode.EXTERNAL)
        try:
            return cls(ExternalLLMProvider(settings, transport))
        except RuntimeError:
            return cls(None)

    def _call(
        self,
        builder: Callable[[dict], tuple[str, str]],
        payload: dict,
        validator: Callable[[Any], Any],
        *,
        stage: str,
    ) -> Any | None:
        self.last_provider_failure = None
        self.last_provider_failure_detail = None
        self.last_provider_diagnostic = {}
        self.last_provider_call_diagnostics = ()
        if self.provider is None:
            return None
        system, user = builder(payload)
        request_bytes = len((system + user).encode("utf-8"))
        provider_calls: list[dict[str, Any]] = []

        def generate(active_system: str, active_stage: str) -> Any:
            try:
                return self.provider.generate(active_system, user, payload)
            finally:
                value = consume_provider_diagnostic(
                    self.provider, stage=active_stage,
                )
                if value:
                    provider_calls.append(value)
                    self._provider_call_log.append(dict(value))
                    self.last_provider_call_diagnostics = tuple(
                        provider_calls
                    )

        def record_failure(
            error: Exception,
            failure_stage: str,
            *,
            category: str | None = None,
        ) -> None:
            if isinstance(error, ProviderHTTPError):
                diagnostic = error.diagnostic()
            else:
                diagnostic = {
                    "category": category or "provider",
                    "message": str(error)[:1200],
                    "request_bytes": request_bytes,
                    "request_bytes_estimated": True,
                    "model": str(
                        getattr(self.provider, "model", "unknown")
                    ),
                }
            diagnostic["stage"] = failure_stage
            diagnostic["internal_code"] = self._provider_failure_code(error)
            self.last_provider_diagnostic = diagnostic
            self.last_provider_failure_detail = str(
                diagnostic.get("message") or str(error)
            )

        first_raw = None
        try:
            first_raw = generate(system, stage)
            return validator(first_raw)
        except ValueError as error:
            repair_system = (
                system
                + "\n이전 응답이 로컬 JSON 검증에 실패했다. 검증 코드: "
                + str(error)
                + ". 같은 근거만 사용해 전체 JSON을 한 번 다시 생성하라."
            )
            repair_raw = None
            try:
                repair_raw = generate(repair_system, f"{stage}_repair")
                return validator(repair_raw)
            except TimeoutError as repair_error:
                self.last_provider_failure = "external_timeout"
                record_failure(repair_error, f"{stage}_repair")
                self.last_provider_diagnostic["repair_trigger"] = str(error)
                return None
            except ValueError as repair_error:
                self.last_provider_failure = "external_validation_failed"
                record_failure(
                    repair_error,
                    f"{stage}_repair",
                    category="response_validation",
                )
                self.last_provider_diagnostic["repair_trigger"] = str(error)
                self.last_provider_diagnostic["quality_failure"] = (
                    build_validation_failure_record(
                        domain="case",
                        stage=f"{stage}_repair",
                        validation_code=str(error),
                        repair_validation_code=str(repair_error),
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
                return None
            except Exception as error:
                self.last_provider_failure = self._provider_failure_code(error)
                record_failure(error, f"{stage}_repair")
                self.last_provider_diagnostic["repair_trigger"] = str(error)
                return None
        except TimeoutError as error:
            self.last_provider_failure = "external_timeout"
            record_failure(error, stage)
            return None
        except Exception as error:
            self.last_provider_failure = self._provider_failure_code(error)
            record_failure(error, stage)
            return None

    @staticmethod
    def _provider_failure_code(error: Exception) -> str:
        code = str(error).strip()
        if code.startswith("provider_http_"):
            return "external_http_" + code.removeprefix("provider_http_")
        if code == "provider_network_error":
            return "external_network_error"
        if code == "provider_error":
            return "external_provider_error"
        return "external_request_failed"

    @staticmethod
    def _context_payload(context: LearningAnalysisContext) -> dict:
        data = context.to_dict()
        data["electrical_changes"] = {
            name: value for name, value in data["electrical_changes"].items() if value["available"]
        }
        return data

    @staticmethod
    def _question_payload(question: QuestionSpec) -> dict:
        data = asdict(question)
        # The model receives concepts, while correct option keys remain code authority.
        data.pop("correct_options", None)
        return data

    def evaluate_answer(
        self,
        topic: TopicConfig,
        question: QuestionSpec,
        raw_answer: Any,
        context: LearningAnalysisContext,
    ) -> AnswerEvaluation:
        selected, reason = parse_answer(raw_answer)
        if sum(len(item) for item in selected) + len(reason) > 2000:
            raise ValueError("answer_too_long")
        deterministic = evaluate_structured_answer(question, raw_answer)
        payload = {
            "learning_topic": {
                "topic_id": topic.topic_id,
                "learning_objectives": topic.learning_objectives,
                "expected_concepts": topic.expected_concepts,
                "common_misconceptions": topic.common_misconceptions,
            },
            "question": self._question_payload(question),
            "user_answer": {"selected": selected, "reason": reason},
            "deterministic_evaluation": deterministic.to_dict(),
            "simulation_facts": self._context_payload(context),
        }
        external = self._call(
            answer_evaluation_prompt.build_prompt,
            payload,
            lambda data: validate_evaluation(data, topic),
            stage="answer_evaluation",
        )
        if external is None:
            return deterministic
        correct = tuple(dict.fromkeys((*deterministic.correct_concepts, *external.correct_concepts)))
        question_expected = {
            concept
            for option in question.correct_options
            for concept in question.concepts_by_option.get(option, ())
        }
        missing = tuple(concept for concept in topic.expected_concepts if concept in question_expected and concept not in correct)
        misconceptions = tuple(dict.fromkeys((*deterministic.detected_misconceptions, *external.detected_misconceptions)))
        level = external.understanding_level
        if deterministic.understanding_level == "incorrect":
            level = "incorrect"
        elif deterministic.understanding_level == "partial" and level == "correct":
            level = "partial"
        return AnswerEvaluation(
            understanding_level=level,
            correct_concepts=correct,
            missing_concepts=missing,
            detected_misconceptions=misconceptions,
            unsupported_claims=tuple(dict.fromkeys((*deterministic.unsupported_claims, *external.unsupported_claims))),
            feedback_strategy=external.feedback_strategy,
            recommended_next_action="show_feedback",
            source="external_llm",
        )

    @staticmethod
    def _canonical_evidence(
        evaluation: AnswerEvaluation,
        context: LearningAnalysisContext,
    ) -> tuple[FeedbackEvidence, ...]:
        requested = [
            CONCEPT_METRICS[concept]
            for concept in (*evaluation.correct_concepts, *evaluation.missing_concepts)
            if concept in CONCEPT_METRICS
        ]
        requested.extend(("ion", "ioff", "dibl"))
        evidence = []
        for label in dict.fromkeys(requested):
            change = context.electrical_changes.get(label)
            if not change or not change.available or change.before is None or change.after is None:
                continue
            evidence.append(FeedbackEvidence(
                label, change.before, change.after, change.unit,
                change.direction, change.evidence_id,
            ))
            if len(evidence) == 5:
                break
        return tuple(evidence)

    @staticmethod
    def _local_feedback(
        topic: TopicConfig,
        evaluation: AnswerEvaluation,
        context: LearningAnalysisContext,
    ) -> LearningFeedback:
        evidence = LearningLLMService._canonical_evidence(evaluation, context)
        if evaluation.understanding_level == "correct":
            headline = "핵심 변화 방향을 올바르게 파악했습니다."
        elif evaluation.understanding_level == "partial":
            headline = "일부 변화는 맞지만 함께 확인할 특성이 남아 있습니다."
        else:
            headline = "그래프의 변화 방향을 다시 확인해보세요."
        positive = tuple(f"{concept} 개념을 확인했습니다." for concept in evaluation.correct_concepts)
        corrections = tuple(f"{concept} 개념을 결과와 다시 연결해보세요." for concept in evaluation.missing_concepts)
        if evaluation.detected_misconceptions:
            corrections += ("짧은 채널이 모든 특성을 개선하는 것은 아닙니다.",)
        has_gap = bool(
            evaluation.missing_concepts
            or evaluation.detected_misconceptions
            or evaluation.unsupported_claims
        )
        if not has_gap:
            curve_focus = "추가로 다시 확인할 Curve 위치 없음"
            field_focus = "추가로 다시 확인할 Field 위치 없음"
        elif topic.topic_id == "oxide_gate_control":
            curve_focus = (
                "log(Id)–Vg의 subthreshold 기울기와 선형 Id–Vg의 최대 dId/dVg를 "
                "SS·gm 추출값과 다시 연결해보세요."
            )
            field_focus = (
                "Gate/oxide/channel 인접 영역의 Potential과 Electric Field를 같은 "
                "color scale에서 다시 확인하세요."
            )
        else:
            curve_focus = (
                "log(Id)–Vg의 subthreshold 기울기, 두 Drain bias의 문턱 이동과 "
                "정의된 on/off bias 전류를 다시 확인하세요."
            )
            field_focus = (
                "채널 표면과 Source-side 장벽 방향에서 Potential·Electric Field가 "
                "어떻게 달라지는지 다시 확인하세요."
            )
        if topic.topic_id == "oxide_gate_control":
            summary = (
                "Oxide 두께 감소에 따른 Gate control 변화와 Ioff·oxide 전계의 "
                "trade-off를 분리해 판단해야 합니다."
            )
            next_question = "gm 증가와 SS 감소가 모두 Gate control과 연결되는 이유는 무엇인가요?"
        else:
            summary = (
                "채널 길이 감소에 따른 구동 성능 변화와 off-state/SCE 악화를 함께 "
                "판단해야 합니다."
            )
            next_question = "Ion 증가와 동시에 악화된 특성은 무엇인가요?"
        return LearningFeedback(
            headline=headline,
            model_answer=build_grounded_model_answer(topic, context),
            positive_feedback=positive,
            corrections=corrections,
            evidence=evidence,
            curve_focus=curve_focus,
            field_focus=field_focus,
            summary=summary,
            next_question=next_question,
            source="local",
        )

    def generate_feedback(
        self,
        topic: TopicConfig,
        evaluation: AnswerEvaluation,
        context: LearningAnalysisContext,
    ) -> LearningFeedback:
        evidence = self._canonical_evidence(evaluation, context)
        payload = {
            "learning_topic": {"title": topic.title, "learning_objectives": topic.learning_objectives},
            "evaluation": evaluation.to_dict(),
            "simulation_facts": self._context_payload(context),
            "server_evidence": [asdict(item) for item in evidence],
        }
        external = self._call(
            feedback_prompt.build_prompt,
            payload,
            validate_feedback,
            stage="learning_feedback",
        )
        if external is None:
            return self._local_feedback(topic, evaluation, context)
        return LearningFeedback(
            headline=external["headline"],
            model_answer=build_grounded_model_answer(topic, context),
            positive_feedback=external["positive_feedback"],
            corrections=external["corrections"],
            evidence=evidence,
            curve_focus=external["curve_focus"],
            field_focus=external["field_focus"],
            summary=external["summary"],
            next_question=external["next_question"],
            source="external_llm",
        )

    @staticmethod
    def _fallback_action(topic: TopicConfig, evaluation: AnswerEvaluation) -> NextActionDecision:
        allowed = {item.action_id: item for item in topic.allowed_next_actions}
        preferred = {
            "incorrect": "review_sce_theory",
            "uncertain": "retry_sce_prediction",
            "partial": "observe_potential_map",
            "correct": "observe_potential_map",
        }.get(evaluation.understanding_level)
        selected = allowed.get(preferred) or next(iter(allowed.values()))
        return NextActionDecision(selected.action_id, selected.description, "local")

    def select_local_next_action(
        self,
        topic: TopicConfig,
        evaluation: AnswerEvaluation,
    ) -> NextActionDecision:
        """Keep the saved curriculum decision without spending an LLM call."""
        return self._fallback_action(topic, evaluation)

    def select_next_action(
        self,
        topic: TopicConfig,
        evaluation: AnswerEvaluation,
        context: LearningAnalysisContext,
    ) -> NextActionDecision:
        payload = {
            "understanding_level": evaluation.understanding_level,
            "missing_concepts": evaluation.missing_concepts,
            "detected_misconceptions": evaluation.detected_misconceptions,
            "allowed_next_actions": [asdict(item) for item in topic.allowed_next_actions],
            "simulation_facts": self._context_payload(context),
        }
        return self._call(
            next_action_prompt.build_prompt,
            payload,
            lambda data: validate_next_action(data, topic),
            stage="next_action",
        ) or self._fallback_action(topic, evaluation)

    def summarize_session(
        self,
        topic: TopicConfig,
        evaluation: AnswerEvaluation,
        context: LearningAnalysisContext,
        next_action: NextActionDecision | None = None,
    ) -> LearningSessionSummary:
        payload = {
            "learning_topic": {"topic_id": topic.topic_id, "title": topic.title},
            "evaluation": evaluation.to_dict(),
            "next_action": asdict(next_action) if next_action else None,
            "simulation_facts": self._context_payload(context),
        }
        external = self._call(
            summary_prompt.build_prompt,
            payload,
            lambda data: validate_summary(data, topic),
            stage="session_summary",
        )
        if external is not None:
            return external
        return LearningSessionSummary(
            headline=f"{topic.title} 학습 요약",
            summary=(
                f"{topic.title}에서 설정한 비교 조건에 따른 소자 특성과 "
                "물리적 의미를 검토했습니다."
            ),
            understood_concepts=evaluation.correct_concepts,
            needs_review=evaluation.missing_concepts,
            detected_misconceptions=evaluation.detected_misconceptions,
            recommended_next_action=next_action.action_id if next_action else None,
            source="local",
        )

    @staticmethod
    def _routed_response(
        route: QuestionRoute,
        answer: str,
        *,
        evidence: tuple[str, ...] = (),
        distinguishes_current_result: bool = False,
        suggested_action_id: str | None = None,
        theory_concepts: tuple[str, ...] = (),
        case_connection: str | None = None,
    ) -> FollowupResponse:
        return FollowupResponse(
            question_type=route.question_type,
            answer=answer,
            evidence_ids=evidence,
            distinguishes_current_result=distinguishes_current_result,
            needs_new_experiment=route.needs_new_experiment,
            suggested_action_id=suggested_action_id,
            source="local",
            relevance_to_case=route.relevance_to_case,
            matched_concepts=route.matched_concepts,
            uses_current_result=route.uses_current_result,
            needs_clarification=route.needs_clarification,
            clarification_question=route.clarification_question,
            theory_concepts=theory_concepts,
            case_connection=case_connection,
            interpretation_source=route.intent_source,
        )

    @staticmethod
    def _recommended_retry_seconds(
        failure: str | None,
        diagnostic: dict[str, Any],
    ) -> int | None:
        status = diagnostic.get("http_status")
        if status == 413 or failure == "external_http_413":
            return None
        if status == 429 or failure == "external_http_429":
            headers = diagnostic.get("headers")
            if (
                not diagnostic.get("intent_checkpoint_available")
                and isinstance(headers, dict)
            ):
                reset_value = str(
                    headers.get("x-ratelimit-reset-tokens", "")
                )
                reset_match = re.fullmatch(
                    r"(?:(\d+(?:\.\d+)?)m)?"
                    r"(?:(\d+(?:\.\d+)?)s)?",
                    reset_value.strip(),
                )
                if reset_match and any(reset_match.groups()):
                    minutes = float(reset_match.group(1) or 0)
                    seconds = float(reset_match.group(2) or 0)
                    return max(
                        1,
                        math.ceil(minutes * 60 + seconds) + 1,
                    )
            retry_value = (
                headers.get("retry-after")
                if isinstance(headers, dict)
                else None
            )
            try:
                # One extra second avoids resubmitting exactly on the rolling
                # rate-limit boundary.
                return max(1, math.ceil(float(retry_value)) + 1)
            except (TypeError, ValueError):
                pass
            message = str(diagnostic.get("message", ""))
            match = re.search(
                r"try again in\s+([0-9]+(?:\.[0-9]+)?)s",
                message,
                flags=re.IGNORECASE,
            )
            if match:
                return max(1, math.ceil(float(match.group(1))) + 1)
            return 60
        if failure == "external_timeout":
            return 5
        if failure == "external_network_error":
            return 10
        if status in {500, 502, 503, 504}:
            return 10
        if failure == "external_validation_failed":
            return 1
        return 5

    @classmethod
    def _provider_failure_answer(
        cls,
        failure: str | None,
        diagnostic: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        value = dict(diagnostic)
        wait = cls._recommended_retry_seconds(failure, value)
        if wait is not None:
            value["recommended_retry_after_seconds"] = wait
        return public_ai_failure_message(
            feature="Case Study",
            failure=failure,
            diagnostic=value,
            retry_after_seconds=wait,
            checkpoint_preserved=bool(
                value.get("intent_checkpoint_available")
            ),
            state_preserved=True,
        ), value

    @classmethod
    def _provider_failure_followup(
        cls,
        route: QuestionRoute,
        intent: QuestionIntent | None,
        response_plan: LearningResponsePlan,
        *,
        failure: str | None,
        detail: str | None,
        diagnostics: tuple[dict[str, Any], ...],
        warnings: tuple[str, ...] = (),
    ) -> FollowupResponse:
        active_diagnostic = dict(diagnostics[-1]) if diagnostics else {}
        active_stage = str(active_diagnostic.get("stage", ""))
        if intent is not None and active_stage.startswith(
            "answer_generation"
        ):
            active_diagnostic["intent_checkpoint_available"] = True
        answer, enriched = cls._provider_failure_answer(
            failure,
            active_diagnostic,
        )
        final_diagnostics = (
            (*diagnostics[:-1], enriched)
            if diagnostics
            else ()
        )
        base = cls._routed_response(route, answer)
        return replace(
            base,
            source="external_error",
            fallback_reason=(
                failure or "external_response_unavailable"
            ),
            fallback_detail=detail,
            interpreted_intent=intent.to_dict() if intent else {},
            pipeline_warnings=warnings,
            pipeline_diagnostics=final_diagnostics,
            learning_move=response_plan.dialogue_move,
            next_learning_question=None,
            explanation_level=response_plan.explanation_level,
            adaptation_reasons=response_plan.adaptation_reasons,
        )

    def _local_followup(
        self,
        question: str,
        topic: TopicConfig,
        context: LearningAnalysisContext,
        route: QuestionRoute,
        concepts: tuple[TheoryConcept, ...],
        intent: QuestionIntent | None = None,
        metric_definitions: dict[str, dict[str, Any]] | None = None,
        response_plan: LearningResponsePlan | None = None,
    ) -> FollowupResponse:
        draft = self.theory_answerer.compose(
            question,
            route,
            topic,
            context,
            concepts,
            metric_definitions,
        )
        answer = draft.answer
        if response_plan is not None:
            if response_plan.misconception_targets:
                answer = (
                    "먼저 한 방향의 변화만 보고 모든 조건에 일반화하면 안 됩니다. "
                    + answer
                )
            elif (
                response_plan.explanation_level == "foundational"
                and response_plan.include_foundation
            ):
                answer = "핵심 개념부터 원인과 결과를 연결하면, " + answer
            elif response_plan.explanation_level == "intermediate":
                answer = "관찰값과 물리 메커니즘을 연결하면, " + answer
            elif response_plan.explanation_level == "advanced":
                answer = "조건 의존성과 검증 관점까지 연결하면, " + answer
        assessment = "not_applicable"
        acknowledged: tuple[str, ...] = ()
        corrections: tuple[str, ...] = ()
        next_question: str | None = None
        learning_move = (
            response_plan.dialogue_move
            if response_plan
            else "answer_question"
        )
        if learning_move == "confirm_experiment":
            assessment = "supported"
            acknowledged = (
                "현재 비교는 한 개의 실험 변수만 변경한 통제 비교입니다.",
            )
            answer = f"네, 현재 실험 설정을 기준으로 맞습니다. {answer}"
            next_question = (
                "이 조건 통제가 각 전기적 변화의 원인을 해석할 때 "
                "왜 중요한지도 이어서 확인해 볼까요?"
            )
        elif learning_move == "acknowledge_correction":
            assessment = "unverified"
            acknowledged = (
                "이전 설명과 현재 실험 조건을 다시 대조해야 한다는 지적을 반영했습니다.",
            )
            answer = (
                "맞아요. 말씀하신 지적을 반영해 현재 실험 조건과 근거부터 "
                f"다시 확인하겠습니다. {answer}"
            )
        elif learning_move == "evaluate_claim":
            assessment = "unverified"
            acknowledged = (
                "제시한 주장을 현재 결과와 일반 이론으로 나누어 검토했습니다.",
            )
            answer = (
                "말씀하신 주장을 그대로 결론으로 두지 않고, 현재 확인 가능한 "
                f"근거부터 나누어 보겠습니다. {answer}"
            )
        if (
            next_question is None
            and response_plan is not None
            and response_plan.check_understanding
        ):
            next_question = self._adaptive_next_question(
                response_plan,
                concepts,
            )
        response = self._routed_response(
            route,
            answer,
            evidence=draft.evidence_ids,
            distinguishes_current_result=draft.distinguishes_current_result,
            suggested_action_id=draft.suggested_action_id,
            theory_concepts=draft.theory_concepts,
            case_connection=draft.case_connection,
        )
        return replace(
            response,
            interpreted_intent=intent.to_dict() if intent else {},
            learning_move=learning_move,
            claim_assessment=assessment,
            acknowledged_points=acknowledged,
            correction_points=corrections,
            next_learning_question=next_question,
            explanation_level=(
                response_plan.explanation_level
                if response_plan
                else "foundational"
            ),
            adaptation_reasons=(
                response_plan.adaptation_reasons
                if response_plan
                else ()
            ),
        )

    @staticmethod
    def _adaptive_next_question(
        response_plan: LearningResponsePlan,
        concepts: tuple[TheoryConcept, ...],
    ) -> str | None:
        title = concepts[0].title if concepts else "이 개념"
        if response_plan.next_question_style == "diagnostic":
            return (
                f"{title}에 대해 이전 생각과 지금 설명에서 달라진 부분을 "
                "한 가지 말해 볼까요?"
            )
        if response_plan.next_question_style == "concept_check":
            return (
                f"{title}가 현재 관찰 결과와 연결되는 핵심 과정을 "
                "한 문장으로 정리해 볼까요?"
            )
        if response_plan.next_question_style == "mechanism_check":
            return (
                f"{title}의 변화가 어떤 전기적 지표로 이어지는지 "
                "원인과 결과를 연결해 볼까요?"
            )
        if response_plan.next_question_style == "transfer":
            return (
                f"{title}에 대한 이 설명이 다른 소자 조건에서도 유지되는지 "
                "확인하려면 어떤 변수를 추가로 비교해야 할까요?"
            )
        return None

    def _interpret_question(
        self,
        question: str,
        topic: TopicConfig,
        context: LearningAnalysisContext,
        history: list[dict[str, Any]],
        dialogue_state: dict[str, Any] | None = None,
    ) -> QuestionIntent | None:
        payload = {
            "learning_topic": {
                "topic_id": topic.topic_id,
                "title": topic.title,
                "description": topic.description,
                "learning_objectives": topic.learning_objectives,
                "case_theory_concepts": topic.theory_concepts,
            },
            "user_question": question,
            "conversation_history": history,
            "dialogue_state": dict(dialogue_state or {}),
            "available_concepts": [
                {"concept_id": item.concept_id, "title": item.title}
                for item in self.knowledge_base.concepts.values()
            ],
            "available_metrics": sorted({
                *context.electrical_changes,
                "vth",
                "ion",
                "ioff",
                "ss",
                "dibl",
                "gm_max",
                "gds",
                "ron",
            }),
            "available_parameters": sorted(topic.baseline_conditions),
            "available_actions": [
                "explain",
                "compare",
                "predict",
                "run_experiment",
                "add_condition",
                "navigate",
                "clarify",
            ],
        }
        return self._call(
            question_intent_prompt.build_prompt,
            payload,
            lambda data: validate_question_intent(
                data,
                question=question,
                allowed_concepts=set(self.knowledge_base.concepts),
                allowed_metrics=set(payload["available_metrics"]),
                allowed_parameters=set(topic.baseline_conditions),
            ),
            stage="intent_interpretation",
        )

    def _retry_checkpoint_intent(
        self,
        question: str,
        topic: TopicConfig,
        context: LearningAnalysisContext,
        history: list[dict[str, Any]],
    ) -> QuestionIntent | None:
        if not history:
            return None
        previous = history[-1]
        if (
            str(previous.get("source", "")) != "external_error"
            or sanitize_user_text(
                previous.get("question", ""),
                limit=1200,
            )
            != question
        ):
            return None
        diagnostics = [
            item
            for item in previous.get("pipeline_diagnostics", ())
            if isinstance(item, dict)
        ]
        if not diagnostics or not str(
            diagnostics[-1].get("stage", "")
        ).startswith("answer_generation"):
            return None
        saved_intent = previous.get("interpreted_intent")
        if not isinstance(saved_intent, dict) or not saved_intent:
            return None
        saved_intent = dict(saved_intent)
        for name in (
            "alternative_intents",
            "target_concepts",
            "requested_metrics",
        ):
            if isinstance(saved_intent.get(name), tuple):
                saved_intent[name] = list(saved_intent[name])
        try:
            validated = validate_question_intent(
                saved_intent,
                question=question,
                allowed_concepts=set(self.knowledge_base.concepts),
                allowed_metrics={
                    *context.electrical_changes,
                    "vth",
                    "ion",
                    "ioff",
                    "ss",
                    "dibl",
                    "gm_max",
                    "gds",
                    "ron",
                },
                allowed_parameters=set(topic.baseline_conditions),
            )
        except ValueError:
            return None
        return replace(validated, source="retry_checkpoint")

    def ask_followup(
        self,
        topic: TopicConfig,
        question: str,
        context: LearningAnalysisContext,
        history: list[dict[str, Any]] | None = None,
        dialogue_state: dict[str, Any] | None = None,
        learner_profile: dict[str, Any] | None = None,
    ) -> FollowupResponse:
        clean_question = sanitize_user_text(question)
        raw_history = list((history or [])[-6:])
        checkpoint_intent = self._retry_checkpoint_intent(
            clean_question,
            topic,
            context,
            raw_history,
        )
        clean_history = []
        for turn in raw_history:
            if str(turn.get("source", "")) == "external_error":
                continue
            clean_history.append({
                "question": sanitize_user_text(turn.get("question", ""), limit=600),
                "answer": sanitize_user_text(turn.get("answer", ""), limit=1200),
                "question_type": str(turn.get("question_type", "")),
                "matched_concepts": [
                    str(item) for item in turn.get("matched_concepts", ())
                ][:12],
            })
        if checkpoint_intent is not None:
            intent = checkpoint_intent
            intent_failure = intent_failure_detail = None
            intent_failure_diagnostic = {}
        else:
            intent = self._interpret_question(
                clean_question,
                topic,
                context,
                clean_history,
                dialogue_state,
            )
            intent_failure = self.last_provider_failure
            intent_failure_detail = self.last_provider_failure_detail
            intent_failure_diagnostic = dict(
                self.last_provider_diagnostic
            )
            intent_provider_calls = self.last_provider_call_diagnostics
        if checkpoint_intent is not None:
            intent_provider_calls = ()
        route = self.question_router.route(
            clean_question,
            topic,
            context,
            clean_history,
            interpreted_intent=intent,
        )
        pipeline_warnings: tuple[str, ...] = (
            ("intent_checkpoint_reused",)
            if checkpoint_intent is not None
            else ()
        )
        pipeline_diagnostics: tuple[dict[str, Any], ...] = (
            (*intent_provider_calls, intent_failure_diagnostic)
            if intent_failure_diagnostic
            else tuple(intent_provider_calls)
        )
        if (
            self.provider is not None
            and intent is None
            and intent_failure == "external_validation_failed"
        ):
            structure = (
                "parameter_by_parameter"
                if "각" in clean_question
                and (
                    "별" in clean_question
                    or "파라미터" in clean_question
                    or "지표" in clean_question
                )
                else route.answer_structure
            )
            route = replace(
                route,
                answer_structure=structure,
                intent_source="deterministic_fallback",
            )
            pipeline_warnings = (
                "intent_validation_failed"
                + (
                    f":{intent_failure_detail}"
                    if intent_failure_detail
                    else ""
                ),
            )
        response_plan = build_response_plan(
            clean_question,
            route,
            intent,
            dialogue_state,
            learner_profile,
        )
        broad_explanation = (
            response_plan.structure == "parameter_by_parameter"
            or len(route.matched_concepts) >= 3
        )
        concepts = self.knowledge_base.retrieve(
            route.matched_concepts,
            limit=8 if broad_explanation else 5,
        )
        requested_metrics = select_definition_metrics(
            route,
            intent,
        )
        result_metrics = select_result_metrics(
            route,
            intent,
            context,
        )
        knowledge_layers = LearningKnowledgeAssembler.build(
            topic,
            context,
            concepts,
            requested_metrics=requested_metrics,
            result_metrics=result_metrics,
        )
        if (
            self.provider is not None
            and intent is None
            and intent_failure != "external_validation_failed"
        ):
            return self._provider_failure_followup(
                route,
                intent,
                response_plan,
                failure=intent_failure,
                detail=intent_failure_detail,
                diagnostics=pipeline_diagnostics,
                warnings=(
                    "intent_stage_failed"
                    + (
                        f":{intent_failure_detail}"
                        if intent_failure_detail
                        else ""
                    ),
                ),
            )
        compact_layers = compact_knowledge_layers(
            knowledge_layers,
            route,
        )
        compact_simulation = compact_simulation_facts(
            context,
            route,
            result_metrics,
        )
        payload = {
            "learning_topic": {
                "topic_id": topic.topic_id,
                "title": topic.title,
                "description": topic.description,
                "theory_reference": topic.theory_reference,
            },
            "user_question": clean_question,
            "conversation_history": compact_history(
                clean_history,
                route,
                intent,
                response_plan,
            ),
            "dialogue_state": compact_dialogue_state(
                dialogue_state,
                response_plan,
            ),
            "learner_profile": {
                "explanation_level": response_plan.explanation_level,
                "completed_concepts": response_plan.known_concepts,
                "review_concepts": response_plan.review_concepts,
                "misconception_targets": response_plan.misconception_targets,
            },
            "question_route": route.to_dict(),
            "interpreted_intent": intent.to_dict() if intent else None,
            "answer_plan": compact_answer_plan(response_plan),
            "knowledge_layers": compact_layers,
            "simulation_facts": compact_simulation,
            "allowed_evidence_ids": selected_evidence_ids(
                context,
                route,
                compact_layers["result_facts"],
                compact_simulation,
            ),
            "allowed_next_actions": [asdict(item) for item in topic.allowed_next_actions],
        }
        payload = fit_followup_prompt_budget(
            payload,
            followup_prompt.build_prompt,
        )
        external = self._call(
            followup_prompt.build_prompt,
            payload,
            lambda data: validate_followup(
                data,
                topic,
                context,
                route,
                theory_concepts=tuple(item.concept_id for item in concepts),
                case_connection=next(
                    (
                        item.case_connection
                        for item in concepts
                        if item.concept_id in route.matched_concepts
                        and item.case_connection
                    ),
                    None,
                ),
                interpreted_intent=(
                    intent.to_dict() if intent else {}
                ),
                additional_numeric_facts=(
                    {
                        "metric_definitions": (
                            knowledge_layers.metric_definitions
                        ),
                        "interpreted_intent": (
                            intent.to_dict() if intent else {}
                        ),
                        "user_question": clean_question,
                    }
                ),
                learning_move=response_plan.dialogue_move,
                explanation_level=response_plan.explanation_level,
                adaptation_reasons=response_plan.adaptation_reasons,
                question=clean_question,
            ),
            stage="answer_generation",
        )
        if external is not None:
            answer_provider_calls = self.last_provider_call_diagnostics
            return replace(
                external,
                pipeline_warnings=pipeline_warnings,
                pipeline_diagnostics=(
                    pipeline_diagnostics + answer_provider_calls
                ),
                next_learning_question=(
                    external.next_learning_question
                    or self._adaptive_next_question(
                        response_plan,
                        concepts,
                    )
                ),
            )
        if self.provider is not None:
            answer_provider_calls = self.last_provider_call_diagnostics
            answer_diagnostic = dict(self.last_provider_diagnostic)
            final_diagnostics = (
                pipeline_diagnostics
                + answer_provider_calls
                + ((answer_diagnostic,) if answer_diagnostic else ())
            )
            return self._provider_failure_followup(
                route,
                intent,
                response_plan,
                failure=self.last_provider_failure,
                detail=self.last_provider_failure_detail,
                diagnostics=final_diagnostics,
                warnings=pipeline_warnings,
            )
        return self._local_followup(
            clean_question,
            topic,
            context,
            route,
            concepts,
            intent,
            knowledge_layers.metric_definitions,
            response_plan,
        )

    @staticmethod
    def apply_evaluation(session: LearningSession, evaluation: AnswerEvaluation) -> None:
        session.understanding_level = UnderstandingLevel(evaluation.understanding_level)
        session.completed_concepts = list(dict.fromkeys((*session.completed_concepts, *evaluation.correct_concepts)))
        session.remaining_concepts = [
            concept for concept in session.remaining_concepts if concept not in evaluation.correct_concepts
        ]
        session.detected_misconceptions = list(dict.fromkeys(
            (*session.detected_misconceptions, *evaluation.detected_misconceptions)
        ))
        session.updated_at = utc_now()

    @staticmethod
    def record_followup(session: LearningSession, question: str, response: FollowupResponse) -> None:
        session.followup_history.append(FollowupTurn(
            question=sanitize_user_text(question),
            answer=response.answer,
            question_type=response.question_type,
            evidence_ids=response.evidence_ids,
            created_at=utc_now(),
            relevance_to_case=response.relevance_to_case,
            matched_concepts=response.matched_concepts,
            uses_current_result=response.uses_current_result,
            needs_new_experiment=response.needs_new_experiment,
            needs_clarification=response.needs_clarification,
            clarification_question=response.clarification_question,
            theory_concepts=response.theory_concepts,
            case_connection=response.case_connection,
            source=response.source,
            fallback_reason=response.fallback_reason,
            interpreted_intent=response.interpreted_intent,
            interpretation_source=response.interpretation_source,
            pipeline_warnings=response.pipeline_warnings,
            pipeline_diagnostics=response.pipeline_diagnostics,
            fallback_detail=response.fallback_detail,
            learning_move=response.learning_move,
            claim_assessment=response.claim_assessment,
            acknowledged_points=response.acknowledged_points,
            correction_points=response.correction_points,
            next_learning_question=response.next_learning_question,
            explanation_level=response.explanation_level,
            adaptation_reasons=response.adaptation_reasons,
        ))
        session.followup_history = session.followup_history[-20:]
        DialogueStateManager.update_from_response(
            session.dialogue_state,
            question=question,
            response=response,
        )
        session.updated_at = utc_now()
