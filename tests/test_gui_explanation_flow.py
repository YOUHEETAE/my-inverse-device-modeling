"""Regression checks for the simplified explanation provider controls."""

from frontend.visualization.explanation_panel import EXPLANATION_PROVIDERS


def test_gui_exposes_only_mock_and_external_llm() -> None:
    assert EXPLANATION_PROVIDERS == ("mock", "external_llm")
