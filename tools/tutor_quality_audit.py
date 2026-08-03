from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.learning import (
    LearningAnalysisContext,
    LearningLLMService,
    TutorAuditScenario,
    load_topic,
    run_tutor_scenarios,
)


DEFAULT_ANALYSIS = (
    REPOSITORY_ROOT
    / "tests"
    / "fixtures"
    / "learning"
    / "sce_channel_length_analysis.json"
)
DEFAULT_SCENARIOS = (
    REPOSITORY_ROOT
    / "tests"
    / "fixtures"
    / "learning"
    / "tutor_quality_scenarios.json"
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the deterministic Case Study tutor quality audit.",
    )
    parser.add_argument("--analysis", type=Path, default=DEFAULT_ANALYSIS)
    parser.add_argument("--scenarios", type=Path, default=DEFAULT_SCENARIOS)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = _arguments()
    analysis_data = json.loads(args.analysis.read_text(encoding="utf-8"))
    scenario_data = json.loads(args.scenarios.read_text(encoding="utf-8"))
    if str(scenario_data.get("schema_version")) != "1.0":
        raise ValueError("unsupported_tutor_audit_scenario_schema")
    topic = load_topic(str(scenario_data["topic_id"]))
    context = LearningAnalysisContext.from_dict(
        analysis_data["learning_context"]
    )
    scenarios = tuple(
        TutorAuditScenario.from_dict(item)
        for item in scenario_data.get("scenarios", [])
    )
    report = run_tutor_scenarios(
        topic=topic,
        context=context,
        scenarios=scenarios,
        service=LearningLLMService(),
        learner_profile=dict(scenario_data.get("learner_profile", {})),
    )
    rendered = json.dumps(
        report.to_dict(),
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    )
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
