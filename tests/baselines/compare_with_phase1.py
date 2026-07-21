"""Re-run real models and summarize structural progress from the frozen baseline."""

from __future__ import annotations

import json
import argparse
import sys
from pathlib import Path

from generate_phase1_baseline import generate


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--show-mock", action="store_true")
    args = parser.parse_args()
    baseline_path = Path(__file__).with_name("phase1_explanation_baseline.json")
    before = json.loads(baseline_path.read_text(encoding="utf-8"))
    current = generate()
    for name in before["cases"]:
        old = before["cases"][name]
        new = current["cases"][name]
        interpretation = new["payload"].get("interpretation", {})
        overall = interpretation.get("overall_assessment") or {}
        patterns = [item["result_pattern"] for item in overall.get("comparison_results", [])]
        print(
            name,
            "old_mock=" + str({key: len(old["mock_response"][key]) for key in old["mock_response"]}),
            "status=" + str(interpretation.get("status")),
            "summaries=" + str(len(interpretation.get("performance_summaries", []))),
            "effects=" + str(len(interpretation.get("parameter_effects", []))),
            "interactions=" + str(len(interpretation.get("parameter_interactions", []))),
            "tradeoffs=" + str(len(interpretation.get("observed_tradeoffs", []))),
            "patterns=" + str(patterns),
        )
        if args.show_mock and name.startswith("curve_"):
            print(json.dumps(new["mock_response"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
