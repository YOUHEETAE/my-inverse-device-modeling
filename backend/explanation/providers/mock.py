from __future__ import annotations

from ..field_renderer import render_field_explanation
from ..iv_renderer import render_iv_explanation


class MockExplanationProvider:
    """Deterministic renderer that consumes the same Payload v3 as an external LLM."""

    name = "mock"
    model = "deterministic-interpretation-v8"

    def generate(self, system_prompt: str, user_prompt: str, payload: dict) -> dict:
        del system_prompt, user_prompt
        if payload.get("analysis_type", "").startswith("iv_curve_"):
            return render_iv_explanation(payload)
        return render_field_explanation(payload)
