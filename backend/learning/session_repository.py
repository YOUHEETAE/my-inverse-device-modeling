from __future__ import annotations

import json
import os
import shutil
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

    def consume_recovery_notices(self) -> list[dict[str, str]]:
        return []


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
        self._recovery_notices: list[dict[str, str]] = []

    def _path(self, session_id: str) -> Path:
        try:
            normalized = str(UUID(session_id))
        except (TypeError, ValueError, AttributeError) as error:
            raise SessionStorageError("invalid_session_id") from error
        return self.root / f"{normalized}.json"

    def save(self, session: LearningSession) -> None:
        path = self._path(session.session_id)
        temporary = path.with_suffix(".json.tmp")
        backup = path.with_suffix(".json.bak")
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            content = json.dumps(
                session.to_dict(),
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
            if path.exists():
                try:
                    LearningSession.from_dict(
                        json.loads(path.read_text(encoding="utf-8"))
                    )
                except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
                    pass
                else:
                    shutil.copy2(path, backup)
            self._atomic_write(temporary, path, content)
        except (OSError, TypeError, ValueError) as error:
            raise SessionStorageError("session_write_failed") from error

    def load(self, session_id: str) -> LearningSession | None:
        path = self._path(session_id)
        backup = path.with_suffix(".json.bak")
        if not path.exists() and not backup.exists():
            return None
        try:
            return LearningSession.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
            try:
                recovered = LearningSession.from_dict(
                    json.loads(backup.read_text(encoding="utf-8"))
                )
                content = json.dumps(
                    recovered.to_dict(),
                    ensure_ascii=False,
                    indent=2,
                    allow_nan=False,
                )
                self._atomic_write(
                    path.with_suffix(".json.recovery.tmp"),
                    path,
                    content,
                )
            except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as backup_error:
                raise SessionStorageError("session_read_failed") from backup_error
            self._recovery_notices.append({
                "session_id": recovered.session_id,
                "code": "session_recovered_from_backup",
            })
            return recovered

    def list_sessions(self) -> list[LearningSession]:
        if not self.root.exists():
            return []
        sessions = []
        session_ids = {path.stem for path in self.root.glob("*.json")}
        session_ids.update(
            path.name.removesuffix(".json.bak")
            for path in self.root.glob("*.json.bak")
        )
        for session_id in sorted(session_ids):
            try:
                sessions.append(self.load(session_id))
            except SessionStorageError:
                self._recovery_notices.append({
                    "session_id": session_id,
                    "code": "session_skipped_unrecoverable",
                })
        return sorted(
            (item for item in sessions if item is not None),
            key=lambda item: item.updated_at,
            reverse=True,
        )

    def delete(self, session_id: str) -> None:
        path = self._path(session_id)
        try:
            path.unlink(missing_ok=True)
            path.with_suffix(".json.bak").unlink(missing_ok=True)
            path.with_suffix(".json.tmp").unlink(missing_ok=True)
            path.with_suffix(".json.recovery.tmp").unlink(missing_ok=True)
        except OSError as error:
            raise SessionStorageError("session_delete_failed") from error

    def consume_recovery_notices(self) -> list[dict[str, str]]:
        result = list(self._recovery_notices)
        self._recovery_notices.clear()
        return result

    @staticmethod
    def _atomic_write(temporary: Path, target: Path, content: str) -> None:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
