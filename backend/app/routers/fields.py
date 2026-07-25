from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai.curve_model.inference import device_features, range_warning
from ai.shared.field_data import compute_display_payload
from app.services import build_field_map


class MeshData(BaseModel):
    node_xy_nm: list[list[float]]
    node_region: list[int]
    triangles: list[list[int]]
    element_centroid_xy_nm: list[list[float]]
    element_region: list[int]


class FieldRequest(BaseModel):
    L: str
    T: str
    B: str
    SD: str
    LDD: str


class FieldResponse(BaseModel):
    mesh: MeshData
    net_doping: list[float]
    node_fields: dict[str, list[float]]
    element_fields: dict[str, list[float]]
    range_warning: str


class FieldDisplayRequest(BaseModel):
    L: str
    T: str
    B: str
    SD: str
    LDD: str
    display: str
    scale_mode: str = "Auto"
    range_mode: str = "Robust 1-99%"


class FieldDisplayResponse(BaseModel):
    domain: str
    values: list[float | None]
    title: str
    label: str
    norm_type: str
    vmin: float
    vmax: float
    linthresh: float | None
    mode_label: str
    cmap: str


router = APIRouter()


@router.post("/fields/predict")
async def predict_fields(request: FieldRequest) -> FieldResponse:
    values = request.model_dump()

    try:
        device_features(values)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    field_map = build_field_map(values)

    mesh = field_map.mesh
    prediction = field_map.prediction

    return FieldResponse(
        mesh=MeshData(
            node_xy_nm=mesh.node_xy_nm.tolist(),
            node_region=mesh.node_region.tolist(),
            triangles=mesh.triangles.tolist(),
            element_centroid_xy_nm=mesh.element_centroid_xy_nm.tolist(),
            element_region=mesh.element_region.tolist(),
        ),
        net_doping=prediction.net_doping.tolist(),
        node_fields={k: v.tolist() for k, v in prediction.node_fields.items()},
        element_fields={k: v.tolist() for k, v in prediction.element_fields.items()},
        range_warning=range_warning(values),
    )


@router.post("/fields/display")
async def field_display(request: FieldDisplayRequest) -> FieldDisplayResponse:
    values = {k: getattr(request, k) for k in ("L", "T", "B", "SD", "LDD")}

    try:
        device_features(values)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    field_map = build_field_map(values)

    try:
        payload = compute_display_payload(field_map, request.display, request.scale_mode, request.range_mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return FieldDisplayResponse(**payload)
