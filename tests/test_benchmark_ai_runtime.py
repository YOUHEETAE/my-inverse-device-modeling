from __future__ import annotations

import csv
from pathlib import Path

import pytest

from tools.benchmark_ai_runtime import load_accepted_conditions, nearest_rank, summarize


def _write_status(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "structure_id",
        "doping_run_id",
        "gate_width",
        "oxide_thickness",
        "bulk_doping",
        "source_doping",
        "drain_doping",
        "LDD_doping",
        "status",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _row(structure: str, doping: str, status: str = "ok") -> dict[str, str]:
    return {
        "structure_id": structure,
        "doping_run_id": doping,
        "gate_width": "2e-5",
        "oxide_thickness": "2e-6",
        "bulk_doping": "1e16",
        "source_doping": "1e20",
        "drain_doping": "1e20",
        "LDD_doping": "1e18",
        "status": status,
    }


def test_load_accepted_conditions_merges_retry_without_duplicate(tmp_path: Path) -> None:
    primary = tmp_path / "primary.csv"
    retry = tmp_path / "retry.csv"
    _write_status(primary, [_row("L200T20", "A"), _row("L200T20", "B", "failed")])
    _write_status(retry, [_row("L200T20", "B"), _row("L200T20", "A")])

    conditions = load_accepted_conditions(primary, retry)

    assert [condition.case_id for condition in conditions] == ["L200T20|A", "L200T20|B"]
    assert conditions[0].L == pytest.approx(200.0)
    assert conditions[0].T == pytest.approx(20.0)


def test_nearest_rank_and_summary_use_explicit_percentiles() -> None:
    values = list(range(1, 21))

    assert nearest_rank(values, 0.90) == 18
    assert nearest_rank(values, 0.95) == 19
    result = summarize(values)
    assert result["median_ms"] == 10.5
    assert result["p90_ms"] == 18
    assert result["p95_ms"] == 19


@pytest.mark.parametrize("percentile", [0.0, -0.1, 1.1])
def test_nearest_rank_rejects_invalid_percentiles(percentile: float) -> None:
    with pytest.raises(ValueError):
        nearest_rank([1.0], percentile)
