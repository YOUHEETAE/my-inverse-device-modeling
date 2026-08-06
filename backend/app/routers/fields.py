from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ai.curve_model.inference import device_features, range_warning
from ai.shared.field_data import compute_display_payload, compute_display_payload_multi
from app.limiter import limiter
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


class FieldConfig(BaseModel):
    label: str
    L: str
    T: str
    B: str
    SD: str
    LDD: str


class FieldCompareRequest(BaseModel):
    devices: list[FieldConfig]
    display: str
    scale_mode: str = "Auto"
    range_mode: str = "Robust 1-99%"


class FieldCompareItem(BaseModel):
    label: str
    mesh: MeshData
    values: list[float | None]


class FieldCompareResponse(BaseModel):
    domain: str
    title: str
    label: str
    norm_type: str
    vmin: float
    vmax: float
    linthresh: float | None
    mode_label: str
    cmap: str
    items: list[FieldCompareItem]


router = APIRouter()


@router.post("/fields/predict")
@limiter.limit("30/minute")
async def predict_fields(request: Request, body: FieldRequest) -> FieldResponse:
    values = body.model_dump()

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
@limiter.limit("30/minute")
async def field_display(request: Request, body: FieldDisplayRequest) -> FieldDisplayResponse:
    values = {k: getattr(body, k) for k in ("L", "T", "B", "SD", "LDD")}

    try:
        device_features(values)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    field_map = build_field_map(values)

    try:
        payload = compute_display_payload(field_map, body.display, body.scale_mode, body.range_mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return FieldDisplayResponse(**payload)


@router.post("/fields/display/compare")
@limiter.limit("30/minute")
async def field_display_compare(request: Request, body: FieldCompareRequest) -> FieldCompareResponse:
    if not body.devices:
        raise HTTPException(status_code=400, detail="At least one device is required.")

    outputs = []
    for device in body.devices:
        values = device.model_dump(exclude={"label"})
        try:
            device_features(values)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"{device.label}: {e}")
        outputs.append((device.label, build_field_map(values)))

    try:
        payload = compute_display_payload_multi(outputs, body.display, body.scale_mode, body.range_mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    items = [
        FieldCompareItem(
            label=item["label"],
            mesh=MeshData(
                node_xy_nm=output.mesh.node_xy_nm.tolist(),
                node_region=output.mesh.node_region.tolist(),
                triangles=output.mesh.triangles.tolist(),
                element_centroid_xy_nm=output.mesh.element_centroid_xy_nm.tolist(),
                element_region=output.mesh.element_region.tolist(),
            ),
            values=item["values"],
        )
        for item, (_label, output) in zip(payload["items"], outputs, strict=True)
    ]

    return FieldCompareResponse(
        domain=payload["domain"],
        title=payload["title"],
        label=payload["label"],
        norm_type=payload["norm_type"],
        vmin=payload["vmin"],
        vmax=payload["vmax"],
        linthresh=payload["linthresh"],
        mode_label=payload["mode_label"],
        cmap=payload["cmap"],
        items=items,
    )
