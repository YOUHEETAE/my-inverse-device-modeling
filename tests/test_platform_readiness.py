from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from backend.learning import run_platform_readiness_audit


def test_gui_import_order_does_not_cycle_through_readiness() -> None:
    root = Path(__file__).parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import backend.explanation.iv_chat; "
                "import backend.explanation.field_chat; "
                "import backend.learning.readiness"
            ),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_fast_platform_readiness_audit_is_strict_and_complete() -> None:
    report = run_platform_readiness_audit(
        Path(__file__).parents[1],
        with_models=False,
    )
    assert report.ready
    by_id = {item.check_id: item for item in report.checks}
    assert by_id["topic_catalog"].status == "passed"
    assert by_id["comparison_architecture"].detail[
        "controlled_sweep"
    ]["ordered_values"] == [300.0, 500.0, 700.0]
    assert by_id["comparison_architecture"].detail[
        "compound_pair"
    ]["claim_level"] == "multi_parameter_association"
    assert by_id["runtime_assets"].detail["required_file_count"] == 5
    assert by_id["curriculum_reachability"].detail[
        "reachable_order"
    ] == [
        "sce_channel_length",
        "oxide_gate_control",
        "body_doping_design_window",
        "source_drain_on_state_conduction",
        "ldd_field_resistance_tradeoff",
        "channel_oxide_electrostatic_compensation",
        "source_drain_ldd_junction_engineering",
        "integrated_device_design",
    ]
    assert by_id["session_isolation_round_trip"].status == "passed"
    assert by_id["portfolio_recommendation"].detail == {
        "initial_recommendation": "sce_channel_length",
        "next_recommendation": "oxide_gate_control",
        "total_cases": 8,
    }
    assert by_id["real_model_contracts"].status == "skipped"
    assert by_id["local_tutor_grounding"].status == "skipped"
    assert by_id["multi_condition_context_budget"].status == "skipped"
    assert by_id["external_llm_live"].status == "skipped"
    assert by_id["external_llm_live"].detail["model"] == (
        "openai/gpt-oss-120b"
    )
    assert by_id["external_llm_live"].detail["live_call_spent"] is False
    rendered = json.dumps(
        report.to_dict(), ensure_ascii=False, allow_nan=False
    )
    assert json.loads(rendered)["summary"]["failed_check_ids"] == []
