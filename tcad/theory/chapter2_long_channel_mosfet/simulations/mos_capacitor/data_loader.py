from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np

try:
    # Package import — used when the backend imports this module as
    # tcad.theory.chapter2_long_channel_mosfet.simulations.mos_capacitor.data_loader.
    from .result_types import MOSCapResult
except ImportError:
    # Bare import — used when app.py (the Tkinter reference tool) is run
    # directly as a script, with this directory on sys.path and no
    # enclosing package context for a relative import to resolve against.
    from result_types import MOSCapResult


DATA_DIR = Path(__file__).resolve().parent / "precomputed_data"


class MOSCapDataset:
    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        self.data_dir = data_dir
        manifest_path = data_dir / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(
                f"Required precomputed dataset not found: {manifest_path}"
            )
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.acceptor_dopings = tuple(
            float(value) for value in self.manifest["acceptor_dopings"]
        )
        self.oxide_thicknesses_nm = tuple(
            float(value) for value in self.manifest["oxide_thicknesses_nm"]
        )
        self.gate_voltages = tuple(
            float(value) for value in self.manifest["gate_voltages"]
        )
        self._cases = {
            (
                float(case["acceptor_doping"]),
                float(case["oxide_thickness_nm"]),
                float(case["gate_voltage"]),
            ): case
            for case in self.manifest["cases"]
            if case["status"] == "ok"
        }

    def load(
        self,
        acceptor_doping: float,
        oxide_thickness_nm: float,
        gate_voltage: float,
    ) -> MOSCapResult:
        key = (acceptor_doping, oxide_thickness_nm, gate_voltage)
        case = self._cases.get(key)
        if case is None:
            raise KeyError(
                f"No saved MOS capacitor result for NA={acceptor_doping:g}, "
                f"tox={oxide_thickness_nm:g} nm, VG={gate_voltage:g} V"
            )
        with gzip.open(self.data_dir / case["file"], "rt", encoding="utf-8") as stream:
            payload = json.load(stream)
        array = lambda name: np.asarray(payload[name], dtype=float)
        return MOSCapResult(
            gate_voltage=float(payload["gate_voltage"]),
            acceptor_doping=float(payload["acceptor_doping"]),
            oxide_thickness_nm=float(payload["oxide_thickness_nm"]),
            oxide_x_nm=array("oxide_x_nm"),
            oxide_potential=array("oxide_potential"),
            oxide_field_x_nm=array("oxide_field_x_nm"),
            oxide_field=array("oxide_field"),
            silicon_depth_nm=array("silicon_depth_nm"),
            silicon_potential=array("silicon_potential"),
            electrons=array("electrons"),
            holes=array("holes"),
            charge_density=array("charge_density"),
            gate_charge_c_per_cm2=float(payload["gate_charge_c_per_cm2"]),
            regime=str(payload["regime"]),
        )
