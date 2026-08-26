"""로컬 실행판의 저장 계층.

배포판에서는 자바 서비스가 학습 세션과 대화를 Postgres에 넣고 뺀다. 실행
파일에는 자바도 데이터베이스도 없고, 로그인도 없다 — 구글 OAuth는 인터넷과
실제 client secret을 요구하는데 그걸 실행 파일에 넣으면 추출된다. 그래서
사용자가 한 명뿐인 로컬 모드로 두고, 같은 자리를 파일로 채운다. 데스크톱
앱이 runtime/learning_sessions/에 하는 것과 같은 방식이다.

사용자가 하나뿐이라 자바에 있던 소유자 검사(user_id 스코프)는 사라진다.
남의 기록을 볼 수 있는 상황 자체가 없다.
"""
from __future__ import annotations

import json
import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

# 얼린 실행 파일 옆에 둔다. %LOCALAPPDATA% 쪽이 관례지만, 심사용으로
# 받아서 한 번 돌려보고 지우는 쓰임이라 폴더째 옮기고 지울 수 있는 편이
# 낫다. 쓰기가 막힌 경로(Program Files 등)에서 실행하면 현재 디렉터리로
# 물러난다.
_DATA_DIR_NAME = "SemiScopeAI-data"

_lock = threading.Lock()


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def data_dir() -> Path:
    for candidate in (_base_dir() / _DATA_DIR_NAME, Path.cwd() / _DATA_DIR_NAME):
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".writable"
            probe.write_text("", encoding="utf-8")
            probe.unlink()
            return candidate
        except OSError:
            continue
    raise RuntimeError("쓸 수 있는 데이터 폴더를 만들지 못했습니다.")


def _sessions_dir() -> Path:
    path = data_dir() / "sessions"
    path.mkdir(exist_ok=True)
    return path


