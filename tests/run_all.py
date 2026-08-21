"""Dependency-free runner for the repository's plain-function test suite."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MODULES = (
    "tests.test_analysis_payload_v3", "tests.test_relationships", "tests.test_selection",
    "tests.test_comparison_planner",
    "tests.test_iv_renderer", "tests.test_field_renderer", "tests.test_field_specific_renderer",
    "tests.test_safety", "tests.test_provider_integration", "tests.test_final_audit",
    "tests.test_interpretation_contract",
    "tests.test_curve_interpretation",
    "tests.test_field_geometry",
    "tests.test_field_interpretation",
    "tests.test_field_conclusions",
    "tests.test_field_structured_renderer",
    "tests.test_language_polish",
    "tests.test_iv_chat",
    "tests.test_field_chat",
    "tests.test_gui_explanation_flow",
    "tests.test_learning_foundation",
    "tests.test_learning_analysis_adapter",
    "tests.test_learning_experiment_runner",
    "tests.test_learning_llm_service",
    "tests.test_case_study_ui_contract",
    "tests.test_learning_end_to_end",
    "tests.test_learning_progress",
    "tests.test_oxide_case_learning",
    "tests.test_body_doping_case_learning",
    "tests.test_source_drain_case_learning",
    "tests.test_ldd_case_learning",
    "tests.test_channel_oxide_case_learning",
    "tests.test_junction_design_case_learning",
    "tests.test_integrated_design_case_learning",
    "tests.test_platform_readiness",
    "tests.test_tutor_question_router",
    "tests.test_theory_knowledge",
    "tests.test_case_study_scenarios",
    "tests.test_question_intent_pipeline",
    "tests.test_dialogue_knowledge_layers",
    "tests.test_tutor_quality_audit",
)


def main() -> int:
    passed = 0
    requested = tuple(sys.argv[1:])
    modules = tuple(name if name.startswith("tests.") else f"tests.{name.removesuffix('.py')}" for name in requested) or MODULES
    for module_name in modules:
        module = importlib.import_module(module_name)
        for name in sorted(item for item in dir(module) if item.startswith("test_")):
            getattr(module, name)()
            passed += 1
            print(f"PASS {module_name}::{name}")
    print(f"SUMMARY passed={passed} failed=0 skipped=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
