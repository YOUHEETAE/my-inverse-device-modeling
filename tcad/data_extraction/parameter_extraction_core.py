from __future__ import annotations

import numpy as np


PARAMETER_NAMES = (
    "vth_low_v",
    "vth_high_v",
    "ion_ma_per_um",
    "ioff_ma_per_um",
    "ss_mv_per_dec",
    "dibl_gm_v_per_v",
    "gm_max_ms_per_um",
    "gds_ms_per_um",
    "ron_kohm_um",
    "lambda_per_v",
)


def extract_parameters(
    idvd: dict[str, tuple[np.ndarray, np.ndarray]],
    idvg: dict[str, tuple[np.ndarray, np.ndarray]],
) -> dict[str, float]:
    """Extract one device's electrical parameters from the four standard curves."""
    vg_low, id_low = _curve(idvg, "IDVG_VD0P05")
    vg_high, id_high = _curve(idvg, "IDVG_VD1P5")
    vd_on, id_on = _curve(idvd, "IDVD_VG3P0")
    vd_saturation, id_saturation = _curve(idvd, "IDVD_VG1P5")

    vth_low, gm_max = _gm_tangent(vg_low, id_low)
    vth_high, _ = _gm_tangent(vg_high, id_high)
    ion = abs(_at(vd_on, id_on, 3.0))
    ioff = abs(_at(vg_high, id_high, 0.0))
    ss = _subthreshold_swing(vg_low, id_low, vth_low)
    dibl = (vth_low - vth_high) / (1.5 - 0.05)
    gds, gds_intercept = _linear_slope(
        vd_saturation, id_saturation, 2.5, 3.0, "Vg=1.5 V high-Vd"
    )
    linear_conductance, _ = _linear_slope(vd_on, id_on, 0.0, 0.3, "linear")
    if linear_conductance <= 0:
        raise ValueError("linear-region conductance is not positive")
    ron = 1.0 / linear_conductance
    saturation_current = gds * 2.75 + gds_intercept
    if saturation_current == 0:
        raise ValueError("saturation current is zero")
    return {
        "vth_low_v": vth_low,
        "vth_high_v": vth_high,
        "ion_ma_per_um": ion,
        "ioff_ma_per_um": ioff,
        "ss_mv_per_dec": ss,
        "dibl_gm_v_per_v": dibl,
        "gm_max_ms_per_um": gm_max,
        "gds_ms_per_um": gds,
        "ron_kohm_um": ron,
        "lambda_per_v": gds / saturation_current,
    }


def _curve(
    groups: dict[str, tuple[np.ndarray, np.ndarray]], tag: str
) -> tuple[np.ndarray, np.ndarray]:
    if tag not in groups:
        raise ValueError(f"missing curve {tag}")
    x, current = groups[tag]
    if len(x) < 3:
        raise ValueError(f"{tag} has only {len(x)} point(s)")
    return x, current


def _at(x: np.ndarray, y: np.ndarray, target: float) -> float:
    if target < x.min() or target > x.max():
        raise ValueError(f"target {target:g} V is outside [{x.min():g}, {x.max():g}] V")
    return float(np.interp(target, x, y))


def _gm_tangent(x: np.ndarray, current: np.ndarray) -> tuple[float, float]:
    gm = np.gradient(current, x)
    index = int(np.nanargmax(gm))
    gm_max = float(gm[index])
    if not np.isfinite(gm_max) or gm_max <= 0:
        raise ValueError("gm maximum is not positive")
    return float(x[index] - current[index] / gm_max), gm_max


def _subthreshold_swing(
    x: np.ndarray,
    current: np.ndarray,
    vth: float,
    window_points: int = 9,
    below_vth_window_v: float = 0.4,
    min_decades: float = 0.2,
    min_r_squared: float = 0.95,
) -> float:
    log_current = np.log10(np.maximum(np.abs(current), 1e-30))
    mask = (
        (x >= vth - below_vth_window_v)
        & (x <= vth)
        & np.isfinite(x)
        & np.isfinite(log_current)
    )
    sub_x = x[mask]
    sub_log_current = log_current[mask]
    if len(sub_x) < window_points:
        raise ValueError(
            f"not enough points for a {window_points}-point SS fit in "
            f"Vth-{below_vth_window_v:g} V..Vth"
        )
    candidates: list[float] = []
    for start in range(len(sub_x) - window_points + 1):
        window_x = sub_x[start : start + window_points]
        window_log_current = sub_log_current[start : start + window_points]
        if float(np.ptp(window_log_current)) < min_decades:
            continue
        slope, intercept = np.polyfit(window_x, window_log_current, 1)
        if not np.isfinite(slope) or slope <= 0:
            continue
        fitted = slope * window_x + intercept
        residual = float(np.sum((window_log_current - fitted) ** 2))
        total = float(np.sum((window_log_current - np.mean(window_log_current)) ** 2))
        r_squared = 1.0 - residual / total if total > 0 else 0.0
        if r_squared >= min_r_squared:
            candidates.append(1000.0 / float(slope))
    if not candidates:
        raise ValueError(
            f"no {window_points}-point SS window spans {min_decades:g} decade(s) "
            f"with R^2 >= {min_r_squared:g} in Vth-{below_vth_window_v:g} V..Vth"
        )
    return min(candidates)


def _linear_slope(
    x: np.ndarray, y: np.ndarray, low: float, high: float, name: str
) -> tuple[float, float]:
    mask = (x >= low) & (x <= high)
    if np.count_nonzero(mask) < 3:
        raise ValueError(f"not enough {name} points in {low:g}..{high:g} V")
    slope, intercept = np.polyfit(x[mask], y[mask], 1)
    return float(slope), float(intercept)
