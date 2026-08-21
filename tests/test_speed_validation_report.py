from __future__ import annotations

import pytest

from tools.build_speed_validation_report import calculate_speed_results


def test_calculate_speed_results_keeps_comparison_boundaries_distinct() -> None:
    tcad = {
        "elapsed_seconds": {"median": 100.0, "p95": 300.0},
        "representative_case_timings": {
            "short": {"case_id": "short-case", "elapsed_sec": 80.0},
            "default": {"case_id": "default-case", "elapsed_sec": 100.0},
            "long": {"case_id": "long-case", "elapsed_sec": 160.0},
        },
    }
    ai = {
        "combined_representative_statistics_ms": {
            "simulation_to_result": {"median": 500.0, "p95": 1000.0},
            "user_end_to_end": {"median": 800.0, "p95": 1200.0},
        },
        "per_condition_primary_median_ms": {
            "short": 400.0,
            "default": 500.0,
            "long": 800.0,
        },
    }

    result = calculate_speed_results(tcad, ai)

    assert result["ai_primary_median_s"] == pytest.approx(0.5)
    assert result["ai_e2e_median_s"] == pytest.approx(0.8)
    assert result["primary_median_speedup"] == pytest.approx(200.0)
    assert result["end_to_end_median_speedup"] == pytest.approx(125.0)
    assert result["conservative_speedup"] == pytest.approx(100.0)
    assert result["p95_to_p95_ratio"] == pytest.approx(300.0)
    assert result["paired_representative_cases"]["short"]["speedup"] == pytest.approx(200.0)
    assert result["paired_representative_cases"]["default"]["speedup"] == pytest.approx(200.0)
    assert result["paired_representative_cases"]["long"]["speedup"] == pytest.approx(200.0)
