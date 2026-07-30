from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class TheoryConcept:
    concept_id: str
    title: str
    summary: str
    principles: tuple[str, ...]
    general_effects: tuple[str, ...]
    related_concepts: tuple[str, ...]
    case_connection: str
    caveats: tuple[str, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TheoryConcept":
        return cls(
            concept_id=str(data["concept_id"]),
            title=str(data["title"]),
            summary=str(data["summary"]),
            principles=tuple(str(item) for item in data.get("principles", [])),
            general_effects=tuple(str(item) for item in data.get("general_effects", [])),
            related_concepts=tuple(str(item) for item in data.get("related_concepts", [])),
            case_connection=str(data.get("case_connection", "")),
            caveats=tuple(str(item) for item in data.get("caveats", [])),
        )

    def to_prompt_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TheoryKnowledgeBase:
    knowledge_id: str
    concepts: dict[str, TheoryConcept]
    schema_version: str = "1.0"

    @classmethod
    def load(cls, path: Path) -> "TheoryKnowledgeBase":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if str(data.get("schema_version", "")) != "1.0":
            raise ValueError("unsupported_theory_knowledge_schema")
        concepts = [TheoryConcept.from_dict(item) for item in data.get("concepts", [])]
        by_id = {item.concept_id: item for item in concepts}
        if not by_id or len(by_id) != len(concepts):
            raise ValueError("invalid_theory_concept_ids")
        for concept in concepts:
            if not concept.title or not concept.summary or not concept.principles:
                raise ValueError(f"incomplete_theory_concept:{concept.concept_id}")
            unknown = set(concept.related_concepts) - set(by_id)
            if unknown:
                raise ValueError(f"unknown_related_theory_concept:{concept.concept_id}")
        return cls(str(data["knowledge_id"]), by_id)

    def retrieve(
        self,
        concept_ids: Iterable[str],
        *,
        limit: int = 6,
    ) -> tuple[TheoryConcept, ...]:
        seeds = [
            self.concepts[concept_id]
            for concept_id in dict.fromkeys(str(item) for item in concept_ids)
            if concept_id in self.concepts
        ]
        selected = list(seeds)
        seen = {item.concept_id for item in selected}
        for concept in seeds:
            for related_id in concept.related_concepts:
                if related_id not in seen:
                    selected.append(self.concepts[related_id])
                    seen.add(related_id)
                if len(selected) >= limit:
                    return tuple(selected[:limit])
        return tuple(selected[:limit])


@lru_cache(maxsize=1)
def load_theory_knowledge_base() -> TheoryKnowledgeBase:
    path = Path(__file__).with_name("knowledge") / "semiconductor_theory.json"
    return TheoryKnowledgeBase.load(path)
