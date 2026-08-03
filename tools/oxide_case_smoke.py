from __future__ import annotations

import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.learning import load_topic
from backend.learning.experiment_runner import LearningExperimentRunner


def main() -> int:
    topic = load_topic("oxide_gate_control")
    result = LearningExperimentRunner.from_repository(
        REPOSITORY_ROOT
    ).execute(topic)
    context = result.learning_context
    expected_electrical = {
        "gm_max": "increase",
        "ss": "decrease",
        "ioff": "increase",
    }
    electrical = {
        name: context.electrical_changes[name].direction
        for name in expected_electrical
    }
    electric_field_observations = [
        item for item in context.field_observations
        if item.field_display == "electric_field"
    ]
    drain_field_decreased = any(
        item.region == "drain_near_surface"
        and item.observation == "decrease"
        for item in electric_field_observations
    )
    report = {
        "topic_id": topic.topic_id,
        "changed_parameter": context.experiment.get("changed_parameter"),
        "baseline_tox_nm": topic.baseline_conditions["T"],
        "comparison_tox_nm": topic.comparison_conditions["T"],
        "analysis_status": context.analysis_status,
        "electrical_directions": electrical,
        "electric_field_observation_count": len(electric_field_observations),
        "drain_field_decreased": drain_field_decreased,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    passed = (
        context.experiment.get("changed_parameter") == "T"
        and electrical == expected_electrical
        and bool(electric_field_observations)
        and drain_field_decreased
        and context.analysis_status in {"complete", "partial"}
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
