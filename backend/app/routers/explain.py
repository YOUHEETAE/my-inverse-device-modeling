from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai.curve_model.inference import device_features
from app.services import curve_predictor, explanation_service

from app.services import build_field_map


class ExplainCurveRequest(BaseModel):
    L: str
    T: str
    B: str
    SD: str
    LDD: str


class ExplainFieldRequest(BaseModel):
    L: str
    T: str
    B: str
    SD: str
    LDD: str
    display: str
    scale_mode: str
    range_mode: str


class ExplainResponse(BaseModel):
    descriptions: list[str]
    comparisons: list[str]
    tradeoffs: list[str]
    cautions: list[str]
    provider: str
    model: str
    cached: bool


class PromptResponse(BaseModel):
    prompt: str


router = APIRouter()


@router.post("/explain/curves")
def explain_curves(request: ExplainCurveRequest) -> ExplainResponse:
    values = request.model_dump()
    features = device_features(values)
    idvd = curve_predictor.predict("idvd", features)
    idvg = curve_predictor.predict("idvg", features)

    result = explanation_service.explain_curves(
        results=[("Curve 1", idvd, idvg)],
        configs=[values],
    )

    return ExplainResponse(
        descriptions=list(result.descriptions),
        comparisons=list(result.comparisons),
        tradeoffs=list(result.tradeoffs),
        cautions=list(result.cautions),
        provider=result.provider,
        model=result.model,
        cached=result.cached,
    )


@router.post("/explain/curves/prompt")
def explain_curves_prompt(request: ExplainCurveRequest) -> PromptResponse:
    values = request.model_dump()
    features = device_features(values)
    idvd = curve_predictor.predict("idvd", features)
    idvg = curve_predictor.predict("idvg", features)

    prompt = explanation_service.build_curves_prompt(
        results=[("Curve 1", idvd, idvg)],
        configs=[values],
    )
    return PromptResponse(prompt=prompt)


@router.post("/explain/fields")
async def explain_fields_endpoint(request: ExplainFieldRequest) -> ExplainResponse:
    dumped = request.model_dump()
    values = {k: dumped[k] for k in ("L", "T", "B", "SD", "LDD")}
    field_map = build_field_map(values)

    try:
        result = explanation_service.explain_fields(
            outputs=[("Field 1", field_map)],
            display=request.display,
            scale_mode=request.scale_mode,
            range_mode=request.range_mode,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ExplainResponse(
        descriptions=list(result.descriptions),
        comparisons=list(result.comparisons),
        tradeoffs=list(result.tradeoffs),
        cautions=list(result.cautions),
        provider=result.provider,
        model=result.model,
        cached=result.cached,
    )


@router.post("/explain/fields/prompt")
async def explain_fields_prompt(request: ExplainFieldRequest) -> PromptResponse:
    dumped = request.model_dump()
    values = {k: dumped[k] for k in ("L", "T", "B", "SD", "LDD")}
    field_map = build_field_map(values)

    try:
        prompt = explanation_service.build_fields_prompt(
            outputs=[("Field 1", field_map)],
            display=request.display,
            scale_mode=request.scale_mode,
            range_mode=request.range_mode,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return PromptResponse(prompt=prompt)
