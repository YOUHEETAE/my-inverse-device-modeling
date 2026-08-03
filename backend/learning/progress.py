from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping, Sequence

from .schemas import LearningSession, LearningStep, TopicConfig


@dataclass(frozen=True)
class CaseProgress:
    topic_id: str
    title: str
    status: str
    session_count: int
    completed_session_count: int
    latest_step: str | None
    completed_concepts: tuple[str, ...]
    remaining_concepts: tuple[str, ...]
    updated_at: str | None
    prerequisites: tuple[str, ...]
    prerequisites_met: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class LearningPortfolio:
    cases: tuple[CaseProgress, ...]
    completed_case_count: int
    total_case_count: int
    next_topic_id: str | None
    recommendation_kind: str
    recommendation_reason: str
    archived_incompatible_session_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def _compatible(session: LearningSession, topic: TopicConfig) -> bool:
    return (
        session.topic_id == topic.topic_id
        and session.baseline_conditions == topic.baseline_conditions
        and session.comparison_conditions == topic.comparison_conditions
    )


def build_learning_portfolio(
    topics: Mapping[str, TopicConfig],
    sessions: Sequence[LearningSession],
) -> LearningPortfolio:
    ordered_topics = sorted(
        topics.values(), key=lambda item: (item.catalog_order, item.topic_id)
    )
    compatible_ids: set[str] = set()
    grouped: dict[str, list[LearningSession]] = {}
    for topic in ordered_topics:
        matches = [
            session for session in sessions if _compatible(session, topic)
        ]
        matches.sort(key=lambda item: item.updated_at, reverse=True)
        grouped[topic.topic_id] = matches
        compatible_ids.update(item.session_id for item in matches)

    completed_topic_ids = {
        topic.topic_id
        for topic in ordered_topics
        if any(
            session.current_step is LearningStep.SESSION_COMPLETE
            for session in grouped[topic.topic_id]
        )
    }
    progress_items = []
    for topic in ordered_topics:
        matches = grouped[topic.topic_id]
        latest = matches[0] if matches else None
        completed_sessions = [
            item for item in matches
            if item.current_step is LearningStep.SESSION_COMPLETE
        ]
        completed_concepts = tuple(
            concept
            for concept in topic.expected_concepts
            if any(concept in item.completed_concepts for item in matches)
        )
        prerequisites_met = set(topic.prerequisite_topic_ids).issubset(
            completed_topic_ids
        )
        status = (
            "completed"
            if completed_sessions
            else "in_progress"
            if matches
            else "locked"
            if not prerequisites_met
            else "not_started"
        )
        progress_items.append(
            CaseProgress(
                topic_id=topic.topic_id,
                title=topic.title,
                status=status,
                session_count=len(matches),
                completed_session_count=len(completed_sessions),
                latest_step=(
                    latest.current_step.value if latest is not None else None
                ),
                completed_concepts=completed_concepts,
                remaining_concepts=tuple(
                    concept
                    for concept in topic.expected_concepts
                    if concept not in completed_concepts
                ),
                updated_at=latest.updated_at if latest is not None else None,
                prerequisites=topic.prerequisite_topic_ids,
                prerequisites_met=prerequisites_met,
            )
        )

    resumable = next(
        (
            item for item in progress_items
            if item.status == "in_progress" and item.prerequisites_met
        ),
        None,
    )
    available = next(
        (item for item in progress_items if item.status == "not_started"),
        None,
    )
    review = next(
        (item for item in progress_items if item.status == "completed"),
        None,
    )
    if resumable is not None:
        next_topic_id = resumable.topic_id
        kind = "resume"
        reason = f"진행 중인 ‘{resumable.title}’ 학습을 이어가세요."
    elif available is not None:
        next_topic_id = available.topic_id
        kind = "start"
        reason = f"선행 학습을 마쳤으므로 ‘{available.title}’을 시작할 수 있습니다."
    elif len(completed_topic_ids) == len(progress_items) and progress_items:
        next_topic_id = review.topic_id if review else None
        kind = "review"
        reason = "모든 Case를 완료했습니다. 필요한 Case를 선택해 복습하세요."
    else:
        next_topic_id = None
        kind = "complete_prerequisite"
        reason = "잠긴 Case의 선행 학습을 먼저 완료하세요."

    return LearningPortfolio(
        cases=tuple(progress_items),
        completed_case_count=len(completed_topic_ids),
        total_case_count=len(progress_items),
        next_topic_id=next_topic_id,
        recommendation_kind=kind,
        recommendation_reason=reason,
        archived_incompatible_session_count=sum(
            session.topic_id in topics and session.session_id not in compatible_ids
            for session in sessions
        ),
    )
