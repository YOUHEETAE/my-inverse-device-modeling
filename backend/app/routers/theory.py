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


router = APIRouter()

_manifest: dict | None = None
_cases: dict[tuple[float, float, float], dict] = {}


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
