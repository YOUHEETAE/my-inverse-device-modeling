from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from .experiment_runner import LearningExperimentRunner
from .llm_service import LearningLLMService
from .progress import build_learning_portfolio
from .schemas import LearningSession, LearningStep, utc_now
from .session_repository import JsonSessionRepository
from .topics import load_topics
from .validation import compare_experiment_conditions
from backend.explanation.comparison_planner import build_comparison_plan
from backend.explanation.providers import ProviderSettings


@dataclass(frozen=True)
class ReadinessCheck:
    check_id: str
    status: str
    detail: dict[str, Any]
    required: bool = True

    @property
    def passed(self) -> bool:
        return self.status == "passed" or (
            self.status == "skipped" and not self.required
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["passed"] = self.passed
        return value


@dataclass(frozen=True)
class PlatformReadinessReport:
    generated_at: str
    checks: tuple[ReadinessCheck, ...]
    ready: bool
    schema_version: str = "1.1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "ready": self.ready,
            "checks": [item.to_dict() for item in self.checks],
            "summary": {
                "passed": sum(
                    item.status == "passed" for item in self.checks
                ),
                "skipped": sum(
                    item.status == "skipped" for item in self.checks
                ),
                "total": len(self.checks),
                "required_passed": sum(
                    item.required and item.status == "passed"
                    for item in self.checks
                ),
                "required_total": sum(
                    item.required for item in self.checks
                ),
                "failed_check_ids": [
                    item.check_id for item in self.checks if not item.passed
                ],
            },
        }


def _check(
    check_id: str,
    operation,
    *,
    required: bool = True,
) -> ReadinessCheck:
    try:
        detail = operation()
    except Exception as error:
        return ReadinessCheck(
            check_id,
            "failed",
            {
                "error_type": type(error).__name__,
                "message": str(error)[:500],
            },
            required,
        )
    return ReadinessCheck(check_id, "passed", dict(detail or {}), required)


