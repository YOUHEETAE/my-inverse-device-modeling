from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np

from result_types import PNResult


DATA_DIR = Path(__file__).resolve().parent / "precomputed_data"


class Dataset:
    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        self.data_dir = data_dir
        manifest_path = data_dir / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(
                f"Required precomputed dataset not found: {manifest_path}"
            )
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.dopings = tuple(float(value) for value in self.manifest["dopings"])
        self.biases = tuple(float(value) for value in self.manifest["biases"])
        self._cases = {
            (
                float(case["acceptors"]),
                float(case["donors"]),
                float(case["bias"]),
            ): case
            for case in self.manifest["cases"]
            if case["status"] == "ok"
        }
        self._band_limit_cache: dict[tuple[float, float], tuple[float, float]] = {}
        self._global_line_limits: dict[str, tuple[float, float]] | None = None

    def _read_payload(self, case: dict) -> dict:
        with gzip.open(self.data_dir / case["file"], "rt", encoding="utf-8") as stream:
            return json.load(stream)

    def load(self, acceptors: float, donors: float, bias: float) -> PNResult:
        key = (acceptors, donors, bias)
        case = self._cases.get(key)
        if case is None:
            raise KeyError(f"No saved result for NA={acceptors:g}, ND={donors:g}, V={bias:g}")
        payload = self._read_payload(case)
        array = lambda name: np.asarray(payload[name], dtype=float)
        iv_cases = [
            self._cases[(acceptors, donors, voltage)]
            for voltage in self.biases
            if (acceptors, donors, voltage) in self._cases
        ]
        return PNResult(
            x_um=array("x_um"),
            y_um=array("y_um"),
            net_doping=array("net_doping"),
            potential=array("potential"),
            electrons=array("electrons"),
            holes=array("holes"),
            electric_field=array("electric_field"),
            electric_field_x=array("electric_field_x"),
            voltages=np.asarray([case["bias"] for case in iv_cases], dtype=float),
            currents=np.asarray([case["current"] for case in iv_cases], dtype=float),
            selected_bias=bias,
        )

    def band_energy_limits(
        self, acceptors: float, donors: float
    ) -> tuple[float, float]:
        """Return one fixed energy scale for all biases of a doping pair."""
        key = (acceptors, donors)
        cached = self._band_limit_cache.get(key)
        if cached is not None:
            return cached

        energy_min = float("inf")
        energy_max = float("-inf")
        band_gap = 1.12
        for bias in self.biases:
            case = self._cases.get((acceptors, donors, bias))
            if case is None:
                continue
            payload = self._read_payload(case)
            x = np.asarray(payload["x_um"], dtype=float)
            y = np.asarray(payload["y_um"], dtype=float)
            potential = np.asarray(payload["potential"], dtype=float)
            target_y = 0.5 * (float(np.min(y)) + float(np.max(y)))
            nearest_y = float(y[int(np.argmin(np.abs(y - target_y)))])
            indices = np.flatnonzero(
                np.isclose(y, nearest_y, rtol=0.0, atol=1e-10)
            )
            indices = indices[np.argsort(x[indices])]
            conduction = -potential[indices]
            # The n-side endpoint is the shared relative-energy reference.
            conduction = conduction - conduction[-1]
            energy_max = max(energy_max, float(np.max(conduction)))
            energy_min = min(energy_min, float(np.min(conduction - band_gap)))

        if not np.isfinite(energy_min) or not np.isfinite(energy_max):
            return (-1.25, 0.25)
        span = max(energy_max - energy_min, band_gap)
        padding = 0.08 * span
        limits = (energy_min - padding, energy_max + padding)
        self._band_limit_cache[key] = limits
        return limits

    def line_plot_limits(self) -> dict[str, tuple[float, float]]:
        """Return scales fixed across every doping pair and every bias."""
        if self._global_line_limits is not None:
            return self._global_line_limits

        q = 1.602176634e-19
        carrier_min = float("inf")
        carrier_max = float("-inf")
        charge_abs_max = 0.0
        field_abs_max = 0.0
        potential_min = float("inf")
        potential_max = float("-inf")

        for acceptors in self.dopings:
            for donors in self.dopings:
                for bias in self.biases:
                    case = self._cases.get((acceptors, donors, bias))
                    if case is None:
                        continue
                    payload = self._read_payload(case)
                    x = np.asarray(payload["x_um"], dtype=float)
                    y = np.asarray(payload["y_um"], dtype=float)
                    target_y = 0.5 * (float(np.min(y)) + float(np.max(y)))
                    nearest_y = float(y[int(np.argmin(np.abs(y - target_y)))])
                    indices = np.flatnonzero(
                        np.isclose(y, nearest_y, rtol=0.0, atol=1e-10)
                    )
                    indices = indices[np.argsort(x[indices])]

                    electrons = np.maximum(
                        np.asarray(payload["electrons"], dtype=float)[indices], 1.0
                    )
                    holes = np.maximum(
                        np.asarray(payload["holes"], dtype=float)[indices], 1.0
                    )
                    doping = np.asarray(payload["net_doping"], dtype=float)[indices]
                    potential = np.asarray(payload["potential"], dtype=float)[indices]
                    field_x = np.asarray(
                        payload["electric_field_x"], dtype=float
                    )[indices]
                    charge = q * (holes - electrons + doping)

                    carrier_min = min(
                        carrier_min,
                        float(np.min(electrons)),
                        float(np.min(holes)),
                    )
                    carrier_max = max(
                        carrier_max,
                        float(np.max(electrons)),
                        float(np.max(holes)),
                    )
                    charge_abs_max = max(
                        charge_abs_max, float(np.max(np.abs(charge)))
                    )
                    field_abs_max = max(
                        field_abs_max, float(np.max(np.abs(field_x)))
                    )
                    potential_min = min(potential_min, float(np.min(potential)))
                    potential_max = max(potential_max, float(np.max(potential)))

        carrier_min = max(carrier_min / 2.0, 1.0)
        carrier_max = max(carrier_max * 2.0, carrier_min * 10.0)
        charge_abs_max = max(charge_abs_max * 1.08, 1e-20)
        field_abs_max = max(field_abs_max * 1.08, 1.0)
        potential_span = max(potential_max - potential_min, 1e-6)
        potential_padding = 0.08 * potential_span
        limits = {
            "carrier": (carrier_min, carrier_max),
            "charge": (-charge_abs_max, charge_abs_max),
            "field": (-field_abs_max, field_abs_max),
            "potential": (
                potential_min - potential_padding,
                potential_max + potential_padding,
            ),
        }
        self._global_line_limits = limits
        return limits
