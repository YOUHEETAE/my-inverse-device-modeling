from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MOSCapResult:
    gate_voltage: float
    acceptor_doping: float
    oxide_thickness_nm: float
    oxide_x_nm: np.ndarray
    oxide_potential: np.ndarray
    oxide_field_x_nm: np.ndarray
    oxide_field: np.ndarray
    silicon_depth_nm: np.ndarray
    silicon_potential: np.ndarray
    electrons: np.ndarray
    holes: np.ndarray
    charge_density: np.ndarray
    gate_charge_c_per_cm2: float
    regime: str
