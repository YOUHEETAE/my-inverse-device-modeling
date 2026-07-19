from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class JsonExplanationCache:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._entries: dict[str, dict[str, Any]] = {}
        self.read_failed = False
        self.write_failed = False
        if path and path.is_file():
            try:
                self._entries = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self._entries = {}
                self.read_failed = True

    @staticmethod
    def key(payload: dict, provider: str, model: str, *, prompt_version: str = "1.0", response_schema_version: str = "1.0", renderer_version: str = "1.0") -> str:
        canonical = json.dumps({"payload": payload, "provider": provider, "model": model, "prompt_version": prompt_version,
                                "response_schema_version": response_schema_version, "renderer_version": renderer_version}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def get(self, key: str) -> dict[str, Any] | None:
        value = self._entries.get(key)
        return value if isinstance(value, dict) else None

    def put(self, key: str, value: dict[str, Any]) -> None:
        self._entries[key] = value
        if self.path:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_text(json.dumps(self._entries, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
            except (OSError, TypeError, ValueError):
                self.write_failed = True
