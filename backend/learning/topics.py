from __future__ import annotations

import json
from pathlib import Path

from .knowledge_base import load_theory_knowledge_base
from .schemas import TopicConfig
from .validation import compare_experiment_conditions, validate_model_conditions


class TopicConfigError(ValueError):
    pass


CONFIG_DIR = Path(__file__).with_name("configs")


def _require_unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise TopicConfigError(f"duplicate_{label}")


def validate_topic(topic: TopicConfig) -> TopicConfig:
    if topic.schema_version != "1.0":
        raise TopicConfigError("unsupported_topic_schema")
    if not topic.topic_id or not topic.title or not topic.learning_objectives:
        raise TopicConfigError("missing_topic_identity")
    if topic.catalog_order < 0 or topic.topic_id in topic.prerequisite_topic_ids:
        raise TopicConfigError("invalid_topic_curriculum_metadata")
    if not topic.expected_concepts or not topic.prediction_questions or not topic.observation_questions:
        raise TopicConfigError("incomplete_learning_contract")
    unknown_theory = (
        set(topic.theory_concepts)
        - set(load_theory_knowledge_base().concepts)
    )
    if unknown_theory:
        raise TopicConfigError("unknown_theory_concept")
    comparison = compare_experiment_conditions(topic.baseline_conditions, topic.comparison_conditions)
    if topic.topic_id == "sce_channel_length" and comparison.changed_parameters != ("L",):
        raise TopicConfigError("sce_topic_must_change_channel_length_only")
    reference_ids = [item.condition_id for item in topic.reference_conditions]
    _require_unique(reference_ids, "reference_condition_id")
    for reference in topic.reference_conditions:
        if not reference.condition_id or not reference.label:
            raise TopicConfigError("invalid_reference_condition")
        validate_model_conditions(
            reference.conditions,
            require_supported_value=True,
        )
    if topic.comparison_design not in {
        "controlled_pair",
        "two_by_two",
        "candidate_set",
    }:
        raise TopicConfigError("invalid_comparison_design")
    if topic.display_parameters and not set(topic.display_parameters).issubset(
        topic.baseline_conditions
    ):
        raise TopicConfigError("invalid_display_parameters")
    condition_labels = {
        *(item.label for item in topic.reference_conditions),
        topic.baseline_label,
        topic.comparison_label,
    }
    if (
        not set(topic.condition_descriptions).issubset(condition_labels)
        or (
            topic.condition_descriptions
            and set(topic.condition_descriptions) != condition_labels
        )
        or any(not value.strip() for value in topic.condition_descriptions.values())
    ):
        raise TopicConfigError("invalid_condition_descriptions")
    question_ids = [item.question_id for item in (*topic.prediction_questions, *topic.observation_questions)]
    action_ids = [item.action_id for item in topic.allowed_next_actions]
    _require_unique(question_ids, "question_id")
    _require_unique(action_ids, "action_id")
    for question in (*topic.prediction_questions, *topic.observation_questions):
        if not question.question_id or not question.prompt:
            raise TopicConfigError("invalid_question")
        if "select" in question.type and not question.options:
            raise TopicConfigError("select_question_requires_options")
        if question.correct_options and not set(question.correct_options).issubset(question.options):
            raise TopicConfigError("correct_option_not_in_options")
        if not set(question.concepts_by_option).issubset(question.options):
            raise TopicConfigError("concept_mapping_option_not_in_options")
        if not set(question.misconceptions_by_option).issubset(question.options):
            raise TopicConfigError("misconception_mapping_option_not_in_options")
        mapped_concepts = {value for values in question.concepts_by_option.values() for value in values}
        mapped_misconceptions = {value for values in question.misconceptions_by_option.values() for value in values}
        if not mapped_concepts.issubset(topic.expected_concepts):
            raise TopicConfigError("unknown_expected_concept")
        if not mapped_misconceptions.issubset(topic.common_misconceptions):
            raise TopicConfigError("unknown_common_misconception")
    return topic


def load_topic(topic_id: str, *, config_dir: Path = CONFIG_DIR) -> TopicConfig:
    path = config_dir / f"{topic_id}.json"
    if not path.is_file():
        raise KeyError(f"unknown_learning_topic:{topic_id}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return validate_topic(TopicConfig.from_dict(raw))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        if isinstance(error, TopicConfigError):
            raise
        raise TopicConfigError(f"invalid_topic_config:{topic_id}") from error


def load_topics(*, config_dir: Path = CONFIG_DIR) -> dict[str, TopicConfig]:
    topics: dict[str, TopicConfig] = {}
    for path in sorted(config_dir.glob("*.json")):
        topic = load_topic(path.stem, config_dir=config_dir)
        if topic.topic_id != path.stem:
            raise TopicConfigError(f"topic_filename_mismatch:{path.stem}")
        topics[topic.topic_id] = topic
    known = set(topics)
    for topic in topics.values():
        if not set(topic.prerequisite_topic_ids).issubset(known):
            raise TopicConfigError(
                f"unknown_topic_prerequisite:{topic.topic_id}"
            )
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(topic_id: str) -> None:
        if topic_id in visiting:
            raise TopicConfigError("cyclic_topic_prerequisite")
        if topic_id in visited:
            return
        visiting.add(topic_id)
        for prerequisite in topics[topic_id].prerequisite_topic_ids:
            visit(prerequisite)
        visiting.remove(topic_id)
        visited.add(topic_id)

    for topic_id in topics:
        visit(topic_id)
    return dict(
        sorted(
            topics.items(),
            key=lambda item: (item[1].catalog_order, item[0]),
        )
    )
