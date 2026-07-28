from __future__ import annotations

import numpy as np
import pytest

from tcad.data_extraction import parameter_extraction_core as extraction


def test_constant_current_threshold_interpolates_on_log_current() -> None:
    vg = np.array([0.0, 0.2, 0.4])
    current = np.array([1e-8, 1e-5, 1e-2])

    threshold = extraction._constant_current_threshold(vg, current, 1e-4)

    assert threshold == pytest.approx(0.2666666667)


def test_extraction_corrects_low_vth_and_uses_constant_current_dibl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vg = np.array([0.0, 0.5, 1.0])
    low_current = np.array([1e-8, 1e-4, 1e-2])
    high_current = np.array([1e-6, 1e-3, 1e-1])
    vd = np.linspace(0.0, 3.0, 31)

    gm_results = iter(((0.4, 2.0), (0.2, 3.0)))
    monkeypatch.setattr(extraction, "_gm_tangent", lambda _x, _y: next(gm_results))
    monkeypatch.setattr(extraction, "_subthreshold_swing", lambda _x, _y, _vth: 80.0)

    values = extraction.extract_parameters(
        {
            "IDVD_VG1P5": (vd, 0.1 + 0.05 * vd),
            "IDVD_VG3P0": (vd, 0.2 + 0.2 * vd),
        },
        {
            "IDVG_VD0P05": (vg, low_current),
            "IDVG_VD1P5": (vg, high_current),
        },
    )

    vth_cc_low = 0.5
    vth_cc_high = 1.0 / 3.0
    assert values["vth_low_v"] == pytest.approx(0.425)
    assert values["vth_high_v"] == pytest.approx(0.2)
    assert values["dibl_gm_v_per_v"] == pytest.approx(
        abs(vth_cc_low - vth_cc_high) / 1.45
    )
