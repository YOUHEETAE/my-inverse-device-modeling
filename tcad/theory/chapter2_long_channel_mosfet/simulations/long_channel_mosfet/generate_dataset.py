from __future__ import annotations

import gzip
import json
from pathlib import Path

from generate_gmsh_mesh import MESH_FILE, main as generate_mesh
from long_channel_simulation import run_long_channel_mosfet


OUTPUT_DIR = Path(__file__).resolve().parent / "precomputed_data"
RESULT_FILE = OUTPUT_DIR / "long_channel_mosfet.json.gz"
MANIFEST_FILE = OUTPUT_DIR / "manifest.json"


def _optional(values):
    return None if values is None else values.tolist()


def _serialize_snapshot(snapshot):
    regions = {}
    for name, region in snapshot.regions.items():
        regions[name] = {
            "x_um": region.x_um.tolist(),
            "y_um": region.y_um.tolist(),
            "potential": region.potential.tolist(),
            "net_doping": _optional(region.net_doping),
            "electrons": _optional(region.electrons),
            "holes": _optional(region.holes),
        }
    return {
        "gate_voltage": snapshot.gate_voltage,
        "drain_voltage": snapshot.drain_voltage,
        "regions": regions,
    }


def main() -> None:
    if not MESH_FILE.exists():
        generate_mesh()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result = run_long_channel_mosfet()
    payload = {
        "drain_voltage": result.drain_voltage,
        "gate_voltages": result.gate_voltages.tolist(),
        "drain_currents": result.drain_currents.tolist(),
        "snapshots": {},
        "idvd_gate_voltages": result.idvd_gate_voltages.tolist(),
        "idvd_drain_voltages": result.idvd_drain_voltages.tolist(),
        "idvd_currents": result.idvd_currents.tolist(),
        "idvd_snapshots": {},
    }
    for voltage, snapshot in result.snapshots.items():
        payload["snapshots"][f"{voltage:g}"] = _serialize_snapshot(snapshot)
    for (gate_voltage, drain_voltage), snapshot in result.idvd_snapshots.items():
        key = f"vg_{gate_voltage:g}__vd_{drain_voltage:g}"
        payload["idvd_snapshots"][key] = _serialize_snapshot(snapshot)
    with gzip.open(RESULT_FILE, "wt", encoding="utf-8") as stream:
        json.dump(payload, stream, separators=(",", ":"))
    MANIFEST_FILE.write_text(
        json.dumps(
            {
                "mesh_file": MESH_FILE.name,
                "result_file": RESULT_FILE.name,
                "gate_length_um": 0.5,
                "drain_voltage": result.drain_voltage,
                "snapshot_gate_voltages": sorted(result.snapshots),
                "idvd_gate_voltages": result.idvd_gate_voltages.tolist(),
                "idvd_drain_voltages": result.idvd_drain_voltages.tolist(),
                "idvd_snapshot_drain_voltages": sorted(
                    {key[1] for key in result.idvd_snapshots}
                ),
                "regions": ["gate", "oxide", "bulk"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(RESULT_FILE)


if __name__ == "__main__":
    main()
