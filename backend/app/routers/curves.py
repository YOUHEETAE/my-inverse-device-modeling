import math

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Literal
from app.limiter import limiter
from app.services import curve_predictor
from ai.curve_model.inference import (
    device_features,
    extract_electrical_parameters,
    range_warning,
)


class CurveData(BaseModel):
    kind: Literal["idvd", "idvg"]
    grid: list[float]
    fixed_biases: list[float]
    currents: list[list[float]]


class CurveRequest(BaseModel):
    L: str
    T: str
    B: str
    SD: str
    LDD: str


class CurveResponse(BaseModel):
    idvd: CurveData
    idvg: CurveData
    electrical_parameters: dict[str, float]
    range_warning: str


router = APIRouter()


@router.post("/curves/predict")
@limiter.limit("30/minute")
def predict_curves(request: Request, payload: CurveRequest) -> CurveResponse:
    values = payload.model_dump()

    try:
        features = device_features(values)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    idvd = curve_predictor.predict("idvd", features)
    idvg = curve_predictor.predict("idvg", features)
    electrical = extract_electrical_parameters(idvd, idvg)
    # Not part of the shared extraction contract (ai/curve_model/inference) —
    # the Tkinter reference (frontend/app.py) computes this the same way,
    # after calling the shared extractor, rather than inside it.
    ioff = electrical.get("ioff_ma_per_um", 0.0)
    electrical["ion_ioff_ratio"] = (
        electrical.get("ion_ma_per_um", 0.0) / ioff if ioff != 0 else math.inf
    )

    return CurveResponse(
        idvd=CurveData(
            kind=idvd.kind,
            grid=idvd.grid.tolist(),
            fixed_biases=idvd.fixed_biases.tolist(),
            currents=idvd.currents.tolist(),
        ),
        idvg=CurveData(
            kind=idvg.kind,
            grid=idvg.grid.tolist(),
            fixed_biases=idvg.fixed_biases.tolist(),
            currents=idvg.currents.tolist(),
        ),
        electrical_parameters=electrical,
        range_warning=range_warning(values),
    )
