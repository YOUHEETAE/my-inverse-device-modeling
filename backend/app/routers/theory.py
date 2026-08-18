import gzip
import json

import matplotlib.tri as mtri
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import REPO_ROOT
from tcad.theory.chapter1_pn_junction.data_loader import Dataset as PNDataset
from tcad.theory.chapter2_long_channel_mosfet.simulations.mos_capacitor.data_loader import (
    MOSCapDataset,
)


class PNOptionsResponse(BaseModel):
    dopings: list[float]
    biases: list[float]


class PNResultRequest(BaseModel):
    acceptors: float
    donors: float
    bias: float


class PNResultResponse(BaseModel):
    x_um: list[float]
    y_um: list[float]
    # Desktop app's tripcolor(shading="gouraud") shades a Delaunay
    # triangulation of the scattered points rather than plotting bare
    # markers — matplotlib's Triangulation(x, y) computes this automatically
    # when no explicit triangles are given, so this mirrors that exactly
    # (via the same library) instead of leaving it to a bare point-cloud
    # scatter on the frontend.
    triangles: list[list[int]]
    net_doping: list[float]
    potential: list[float]
    electrons: list[float]
    holes: list[float]
    electric_field: list[float]
    electric_field_x: list[float]
    voltages: list[float]
    currents: list[float]
    selected_bias: float


LC_DATA_DIR = (
    REPO_ROOT
    / "tcad/theory/chapter2_long_channel_mosfet/simulations/long_channel_mosfet/precomputed_data"
)


class LongChannelOptionsResponse(BaseModel):
    gate_voltages: list[float]
    drain_voltages: list[float]


class LongChannelResultRequest(BaseModel):
    gate_voltage: float
    drain_voltage: float


class LongChannelRegion(BaseModel):
    x_um: list[float]
    y_um: list[float]
    triangles: list[list[int]]
    potential: list[float]
    net_doping: list[float] | None
    electrons: list[float] | None
    holes: list[float] | None


class LongChannelResultResponse(BaseModel):
    regions: dict[str, LongChannelRegion]
    # ID-VG transfer curve (fixed VD, all VG points) and ID-VD output-curve
    # family (fixed VG set, all VD points) are independent of which snapshot
    # is selected for the field map, so both are always returned in full —
    # matching the desktop app, which draws both lower plots unconditionally.
    gate_voltages: list[float]
    drain_currents: list[float]
    idvg_drain_voltage: float
    idvd_gate_voltages: list[float]
    idvd_drain_voltages: list[float]
    idvd_currents: list[list[float]]
    selected_gate_voltage: float
    selected_drain_voltage: float


class MOSCapOptionsResponse(BaseModel):
    acceptor_dopings: list[float]
    oxide_thicknesses_nm: list[float]
    gate_voltages: list[float]


class MOSCapResultRequest(BaseModel):
    acceptor_doping: float
    oxide_thickness_nm: float
    gate_voltage: float


class MOSCapResultResponse(BaseModel):
    acceptor_doping: float
    oxide_thickness_nm: float
    gate_voltage: float
    regime: str
    gate_charge_c_per_cm2: float
    oxide_x_nm: list[float]
    oxide_potential: list[float]
    oxide_field_x_nm: list[float]
    oxide_field: list[float]
    silicon_depth_nm: list[float]
    silicon_potential: list[float]
    electrons: list[float]
    holes: list[float]
    charge_density: list[float]


router = APIRouter()

_lc_manifest: dict | None = None
_lc_payload: dict | None = None

_pn_dataset: PNDataset | None = None


def _load_pn_dataset() -> PNDataset:
    global _pn_dataset
    if _pn_dataset is None:
        try:
            _pn_dataset = PNDataset()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _pn_dataset


@router.get("/theory/pn-junction/options")
def get_pn_junction_options() -> PNOptionsResponse:
    dataset = _load_pn_dataset()
    return PNOptionsResponse(dopings=list(dataset.dopings), biases=list(dataset.biases))


@router.post("/theory/pn-junction/result")
def get_pn_junction_result(request: PNResultRequest) -> PNResultResponse:
    dataset = _load_pn_dataset()
    try:
        result = dataset.load(request.acceptors, request.donors, request.bias)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=exc.args[0]) from exc

    triangulation = mtri.Triangulation(result.x_um, result.y_um)
    return PNResultResponse(
        x_um=result.x_um.tolist(),
        y_um=result.y_um.tolist(),
        triangles=triangulation.triangles.tolist(),
        net_doping=result.net_doping.tolist(),
        potential=result.potential.tolist(),
        electrons=result.electrons.tolist(),
        holes=result.holes.tolist(),
        electric_field=result.electric_field.tolist(),
        electric_field_x=result.electric_field_x.tolist(),
        voltages=result.voltages.tolist(),
        currents=result.currents.tolist(),
        selected_bias=result.selected_bias,
    )


