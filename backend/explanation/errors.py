from __future__ import annotations

from typing import Any, Iterable


_STAGE_LABELS = {
    "python_analysis": "Python 관찰값·비교 분석",
    "deterministic_draft": "Python 결정론적 초안 생성",
    "deterministic_draft_validation": "Python 결정론적 초안 검증",
    "polish_package_build": "LLM 문장 교정 입력 구성",
    "llm_response_validation": "Groq 문장 교정 응답 검증",
}


class ExplanationPipelineError(RuntimeError):
    """Failure annotated with its actual automatic-explanation pipeline stage."""

    def __init__(
        self,
        stage: str,
        code: str,
        *,
        retryable: bool,
        diagnostics: Iterable[dict[str, Any]] = (),
        first_validation_code: str | None = None,
    ) -> None:
        super().__init__(code)
        self.stage = stage
        self.code = code
        self.retryable = retryable
        self.diagnostics = tuple(
            dict(item) for item in diagnostics if isinstance(item, dict)
        )
        self.first_validation_code = first_validation_code

    @property
    def stage_label(self) -> str:
        return _STAGE_LABELS.get(self.stage, self.stage)

    @property
    def is_local(self) -> bool:
        return self.stage != "llm_response_validation"
