from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ai.curve_model.inference import device_features
from app.limiter import limiter
from app.services import curve_predictor, explanation_service

from app.services import build_field_map

# Bounds the label field sent into the LLM prompt (see payload_builders.py /
# iv_renderer.py / field_renderer.py — it's interpolated into rendered
# sentences verbatim). The shipped frontend auto-generates labels like
# "Curve 1" and never exposes a text input for this, but the API schema
# itself didn't previously constrain it, so a direct API call could put
# arbitrary long/adversarial text here.
LABEL_MAX_LENGTH = 60


class CurveConfig(BaseModel):
    label: str = Field(max_length=LABEL_MAX_LENGTH)
    L: str
    T: str
    B: str
    SD: str
    LDD: str


class ExplainCurveRequest(BaseModel):
    curves: list[CurveConfig]


class FieldConfig(BaseModel):
    label: str = Field(max_length=LABEL_MAX_LENGTH)
    L: str
    T: str
    B: str
    SD: str
    LDD: str


class ExplainFieldRequest(BaseModel):
    fields: list[FieldConfig]
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


def _predict_curve_results(curves: list[CurveConfig]):
    results = []
    configs = []
    for curve in curves:
        values = curve.model_dump(exclude={"label"})
        features = device_features(values)
        idvd = curve_predictor.predict("idvd", features)
        idvg = curve_predictor.predict("idvg", features)
        results.append((curve.label, idvd, idvg))
        configs.append(values)
    return results, configs


@router.post("/explain/curves")
@limiter.limit("10/minute")
@limiter.limit("15/day")
def explain_curves(request: Request, payload: ExplainCurveRequest) -> ExplainResponse:
    results, configs = _predict_curve_results(payload.curves)

    result = explanation_service.explain_curves(results=results, configs=configs)

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
@limiter.limit("10/minute")
def explain_curves_prompt(request: Request, payload: ExplainCurveRequest) -> PromptResponse:
    results, configs = _predict_curve_results(payload.curves)

    prompt = explanation_service.build_curves_prompt(results=results, configs=configs)
    return PromptResponse(prompt=prompt)


def _build_field_outputs(fields: list[FieldConfig]):
    outputs = []
    for field in fields:
        values = field.model_dump(exclude={"label"})
        field_map = build_field_map(values)
        outputs.append((field.label, field_map))
    return outputs


@router.post("/explain/fields")
@limiter.limit("10/minute")
@limiter.limit("15/day")
async def explain_fields_endpoint(request: Request, payload: ExplainFieldRequest) -> ExplainResponse:
    outputs = _build_field_outputs(payload.fields)

    try:
        result = explanation_service.explain_fields(
            outputs=outputs,
            display=payload.display,
            scale_mode=payload.scale_mode,
            range_mode=payload.range_mode,
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
@limiter.limit("10/minute")
async def explain_fields_prompt(request: Request, payload: ExplainFieldRequest) -> PromptResponse:
    outputs = _build_field_outputs(payload.fields)

    try:
        prompt = explanation_service.build_fields_prompt(
            outputs=outputs,
            display=payload.display,
            scale_mode=payload.scale_mode,
            range_mode=payload.range_mode,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return PromptResponse(prompt=prompt)
