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
    "tests.test_iv_renderer", "tests.test_field_renderer", "tests.test_field_specific_renderer",
    "tests.test_safety", "tests.test_provider_integration", "tests.test_staged_explanation", "tests.test_final_audit",
)


def main() -> int:
    passed = 0
    for module_name in MODULES:
        module = importlib.import_module(module_name)
        for name in sorted(item for item in dir(module) if item.startswith("test_")):
            getattr(module, name)()
            passed += 1
            print(f"PASS {module_name}::{name}")
    print(f"SUMMARY passed={passed} failed=0 skipped=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
