from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from uuid import UUID

from .schemas import LearningSession


class SessionStorageError(RuntimeError):
    pass


class LearningSessionRepository(ABC):
    @abstractmethod
    def save(self, session: LearningSession) -> None:
        raise NotImplementedError

    @abstractmethod
    def load(self, session_id: str) -> LearningSession | None:
        raise NotImplementedError

    @abstractmethod
    def list_sessions(self) -> list[LearningSession]:
        raise NotImplementedError

    @abstractmethod
    def delete(self, session_id: str) -> None:
        raise NotImplementedError


def _copy_session(session: LearningSession) -> LearningSession:
    return LearningSession.from_dict(session.to_dict())


class InMemorySessionRepository(LearningSessionRepository):
    def __init__(self) -> None:
        self._sessions: dict[str, LearningSession] = {}

    def save(self, session: LearningSession) -> None:
        self._sessions[session.session_id] = _copy_session(session)

    def load(self, session_id: str) -> LearningSession | None:
        value = self._sessions.get(session_id)
        return _copy_session(value) if value else None

    def list_sessions(self) -> list[LearningSession]:
        sessions = [_copy_session(item) for item in self._sessions.values()]
        return sorted(sessions, key=lambda item: item.updated_at, reverse=True)

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


class JsonSessionRepository(LearningSessionRepository):
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _path(self, session_id: str) -> Path:
        try:
            normalized = str(UUID(session_id))
        except (TypeError, ValueError, AttributeError) as error:
            raise SessionStorageError("invalid_session_id") from error
        return self.root / f"{normalized}.json"

    def save(self, session: LearningSession) -> None:
        path = self._path(session.session_id)
        temporary = path.with_suffix(".json.tmp")
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            temporary.write_text(
                json.dumps(session.to_dict(), ensure_ascii=False, indent=2, allow_nan=False),
                encoding="utf-8",
            )
            temporary.replace(path)
        except (OSError, TypeError, ValueError) as error:
            raise SessionStorageError("session_write_failed") from error

    def load(self, session_id: str) -> LearningSession | None:
        path = self._path(session_id)
        if not path.exists():
            return None
        try:
            return LearningSession.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
            raise SessionStorageError("session_read_failed") from error

    def list_sessions(self) -> list[LearningSession]:
        if not self.root.exists():
            return []
        sessions = []
        for path in self.root.glob("*.json"):
            sessions.append(self.load(path.stem))
        return sorted(
            (item for item in sessions if item is not None),
            key=lambda item: item.updated_at,
            reverse=True,
        )

    def delete(self, session_id: str) -> None:
        path = self._path(session_id)
        try:
            path.unlink(missing_ok=True)
        except OSError as error:
            raise SessionStorageError("session_delete_failed") from error
