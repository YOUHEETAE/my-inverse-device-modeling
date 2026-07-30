from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class RegionSnapshot:
    x_um: np.ndarray
    y_um: np.ndarray
    potential: np.ndarray
    net_doping: np.ndarray | None = None
    electrons: np.ndarray | None = None
    holes: np.ndarray | None = None


@dataclass(frozen=True)
class MOSFETSnapshot:
    gate_voltage: float
    drain_voltage: float
    regions: dict[str, RegionSnapshot]


@dataclass(frozen=True)
class LongChannelResult:
    gate_voltages: np.ndarray
    drain_currents: np.ndarray
    drain_voltage: float
    snapshots: dict[float, MOSFETSnapshot]
    idvd_gate_voltages: np.ndarray
    idvd_drain_voltages: np.ndarray
    idvd_currents: np.ndarray
    idvd_snapshots: dict[tuple[float, float], MOSFETSnapshot]
