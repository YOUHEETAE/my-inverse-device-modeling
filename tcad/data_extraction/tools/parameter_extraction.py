from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np


OUTPUT_COLUMNS = (
    "structure_id",
    "doping_run_id",
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
    "extraction_status",
    "error",
)


@dataclass(frozen=True)
class CurveFiles:
    stem: str
    idvd: Path
    idvg: Path


def _default_dataset() -> Path:
    return Path(__file__).resolve().parents[1] / "dataset"


def _parse_args() -> argparse.Namespace:
    dataset = _default_dataset()
    parser = argparse.ArgumentParser(description="Extract MOSFET parameters from all IdVd/IdVg CSV pairs.")
    parser.add_argument("--dataset-dir", type=Path, default=dataset)
    parser.add_argument(
        "--output",
        type=Path,
        default=dataset / "device_parameters.csv",
        help="Combined output CSV",
    )
    return parser.parse_args()


def _discover(dataset: Path) -> list[CurveFiles]:
    idvd = {path.stem.removesuffix("_IdVd"): path for path in dataset.glob("*_IdVd.csv")}
    idvg = {path.stem.removesuffix("_IdVg"): path for path in dataset.glob("*_IdVg.csv")}
    return [CurveFiles(stem, idvd[stem], idvg[stem]) for stem in sorted(idvd.keys() & idvg.keys())]


def _read_groups(path: Path) -> tuple[str, str, dict[str, tuple[np.ndarray, np.ndarray]]]:
    groups: dict[str, list[tuple[float, float]]] = {}
    structure_id = ""
    doping_run_id = ""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            structure_id = (row.get("structure_id") or structure_id).strip()
            doping_run_id = (row.get("doping_run_id") or doping_run_id).strip()
            tag = (row.get("curve_tag") or "").strip()
            x_name = "gate_v" if tag.startswith("IDVG") else "drain_v"
            groups.setdefault(tag, []).append((float(row[x_name]), float(row["drain_current"])))

    arrays: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for tag, points in groups.items():
        points.sort(key=lambda point: point[0])
        arrays[tag] = (
            np.asarray([point[0] for point in points], dtype=float),
            np.asarray([point[1] for point in points], dtype=float),
        )
    return structure_id, doping_run_id, arrays


def _curve(groups: dict[str, tuple[np.ndarray, np.ndarray]], tag: str) -> tuple[np.ndarray, np.ndarray]:
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
    vth = float(x[index] - current[index] / gm_max)
    return vth, gm_max


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


def _linear_slope(x: np.ndarray, y: np.ndarray, low: float, high: float, name: str) -> tuple[float, float]:
    mask = (x >= low) & (x <= high)
    if np.count_nonzero(mask) < 3:
        raise ValueError(f"not enough {name} points in {low:g}..{high:g} V")
    slope, intercept = np.polyfit(x[mask], y[mask], 1)
    return float(slope), float(intercept)


def _format(value: float) -> str:
    return f"{value:.12e}"


def _extract(files: CurveFiles) -> dict[str, str]:
    structure_id, doping_run_id, idvd = _read_groups(files.idvd)
    vg_structure, vg_doping, idvg = _read_groups(files.idvg)
    structure_id = structure_id or vg_structure
    doping_run_id = doping_run_id or vg_doping
    base = {"structure_id": structure_id, "doping_run_id": doping_run_id}

    try:
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
            vd_saturation,
            id_saturation,
            2.5,
            3.0,
            "Vg=1.5 V high-Vd",
        )
        linear_conductance, _ = _linear_slope(vd_on, id_on, 0.0, 0.3, "linear")
        if linear_conductance <= 0:
            raise ValueError("linear-region conductance is not positive")
        ron = 1.0 / linear_conductance
        saturation_midpoint = 2.75
        saturation_current = gds * saturation_midpoint + gds_intercept
        if saturation_current == 0:
            raise ValueError("saturation current is zero")
        clm_lambda = gds / saturation_current

        return {
            **base,
            "vth_low_v": _format(vth_low),
            "vth_high_v": _format(vth_high),
            "ion_ma_per_um": _format(ion),
            "ioff_ma_per_um": _format(ioff),
            "ss_mv_per_dec": _format(ss),
            "dibl_gm_v_per_v": _format(dibl),
            "gm_max_ms_per_um": _format(gm_max),
            "gds_ms_per_um": _format(gds),
            "ron_kohm_um": _format(ron),
            "lambda_per_v": _format(clm_lambda),
            "extraction_status": "ok",
            "error": "",
        }
    except (KeyError, ValueError, FloatingPointError) as exc:
        return {**base, "extraction_status": "failed", "error": str(exc)}


def main() -> None:
    args = _parse_args()
    files = _discover(args.dataset_dir.resolve())
    if not files:
        raise FileNotFoundError(f"No IdVd/IdVg CSV pairs found in {args.dataset_dir}")

    rows = [_extract(curve_files) for curve_files in files]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    ok_count = sum(row["extraction_status"] == "ok" for row in rows)
    print(f"Saved: {args.output.resolve()}")
    print(f"Extracted: {ok_count}/{len(rows)} | failed: {len(rows) - ok_count}")


if __name__ == "__main__":
    main()
