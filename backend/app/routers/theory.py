import gzip
import json

import matplotlib.tri as mtri
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import REPO_ROOT

# Reads the same precomputed_data the Tkinter reference app
# (tcad/theory/chapter1_pn_junction/{app,data_loader}.py) uses. Not importing
# that module directly: it relies on bare `from result_types import ...`
# imports that only resolve when chapter1_pn_junction/ itself is on sys.path
# (i.e. run as a script), which conflicts with importing it as part of the
# `backend.app` package — so this is a small, from-scratch re-read of the
# same manifest/gzip files instead.
PN_DATA_DIR = REPO_ROOT / "tcad/theory/chapter1_pn_junction/precomputed_data"


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


MOSCAP_DATA_DIR = (
    REPO_ROOT
    / "tcad/theory/chapter2_long_channel_mosfet/simulations/mos_capacitor/precomputed_data"
)


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

_manifest: dict | None = None
_cases: dict[tuple[float, float, float], dict] = {}
_lc_manifest: dict | None = None
_lc_payload: dict | None = None
_moscap_manifest: dict | None = None
_moscap_cases: dict[tuple[float, float, float], dict] = {}


def _load_manifest() -> dict:
    global _manifest, _cases
    if _manifest is None:
        manifest_path = PN_DATA_DIR / "manifest.json"
        if not manifest_path.exists():
            raise HTTPException(status_code=500, detail="PN junction dataset manifest not found")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        _cases = {
            (float(case["acceptors"]), float(case["donors"]), float(case["bias"])): case
            for case in manifest["cases"]
            if case["status"] == "ok"
        }
        _manifest = manifest
    return _manifest


def _read_case(case: dict) -> dict:
    with gzip.open(PN_DATA_DIR / case["file"], "rt", encoding="utf-8") as stream:
        return json.load(stream)


@router.get("/theory/pn-junction/options")
def get_pn_junction_options() -> PNOptionsResponse:
    manifest = _load_manifest()
    return PNOptionsResponse(
        dopings=[float(v) for v in manifest["dopings"]],
        biases=[float(v) for v in manifest["biases"]],
    )


@router.post("/theory/pn-junction/result")
def get_pn_junction_result(request: PNResultRequest) -> PNResultResponse:
    manifest = _load_manifest()
    key = (request.acceptors, request.donors, request.bias)
    case = _cases.get(key)
    if case is None:
        raise HTTPException(
            status_code=404,
            detail=f"No saved result for NA={request.acceptors:g}, ND={request.donors:g}, V={request.bias:g}",
        )
    payload = _read_case(case)
    triangulation = mtri.Triangulation(payload["x_um"], payload["y_um"])

    iv_cases = [
        _cases[(request.acceptors, request.donors, float(voltage))]
        for voltage in manifest["biases"]
        if (request.acceptors, request.donors, float(voltage)) in _cases
    ]

    return PNResultResponse(
        x_um=payload["x_um"],
        y_um=payload["y_um"],
        triangles=triangulation.triangles.tolist(),
        net_doping=payload["net_doping"],
        potential=payload["potential"],
        electrons=payload["electrons"],
        holes=payload["holes"],
        electric_field=payload["electric_field"],
        electric_field_x=payload["electric_field_x"],
        voltages=[float(c["bias"]) for c in iv_cases],
        currents=[float(c["current"]) for c in iv_cases],
        selected_bias=request.bias,
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


def _load_moscap_manifest() -> dict:
    global _moscap_manifest, _moscap_cases
    if _moscap_manifest is None:
        manifest_path = MOSCAP_DATA_DIR / "manifest.json"
        if not manifest_path.exists():
            raise HTTPException(status_code=500, detail="MOS capacitor dataset manifest not found")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        _moscap_cases = {
            (
                float(case["acceptor_doping"]),
                float(case["oxide_thickness_nm"]),
                float(case["gate_voltage"]),
            ): case
            for case in manifest["cases"]
            if case["status"] == "ok"
        }
        _moscap_manifest = manifest
    return _moscap_manifest


def _read_moscap_case(case: dict) -> dict:
    with gzip.open(MOSCAP_DATA_DIR / case["file"], "rt", encoding="utf-8") as stream:
        return json.load(stream)


@router.get("/theory/mos-capacitor/options")
def get_mos_capacitor_options() -> MOSCapOptionsResponse:
    manifest = _load_moscap_manifest()
    return MOSCapOptionsResponse(
        acceptor_dopings=[float(v) for v in manifest["acceptor_dopings"]],
        oxide_thicknesses_nm=[float(v) for v in manifest["oxide_thicknesses_nm"]],
        gate_voltages=[float(v) for v in manifest["gate_voltages"]],
    )


@router.post("/theory/mos-capacitor/result")
def get_mos_capacitor_result(request: MOSCapResultRequest) -> MOSCapResultResponse:
    _load_moscap_manifest()
    key = (request.acceptor_doping, request.oxide_thickness_nm, request.gate_voltage)
    case = _moscap_cases.get(key)
    if case is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No saved result for NA={request.acceptor_doping:g}, "
                f"tox={request.oxide_thickness_nm:g}nm, VG={request.gate_voltage:g}"
            ),
        )
    payload = _read_moscap_case(case)
    return MOSCapResultResponse(
        acceptor_doping=payload["acceptor_doping"],
        oxide_thickness_nm=payload["oxide_thickness_nm"],
        gate_voltage=payload["gate_voltage"],
        regime=payload["regime"],
        gate_charge_c_per_cm2=payload["gate_charge_c_per_cm2"],
        oxide_x_nm=payload["oxide_x_nm"],
        oxide_potential=payload["oxide_potential"],
        oxide_field_x_nm=payload["oxide_field_x_nm"],
        oxide_field=payload["oxide_field"],
        silicon_depth_nm=payload["silicon_depth_nm"],
        silicon_potential=payload["silicon_potential"],
        electrons=payload["electrons"],
        holes=payload["holes"],
        charge_density=payload["charge_density"],
    )
