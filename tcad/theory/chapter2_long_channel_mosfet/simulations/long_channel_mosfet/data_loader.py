from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np

from result_types import LongChannelResult, MOSFETSnapshot, RegionSnapshot


DATA_DIR = Path(__file__).resolve().parent / "precomputed_data"


def _optional(values):
    return None if values is None else np.asarray(values, dtype=float)


def _snapshot(item) -> MOSFETSnapshot:
    regions = {}
    for name, region in item["regions"].items():
        regions[name] = RegionSnapshot(
            x_um=np.asarray(region["x_um"], dtype=float),
            y_um=np.asarray(region["y_um"], dtype=float),
            potential=np.asarray(region["potential"], dtype=float),
            net_doping=_optional(region["net_doping"]),
            electrons=_optional(region["electrons"]),
            holes=_optional(region["holes"]),
        )
    return MOSFETSnapshot(
        gate_voltage=float(item["gate_voltage"]),
        drain_voltage=float(item.get("drain_voltage", 0.05)),
        regions=regions,
    )


def load_saved_result(data_dir: Path = DATA_DIR) -> LongChannelResult:
    manifest_path = data_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Saved MOSFET result not found: {manifest_path}. "
            "Run generate_dataset.py first."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    with gzip.open(
        data_dir / manifest["result_file"], "rt", encoding="utf-8"
    ) as stream:
        payload = json.load(stream)

    snapshots: dict[float, MOSFETSnapshot] = {}
    for item in payload["snapshots"].values():
        voltage = float(item["gate_voltage"])
        snapshots[voltage] = _snapshot(item)
    idvd_snapshots = {}
    for item in payload.get("idvd_snapshots", {}).values():
        snapshot = _snapshot(item)
        idvd_snapshots[(snapshot.gate_voltage, snapshot.drain_voltage)] = snapshot
    return LongChannelResult(
        gate_voltages=np.asarray(payload["gate_voltages"], dtype=float),
        drain_currents=np.asarray(payload["drain_currents"], dtype=float),
        drain_voltage=float(payload["drain_voltage"]),
        snapshots=snapshots,
        idvd_gate_voltages=np.asarray(
            payload.get("idvd_gate_voltages", []), dtype=float
        ),
        idvd_drain_voltages=np.asarray(
            payload.get("idvd_drain_voltages", []), dtype=float
        ),
        idvd_currents=np.asarray(payload.get("idvd_currents", []), dtype=float),
        idvd_snapshots=idvd_snapshots,
    )
