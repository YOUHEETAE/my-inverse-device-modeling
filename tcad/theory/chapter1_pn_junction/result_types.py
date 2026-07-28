from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PNResult:
    x_um: np.ndarray
    y_um: np.ndarray
    net_doping: np.ndarray
    potential: np.ndarray
    electrons: np.ndarray
    holes: np.ndarray
    electric_field: np.ndarray
    electric_field_x: np.ndarray
    voltages: np.ndarray
    currents: np.ndarray
    selected_bias: float