def _load_long_channel_payload() -> tuple[dict, dict]:
    global _lc_manifest, _lc_payload
    if _lc_payload is None:
        manifest_path = LC_DATA_DIR / "manifest.json"
        if not manifest_path.exists():
            raise HTTPException(status_code=500, detail="Long-channel MOSFET dataset manifest not found")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        with gzip.open(LC_DATA_DIR / manifest["result_file"], "rt", encoding="utf-8") as stream:
            payload = json.load(stream)
        _lc_manifest = manifest
        _lc_payload = payload
    return _lc_manifest, _lc_payload


def _long_channel_region(region: dict) -> LongChannelRegion:
    triangulation = mtri.Triangulation(region["x_um"], region["y_um"])
    return LongChannelRegion(
        x_um=region["x_um"],
        y_um=region["y_um"],
        triangles=triangulation.triangles.tolist(),
        potential=region["potential"],
        net_doping=region["net_doping"],
        electrons=region["electrons"],
        holes=region["holes"],
    )


@router.get("/theory/long-channel-mosfet/options")
def get_long_channel_mosfet_options() -> LongChannelOptionsResponse:
    manifest, _payload = _load_long_channel_payload()
    return LongChannelOptionsResponse(
        gate_voltages=[float(v) for v in manifest["idvd_gate_voltages"]],
        drain_voltages=[float(v) for v in manifest["idvd_snapshot_drain_voltages"]],
    )


@router.post("/theory/long-channel-mosfet/result")
def get_long_channel_mosfet_result(request: LongChannelResultRequest) -> LongChannelResultResponse:
    _manifest_data, payload = _load_long_channel_payload()
    # Desktop app snaps a requested (VG, VD) to the nearest saved grid point
    # via min(..., key=lambda item: abs(vg-item[0]) + abs(vd-item[1])) rather
    # than requiring an exact match; mirrored here with the same key naming
    # the dataset was generated with (vg_{g}__vd_{d}, `g:g`-formatted).
    key = f"vg_{request.gate_voltage:g}__vd_{request.drain_voltage:g}"
    snapshot = payload["idvd_snapshots"].get(key)
    if snapshot is None:
        best_key, best_distance = None, None
        for candidate_key, candidate in payload["idvd_snapshots"].items():
            distance = abs(candidate["gate_voltage"] - request.gate_voltage) + abs(
                candidate["drain_voltage"] - request.drain_voltage
            )
            if best_distance is None or distance < best_distance:
                best_key, best_distance = candidate_key, distance
        snapshot = payload["idvd_snapshots"][best_key]

    regions = {name: _long_channel_region(region) for name, region in snapshot["regions"].items()}

    return LongChannelResultResponse(
        regions=regions,
        gate_voltages=payload["gate_voltages"],
        drain_currents=payload["drain_currents"],
        idvg_drain_voltage=float(payload["drain_voltage"]),
        idvd_gate_voltages=payload["idvd_gate_voltages"],
        idvd_drain_voltages=payload["idvd_drain_voltages"],
        idvd_currents=payload["idvd_currents"],
        selected_gate_voltage=float(snapshot["gate_voltage"]),
        selected_drain_voltage=float(snapshot["drain_voltage"]),
    )


_moscap_dataset: MOSCapDataset | None = None


def _load_moscap_dataset() -> MOSCapDataset:
    global _moscap_dataset
    if _moscap_dataset is None:
        try:
            _moscap_dataset = MOSCapDataset()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _moscap_dataset


@router.get("/theory/mos-capacitor/options")
def get_mos_capacitor_options() -> MOSCapOptionsResponse:
    dataset = _load_moscap_dataset()
    return MOSCapOptionsResponse(
        acceptor_dopings=list(dataset.acceptor_dopings),
        oxide_thicknesses_nm=list(dataset.oxide_thicknesses_nm),
        gate_voltages=list(dataset.gate_voltages),
    )


@router.post("/theory/mos-capacitor/result")
def get_mos_capacitor_result(request: MOSCapResultRequest) -> MOSCapResultResponse:
    dataset = _load_moscap_dataset()
    try:
        result = dataset.load(request.acceptor_doping, request.oxide_thickness_nm, request.gate_voltage)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=exc.args[0]) from exc

    return MOSCapResultResponse(
        acceptor_doping=result.acceptor_doping,
        oxide_thickness_nm=result.oxide_thickness_nm,
        gate_voltage=result.gate_voltage,
        regime=result.regime,
        gate_charge_c_per_cm2=result.gate_charge_c_per_cm2,
        oxide_x_nm=result.oxide_x_nm.tolist(),
        oxide_potential=result.oxide_potential.tolist(),
        oxide_field_x_nm=result.oxide_field_x_nm.tolist(),
        oxide_field=result.oxide_field.tolist(),
        silicon_depth_nm=result.silicon_depth_nm.tolist(),
        silicon_potential=result.silicon_potential.tolist(),
        electrons=result.electrons.tolist(),
        holes=result.holes.tolist(),
        charge_density=result.charge_density.tolist(),
    )
