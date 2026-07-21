from __future__ import annotations

from typing import Protocol


class ExplanationProvider(Protocol):
    name: str
    model: str

    def generate(self, system_prompt: str, user_prompt: str, payload: dict) -> dict:
        ...
