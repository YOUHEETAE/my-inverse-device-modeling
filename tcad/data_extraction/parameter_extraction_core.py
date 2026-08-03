from __future__ import annotations

import numpy as np


DIBL_REFERENCE_CURRENT_MA_PER_UM = 1e-4
LOW_DRAIN_BIAS_V = 0.05
HIGH_DRAIN_BIAS_V = 1.5

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

# Authoritative, user-facing extraction contract. Learning and explanation
# layers import this instead of maintaining a second set of bias definitions.
PARAMETER_EXTRACTION_DEFINITIONS = {
    "vth_low_v": {
        "label": "Vth (low Vd)",
        "unit": "V",
        "source_curve": "Id–Vg at Vd=0.05 V",
        "method": "maximum-gm tangent intercept with the Vd/2 correction",
        "learning_explanation": (
            "이 프로젝트의 low-Vd Vth는 Vd=0.05 V Id–Vg 곡선에서 "
            "최대 gm 접선 절편을 구한 뒤 Vd/2 보정을 적용한 값이다."
        ),
    },
    "vth_high_v": {
        "label": "Vth (high Vd)",
        "unit": "V",
        "source_curve": "Id–Vg at Vd=1.5 V",
        "method": "maximum-gm tangent intercept",
        "learning_explanation": (
            "이 프로젝트의 high-Vd Vth는 Vd=1.5 V Id–Vg 곡선에서 "
            "최대 gm 접선 절편으로 추출한 값이다."
        ),
    },
    "ion_ma_per_um": {
        "label": "Ion",
        "unit": "mA/µm",
        "source_curve": "Id–Vd at Vg=3.0 V",
        "method": "absolute Drain current at Vd=3.0 V",
        "learning_explanation": (
            "이 프로젝트의 Ion은 Vg=3.0 V로 켠 Id–Vd 곡선에서 "
            "Vd=3.0 V일 때의 |Id|이다."
        ),
    },
    "ioff_ma_per_um": {
        "label": "Ioff",
        "unit": "mA/µm",
        "source_curve": "Id–Vg at Vd=1.5 V",
        "method": "absolute Drain current at Vg=0 V",
        "learning_explanation": (
            "이 프로젝트의 Ioff는 Vd=1.5 V Id–Vg 곡선에서 "
            "Vg=0 V일 때의 |Id|이다."
        ),
    },
    "ss_mv_per_dec": {
        "label": "SS",
        "unit": "mV/dec",
        "source_curve": "Id–Vg at Vd=0.05 V",
        "method": (
            "minimum valid 9-point semilog slope within Vth-0.4 V to Vth "
            "(at least 0.2 decade and R²≥0.95)"
        ),
        "learning_explanation": (
            "이 프로젝트의 SS는 Vd=0.05 V Id–Vg 곡선에서 Vth 아래 "
            "0.4 V 범위의 유효한 9점 semilog 구간 중 가장 작은 기울기 값으로 추출한다."
        ),
    },
    "dibl_gm_v_per_v": {
        "label": "DIBL",
        "unit": "V/V",
        "source_curve": "Id–Vg at Vd=0.05 V and 1.5 V",
        "method": (
            "absolute constant-current Vth difference at 1e-4 mA/µm, "
            "divided by 1.45 V"
        ),
        "learning_explanation": (
            "이 프로젝트의 DIBL은 Vd=0.05 V와 1.5 V에서 "
            "|Id|=1e-4 mA/µm가 되는 constant-current Vth 차이를 "
            "Drain bias 차이 1.45 V로 나눈 값이다."
        ),
    },
    "gm_max_ms_per_um": {
        "label": "gm max",
        "unit": "mS/µm",
        "source_curve": "Id–Vg at Vd=0.05 V",
        "method": "maximum numerical dId/dVg",
        "learning_explanation": (
            "이 프로젝트의 gm max는 Vd=0.05 V Id–Vg 곡선에서 "
            "수치 미분한 dId/dVg의 최댓값이다."
        ),
    },
    "gds_ms_per_um": {
        "label": "gds",
        "unit": "mS/µm",
        "source_curve": "Id–Vd at Vg=1.5 V",
        "method": "linear-fit slope over Vd=2.5–3.0 V",
        "learning_explanation": (
            "이 프로젝트의 gds는 Vg=1.5 V Id–Vd 곡선의 "
            "Vd=2.5–3.0 V 구간을 선형 적합한 기울기이다."
        ),
    },
    "ron_kohm_um": {
        "label": "Ron",
        "unit": "kΩ·µm",
        "source_curve": "Id–Vd at Vg=3.0 V",
        "method": "inverse linear-fit conductance over Vd=0–0.3 V",
        "learning_explanation": (
            "이 프로젝트의 Ron은 Vg=3.0 V Id–Vd 곡선의 "
            "Vd=0–0.3 V 선형 적합 conductance의 역수이다."
        ),
    },
    "lambda_per_v": {
        "label": "λ",
        "unit": "1/V",
        "source_curve": "Id–Vd at Vg=1.5 V",
        "method": "gds divided by fitted saturation current at Vd=2.75 V",
        "learning_explanation": (
            "이 프로젝트의 λ는 추출된 gds를 Vd=2.75 V에서의 "
            "선형 적합 saturation current로 나눈 값이다."
        ),
    },
}


