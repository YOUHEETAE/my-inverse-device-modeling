from frontend.visualization.analysis_context import (
    build_analysis_context_status,
    ordered_analysis_indices,
)


def _config(length: str, tox: str = "10") -> dict[str, str]:
    return {
        "L": length,
        "T": tox,
        "B": "1e16",
        "SD": "1e20",
        "LDD": "1e18",
    }


def test_preferred_baseline_is_first_in_analysis_order() -> None:
    assert ordered_analysis_indices({0, 1, 2}, 1) == (1, 0, 2)
    assert ordered_analysis_indices({0, 2}, 1) == (0, 2)


def test_sweep_status_exposes_scope_baseline_and_representative_pair() -> None:
    status = build_analysis_context_status(
        {0, 1, 2},
        [_config("700"), _config("500"), _config("300")],
        preferred_baseline_index=1,
    )
    assert status is not None
    assert status.badge == "SWEEP"
    assert status.baseline_label == "Curve 2"
    assert "L 300 → 500 → 700 nm" in status.scope_label
    assert status.representative_label == "Curve 3 ↔ Curve 1"


def test_compound_status_names_all_changed_parameters() -> None:
    status = build_analysis_context_status(
        {0, 1},
        [_config("700"), _config("400", tox="15")],
    )
    assert status is not None
    assert status.badge == "COMPOUND"
    assert "L" in status.scope_label
    assert "Tox" in status.scope_label