def _threads_dir() -> Path:
    path = data_dir() / "chat"
    path.mkdir(exist_ok=True)
    return path


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _read(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # 손상된 파일 하나 때문에 목록 전체가 열리지 않으면 안 된다.
        return None


def _write(path: Path, payload: dict[str, Any]) -> None:
    # 같은 폴더에 임시 파일을 쓰고 바꿔치기한다. 큰 세션을 쓰는 도중에
    # 창을 닫으면 반쯤 쓰인 JSON이 남아 다음 실행에서 그 기록을 잃는다.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


# ---- 학습 세션 ----------------------------------------------------------


def save_session(session: dict[str, Any]) -> dict[str, Any]:
    session_id = session.get("session_id")
    if not session_id:
        raise ValueError("session_id_missing")
    record = {
        "session_id": str(session_id),
        "topic_id": str(session.get("topic_id", "")),
        "updated_at": _now(),
        "session": session,
    }
    with _lock:
        existing = _read(_sessions_dir() / f"{session_id}.json")
        record["created_at"] = (existing or {}).get("created_at", record["updated_at"])
        _write(_sessions_dir() / f"{session_id}.json", record)
    return session


def load_session(session_id: str) -> dict[str, Any] | None:
    record = _read(_sessions_dir() / f"{session_id}.json")
    return record["session"] if record and "session" in record else None


def all_sessions() -> list[dict[str, Any]]:
    """학습 현황 계산의 재료. Python의 portfolio 엔드포인트가 받는 모양."""
    return [record["session"] for record in _session_records()]


def session_summaries(topic_id: str | None = None) -> list[dict[str, Any]]:
    """목록 화면용. 세션 전체는 수십 KB라 고르는 데 필요한 값만 추린다."""
    summaries = []
    for record in _session_records():
        if topic_id and record.get("topic_id") != topic_id:
            continue
        session = record["session"]
        summaries.append({
            "session_id": record["session_id"],
            "topic_id": record.get("topic_id", ""),
            "display_name": session.get("display_name") or "새 학습 세션",
            "current_step": session.get("current_step") or "",
            "completed": session.get("completed_at") is not None,
            "updated_at": record.get("updated_at", ""),
        })
    return summaries


def _session_records() -> list[dict[str, Any]]:
    records = []
    for path in _sessions_dir().glob("*.json"):
        record = _read(path)
        if record and isinstance(record.get("session"), dict):
            records.append(record)
    records.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return records


def rename_session(session_id: str, display_name: str) -> bool:
    with _lock:
        path = _sessions_dir() / f"{session_id}.json"
        record = _read(path)
        if not record:
            return False
        record["session"]["display_name"] = display_name
        record["updated_at"] = _now()
        _write(path, record)
    return True


def delete_session(session_id: str) -> bool:
    path = _sessions_dir() / f"{session_id}.json"
    try:
        path.unlink()
        return True
    except OSError:
        return False


# ---- 자유질문 대화 ------------------------------------------------------
#
# 자바는 chat_thread / chat_message 두 테이블을 쓰지만, 여기서는 대화 하나가
# 파일 하나다. 한 사람이 쓰는 규모에서 나눠 둘 이유가 없다.


def _thread_path(thread_id: int) -> Path:
    return _threads_dir() / f"{thread_id}.json"


def create_thread(kind: str, device_config: dict[str, Any]) -> int:
    with _lock:
        used = [int(p.stem) for p in _threads_dir().glob("*.json") if p.stem.isdigit()]
        thread_id = max(used, default=0) + 1
        _write(_thread_path(thread_id), {
            "thread_id": thread_id,
            "kind": kind,
            # 첫 질문의 소자 설정을 얼린다. 이후 화면을 바꿔도 대화는 이
            # 설정 기준으로 이어진다 — 배포판과 같은 규칙이다.
            "device_config": device_config,
            "created_at": _now(),
            "updated_at": _now(),
            "messages": [],
        })
    return thread_id


def append_message(
    thread_id: int,
    question: str,
    answer: str,
    source: str,
    intent: str | None,
    intent_checkpoint: dict[str, Any] | None,
) -> int:
    """턴을 저장하고 소모된 턴 수를 돌려준다."""
    with _lock:
        thread = _read(_thread_path(thread_id))
        if not thread:
            raise KeyError(thread_id)
        thread["messages"].append({
            "id": len(thread["messages"]) + 1,
            "question": question,
            "answer": answer,
            "source": source,
            "intent": intent,
            "intent_checkpoint": intent_checkpoint or {},
            "created_at": _now(),
        })
        thread["updated_at"] = _now()
        _write(_thread_path(thread_id), thread)
    return turn_count(thread_id)


def thread(thread_id: int) -> dict[str, Any] | None:
    return _read(_thread_path(thread_id))


def threads(kind: str | None, limit: int) -> list[dict[str, Any]]:
    items = []
    for path in _threads_dir().glob("*.json"):
        record = _read(path)
        if not record or not record.get("messages"):
            # 답을 한 번도 받지 못한 대화는 목록에 띄우지 않는다.
            continue
        if kind and record.get("kind") != kind:
            continue
        items.append(record)
    items.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return items[:limit]


def recent_turns(thread_id: int, count: int) -> list[dict[str, str]]:
    """LLM에 넘길 이력. 실패한 턴은 맥락이 될 수 없어 뺀다."""
    record = _read(_thread_path(thread_id))
    if not record:
        return []
    usable = [m for m in record["messages"] if _counts(m["source"])]
    return [{"question": m["question"], "answer": m["answer"]} for m in usable[-count:]]


def turn_count(thread_id: int) -> int:
    record = _read(_thread_path(thread_id))
    if not record:
        return 0
    return sum(1 for m in record["messages"] if _counts(m["source"]))


def last_checkpoint(thread_id: int) -> dict[str, Any]:
    record = _read(_thread_path(thread_id))
    if not record:
        return {}
    for message in reversed(record["messages"]):
        if message.get("intent_checkpoint"):
            return message["intent_checkpoint"]
    return {}


def _counts(source: str) -> bool:
    # 배포판의 ChatRepository와 같은 규칙 — 외부 오류와 로컬 라우터 응답은
    # 대화 상한에도, 이력에도 넣지 않는다.
    return source not in ("external_error", "local_router")