def run_platform_readiness_audit(
    repository_root: Path,
    *,
    with_models: bool = True,
) -> PlatformReadinessReport:
    topics = load_topics()
    checks: list[ReadinessCheck] = []

    def catalog_check() -> dict[str, Any]:
        controlled = {}
        for topic in topics.values():
            comparison = compare_experiment_conditions(
                topic.baseline_conditions,
                topic.comparison_conditions,
            )
            controlled[topic.topic_id] = list(comparison.changed_parameters)
        return {
            "topic_ids": list(topics),
            "controlled_changed_parameters": controlled,
        }

    checks.append(_check("topic_catalog", catalog_check))

    def comparison_architecture_check() -> dict[str, Any]:
        def subject(
            index: int,
            *,
            length: float,
            tox: float = 10.0,
        ) -> dict[str, Any]:
            return {
                "subject_id": f"curve_{index}",
                "display_name": f"Curve {index}",
                "device_parameters": {
                    "channel_length_nm": length,
                    "oxide_thickness_nm": tox,
                    "bulk_doping_cm3": 1e16,
                    "source_drain_doping_cm3": 1e20,
                    "ldd_doping_cm3": 1e18,
                },
            }

        pair = build_comparison_plan([
            subject(1, length=700), subject(2, length=300),
        ])
        compound = build_comparison_plan([
            subject(1, length=700, tox=10),
            subject(2, length=400, tox=15),
        ])
        sweep = build_comparison_plan([
            subject(1, length=700),
            subject(2, length=500),
            subject(3, length=300),
        ])
        if (
            pair.analysis_mode != "controlled_pair"
            or compound.analysis_mode != "compound_pair"
            or compound.allowed_claim_level != "multi_parameter_association"
            or sweep.analysis_mode != "controlled_sweep"
            or sweep.sweep_values != (300.0, 500.0, 700.0)
        ):
            raise ValueError("comparison_architecture_contract_failed")
        return {
            "controlled_pair": pair.analysis_mode,
            "compound_pair": {
                "mode": compound.analysis_mode,
                "claim_level": compound.allowed_claim_level,
            },
            "controlled_sweep": {
                "mode": sweep.analysis_mode,
                "parameter": sweep.sweep_parameter,
                "ordered_values": list(sweep.sweep_values),
                "representative_subject_ids": list(
                    sweep.representative_subject_ids
                ),
            },
        }

    checks.append(_check(
        "comparison_architecture",
        comparison_architecture_check,
    ))

    def runtime_assets_check() -> dict[str, Any]:
        required = (
            "ai/model_artifacts/curve_model/final/pca_xgboost/idvd/model.pkl",
            "ai/model_artifacts/curve_model/final/pca_xgboost/idvg/model.pkl",
            "ai/model_artifacts/field_map_model/final/"
            "coordinate_mlp_physics/node/model.npz",
            "ai/model_artifacts/field_map_model/final/"
            "coordinate_mlp_physics/element/model.npz",
            "tcad/data_extraction/base_case/gmsh_mos2d.geo",
        )
        missing = [
            value for value in required
            if not (repository_root / value).is_file()
        ]
        if missing:
            raise ValueError("missing_runtime_assets:" + ",".join(missing))
        return {
            "required_file_count": len(required),
            "total_bytes": sum(
                (repository_root / value).stat().st_size
                for value in required
            ),
        }

    checks.append(_check("runtime_assets", runtime_assets_check))

    def curriculum_check() -> dict[str, Any]:
        completed: set[str] = set()
        remaining = list(topics.values())
        order = []
        while remaining:
            available = next(
                (
                    topic for topic in remaining
                    if set(topic.prerequisite_topic_ids).issubset(completed)
                ),
                None,
            )
            if available is None:
                raise ValueError("unreachable_curriculum_topic")
            remaining.remove(available)
            completed.add(available.topic_id)
            order.append(available.topic_id)
        return {"reachable_order": order}

    checks.append(_check("curriculum_reachability", curriculum_check))

    def persistence_check() -> dict[str, Any]:
        with TemporaryDirectory() as directory:
            repository = JsonSessionRepository(Path(directory))
            created = []
            for topic in topics.values():
                session = LearningSession.create(topic)
                repository.save(session)
                created.append(session)
            restored = repository.list_sessions()
        if {item.session_id for item in restored} != {
            item.session_id for item in created
        }:
            raise ValueError("session_round_trip_mismatch")
        return {
            "session_count": len(restored),
            "topic_ids": sorted(item.topic_id for item in restored),
        }

    checks.append(_check("session_isolation_round_trip", persistence_check))

    def portfolio_check() -> dict[str, Any]:
        initial = build_learning_portfolio(topics, [])
        first = initial.next_topic_id
        first_session = LearningSession.create(topics[str(first)])
        first_session.current_step = LearningStep.SESSION_COMPLETE
        after_first = build_learning_portfolio(topics, [first_session])
        if first is None or after_first.next_topic_id == first:
            raise ValueError("portfolio_did_not_advance")
        return {
            "initial_recommendation": first,
            "next_recommendation": after_first.next_topic_id,
            "total_cases": initial.total_case_count,
        }

    checks.append(_check("portfolio_recommendation", portfolio_check))

    contexts = {}
    model_results = {}
    if with_models:
        runner = LearningExperimentRunner.from_repository(repository_root)

        def model_check() -> dict[str, Any]:
            expected = {
                "sce_channel_length": {
                    "changed": "L",
                    "directions": {
                        "ion": "increase",
                        "ioff": "increase",
                        "dibl": "increase",
                    },
                },
                "oxide_gate_control": {
                    "changed": "T",
                    "directions": {
                        "gm_max": "increase",
                        "ss": "decrease",
                        "ioff": "increase",
                    },
                },
                "body_doping_design_window": {
                    "changed": "B",
                    "directions": {
                        "vth_low": "increase",
                        "ion": "decrease",
                        "ioff": "decrease",
                    },
                },
                "source_drain_on_state_conduction": {
                    "changed": "SD",
                    "directions": {
                        "ion": "increase",
                        "ron": "decrease",
                        "dibl": "increase",
                        "gds": "increase",
                    },
                },
                "ldd_field_resistance_tradeoff": {
                    "changed": "LDD",
                    "directions": {
                        "ion": "increase",
                        "ron": "decrease",
                        "gm_max": "increase",
                        "gds": "increase",
                    },
                },
                "channel_oxide_electrostatic_compensation": {
                    "changed": "T",
                    "directions": {
                        "ss": "decrease",
                        "dibl": "decrease",
                        "ioff": "increase",
                        "ion": "increase",
                    },
                },
                "source_drain_ldd_junction_engineering": {
                    "changed": "LDD",
                    "directions": {
                        "ion": "increase",
                        "ron": "decrease",
                        "gm_max": "increase",
                        "gds": "increase",
                    },
                },
                "integrated_device_design": {
                    "changed": "L",
                    "directions": {
                        "ion": "increase",
                        "ioff": "increase",
                        "dibl": "increase",
                        "ron": "decrease",
                    },
                },
            }
            details = {}
            for topic_id, contract in expected.items():
                result = runner.execute(topics[topic_id])
                model_results[topic_id] = result
                context = result.learning_context
                contexts[topic_id] = context
                directions = {
                    name: context.electrical_changes[name].direction
                    for name in contract["directions"]
                }
                if (
                    context.experiment.get("changed_parameter")
                    != contract["changed"]
                    or directions != contract["directions"]
                    or not context.field_observations
                ):
                    raise ValueError(f"model_contract_failed:{topic_id}")
                details[topic_id] = {
                    "analysis_status": context.analysis_status,
                    "changed_parameter": context.experiment.get(
                        "changed_parameter"
                    ),
                    "directions": directions,
                    "field_observation_count": len(
                        context.field_observations
                    ),
                }
            return details

        checks.append(_check("real_model_contracts", model_check))

        def tutor_check() -> dict[str, Any]:
            service = LearningLLMService()
            questions = {
                "sce_channel_length": (
                    "이번 결과에서 Vth가 왜 감소했나요?",
                    {"threshold_voltage"},
                ),
                "oxide_gate_control": (
                    "이번 결과에서 gm은 증가하고 SS는 감소했는데 왜 그런가요?",
                    {"transconductance", "subthreshold_swing"},
                ),
                "body_doping_design_window": (
                    "이번 결과에서 Body doping을 높였더니 Vth가 왜 증가했나요?",
                    {"body_doping", "threshold_voltage"},
                ),
                "source_drain_on_state_conduction": (
                    "이번 결과에서 Source/Drain doping을 높였더니 Ion과 DIBL이 왜 함께 증가했나요?",
                    {"source_drain_doping", "on_current", "dibl"},
                ),
                "ldd_field_resistance_tradeoff": (
                    "이번 결과에서 LDD doping을 높였더니 Drain Field와 Ion이 왜 함께 증가했나요?",
                    {"ldd", "electric_field", "on_current"},
                ),
                "channel_oxide_electrostatic_compensation": (
                    "이번 결과에서 얇은 Oxide가 짧은 Channel의 DIBL을 얼마나 보상했나요?",
                    {"oxide_thickness", "dibl", "short_channel_effect"},
                ),
                "source_drain_ldd_junction_engineering": (
                    "이번 결과에서 High SD와 High LDD를 함께 썼을 때 구동 이득과 Drain 제어 비용은 무엇인가요?",
                    {"source_drain_doping", "ldd", "on_current", "dibl"},
                ),
                "integrated_device_design": (
                    "이번 결과에서 Balanced 후보의 Ion, Ioff, DIBL, SS가 목표 사양을 어떻게 만족했나요?",
                    {"on_current", "off_current", "dibl", "subthreshold_swing"},
                ),
            }
            details = {}
            for topic_id, (question, concepts) in questions.items():
                response = service.ask_followup(
                    topics[topic_id],
                    question,
                    contexts[topic_id],
                )
                if (
                    response.question_type != "current_result"
                    or not response.uses_current_result
                    or not response.evidence_ids
                    or not concepts.issubset(response.theory_concepts)
                ):
                    raise ValueError(f"tutor_grounding_failed:{topic_id}")
                details[topic_id] = {
                    "question_type": response.question_type,
                    "evidence_count": len(response.evidence_ids),
                    "theory_concepts": list(response.theory_concepts),
                }
            return details

        checks.append(_check("local_tutor_grounding", tutor_check))

        def multi_condition_context_check() -> dict[str, Any]:
            # Keep explanation chat imports lazy. backend.learning is imported
            # by the chat knowledge layer, so module-level imports here would
            # create an order-dependent learning -> readiness -> chat cycle.
            from backend.explanation.comparison_focus import (
                resolve_comparison_focus,
            )
            from backend.explanation.curve_analyzer import (
                build_curve_payload,
            )
            from backend.explanation.field_analyzer import (
                build_field_payload,
            )
            from backend.explanation.field_chat import (
                FieldAnalysisSnapshot,
                FieldQuestionIntent,
                build_field_context_pack,
            )
            from backend.explanation.field_renderer import (
                render_field_explanation,
            )
            from backend.explanation.iv_chat import (
                IVAnalysisSnapshot,
                IVQuestionIntent,
                build_iv_context_pack,
            )
            from backend.explanation.iv_renderer import (
                render_iv_explanation,
            )

            sce = model_results["sce_channel_length"]
            middle_conditions = dict(
                topics["sce_channel_length"].baseline_conditions
            )
            middle_conditions["L"] = 500.0
            middle = runner._run_condition("Curve 2", middle_conditions)
            runs = (sce.baseline, middle, sce.comparison)
            labels = ("Curve 1", "Curve 2", "Curve 3")
            configs = [
                runner._config(run.conditions) for run in runs
            ]
            curve_results = [
                (label, run.idvd, run.idvg)
                for label, run in zip(labels, runs)
            ]
            curve_payload = build_curve_payload(
                curve_results, configs,
            ).to_dict()
            curve_snapshot = IVAnalysisSnapshot(
                analysis_id=str(curve_payload["analysis_id"]),
                curve_labels=labels,
                payload=curve_payload,
                automatic_explanation=render_iv_explanation(curve_payload),
            )
            curve_focus = resolve_comparison_focus(
                curve_payload, "전체 L sweep 추세를 설명해줘.",
            )
            curve_pack = build_iv_context_pack(
                curve_snapshot,
                IVQuestionIntent(
                    intent="compare_curves",
                    requested_metrics=("ion", "ioff", "ss", "dibl"),
                    needs_current_result=True,
                    answer_structure="comparison",
                ),
                curve_focus,
            )

            field_payload = build_field_payload(
                [
                    (label, run.field_map)
                    for label, run in zip(labels, runs)
                ],
                "Electric field",
                "Auto",
                "Robust 1-99%",
            ).to_dict()
            field_snapshot = FieldAnalysisSnapshot(
                analysis_id=str(field_payload["analysis_id"]),
                field_labels=labels,
                display=str(
                    field_payload.get("context", {}).get(
                        "display", "electric_field",
                    )
                ),
                payload=field_payload,
                automatic_explanation=render_field_explanation(
                    field_payload
                ),
                iv_payload=curve_payload,
            )
            field_focus = resolve_comparison_focus(
                field_payload, "전체 L sweep 공간 추세를 설명해줘.",
            )
            field_pack = build_field_context_pack(
                field_snapshot,
                FieldQuestionIntent(
                    intent="compare_maps",
                    needs_current_result=True,
                    answer_structure="comparison",
                ),
                field_focus,
            )
            curve_bytes = len(json.dumps(
                curve_pack, ensure_ascii=False, allow_nan=False,
            ).encode("utf-8"))
            field_bytes = len(json.dumps(
                field_pack, ensure_ascii=False, allow_nan=False,
            ).encode("utf-8"))
            if (
                curve_payload["comparison_plan"]["analysis_mode"]
                != "controlled_sweep"
                or field_payload["comparison_plan"]["analysis_mode"]
                != "controlled_sweep"
                or len(curve_pack["comparisons"]) != 2
                or len(field_pack["comparisons"]) != 2
                or curve_bytes >= 16_000
                or field_bytes >= 18_000
                or not curve_pack["fixed_conditions"]
                or not field_pack["fixed_conditions"]
            ):
                raise ValueError("multi_condition_context_contract_failed")
            return {
                "conditions_nm": [700, 500, 300],
                "analysis_mode": "controlled_sweep",
                "comparison_strategy": "adjacent_pairs",
                "comparison_count_sent": {
                    "iv": len(curve_pack["comparisons"]),
                    "field": len(field_pack["comparisons"]),
                },
                "context_bytes": {
                    "iv": curve_bytes,
                    "field": field_bytes,
                },
                "context_limits": {
                    "iv": 16_000,
                    "field": 18_000,
                },
                "fixed_parameters_factored": True,
            }

        checks.append(_check(
            "multi_condition_context_budget",
            multi_condition_context_check,
        ))
    else:
        checks.extend(
            (
                ReadinessCheck(
                    "real_model_contracts",
                    "skipped",
                    {"reason": "models_disabled"},
                    required=False,
                ),
                ReadinessCheck(
                    "local_tutor_grounding",
                    "skipped",
                    {"reason": "requires_model_contexts"},
                    required=False,
                ),
                ReadinessCheck(
                    "multi_condition_context_budget",
                    "skipped",
                    {"reason": "requires_model_contexts"},
                    required=False,
                ),
            )
        )

    external_settings = ProviderSettings.from_environment("external_llm")
    checks.append(
        ReadinessCheck(
            "external_llm_live",
            "skipped",
            {
                "reason": (
                    "Live Groq calls are environment- and quota-dependent; "
                    "verify separately with the configured API key."
                ),
                "api_key_configured": bool(external_settings.api_key()),
                "api_key_env": external_settings.api_key_env,
                "model": external_settings.model,
                "base_url": external_settings.base_url,
                "live_call_spent": False,
            },
            required=False,
        )
    )
    ready = all(item.passed for item in checks)
    return PlatformReadinessReport(
        generated_at=utc_now(),
        checks=tuple(checks),
        ready=ready,
    )