def extract_parameters(
    idvd: dict[str, tuple[np.ndarray, np.ndarray]],
    idvg: dict[str, tuple[np.ndarray, np.ndarray]],
) -> dict[str, float]:
    """Extract one device's electrical parameters from the four standard curves."""
    vg_low, id_low = _curve(idvg, "IDVG_VD0P05")
    vg_high, id_high = _curve(idvg, "IDVG_VD1P5")
    vd_on, id_on = _curve(idvd, "IDVD_VG3P0")
    vd_saturation, id_saturation = _curve(idvd, "IDVD_VG1P5")

    # The linear-region gm-tangent intercept requires the usual Vd/2
    # correction.  The high-Vd curve is kept on the existing gm-max method.
    vth_low_raw, gm_max = _gm_tangent(vg_low, id_low)
    vth_low = vth_low_raw + LOW_DRAIN_BIAS_V / 2.0
    vth_high, _ = _gm_tangent(vg_high, id_high)
    vth_cc_low = _constant_current_threshold(
        vg_low, id_low, DIBL_REFERENCE_CURRENT_MA_PER_UM
    )
    vth_cc_high = _constant_current_threshold(
        vg_high, id_high, DIBL_REFERENCE_CURRENT_MA_PER_UM
    )
    ion = abs(_at(vd_on, id_on, 3.0))
    ioff = abs(_at(vg_high, id_high, 0.0))
    ss = _subthreshold_swing(vg_low, id_low, vth_low)
    dibl = abs(vth_cc_low - vth_cc_high) / (
        HIGH_DRAIN_BIAS_V - LOW_DRAIN_BIAS_V
    )
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


def _constant_current_threshold(
    x: np.ndarray,
    current: np.ndarray,
    reference_current_ma_per_um: float,
) -> float:
    """Return Vg at the requested |Id| using semilog interpolation."""
    if not np.isfinite(reference_current_ma_per_um) or reference_current_ma_per_um <= 0:
        raise ValueError("DIBL reference current must be a positive finite value")

    x = np.asarray(x, dtype=float)
    magnitude = np.abs(np.asarray(current, dtype=float))
    valid = np.isfinite(x) & np.isfinite(magnitude) & (magnitude > 0)
    x = x[valid]
    magnitude = magnitude[valid]
    if len(x) < 2:
        raise ValueError("not enough finite positive-current points for constant-current Vth")

    order = np.argsort(x)
    x = x[order]
    magnitude = magnitude[order]
    target_log_current = float(np.log10(reference_current_ma_per_um))
    log_current = np.log10(magnitude)

    exact = np.flatnonzero(np.isclose(log_current, target_log_current, rtol=0.0, atol=1e-12))
    if len(exact):
        return float(x[int(exact[0])])

    crossings = np.flatnonzero(
        (log_current[:-1] - target_log_current)
        * (log_current[1:] - target_log_current)
        < 0
    )
    if not len(crossings):
        raise ValueError(
            "DIBL reference current "
            f"{reference_current_ma_per_um:g} mA/um is outside the Id-Vg curve range"
        )

    index = int(crossings[0])
    fraction = (
        (target_log_current - log_current[index])
        / (log_current[index + 1] - log_current[index])
    )
    return float(x[index] + fraction * (x[index + 1] - x[index]))


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
