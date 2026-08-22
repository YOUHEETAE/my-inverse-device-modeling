from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ai.curve_model.inference import device_features
from app.services import (
    curve_predictor,
    explanation_service,
    field_chat_service,
    iv_chat_service,
)

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


# One previous exchange. The client sends these back on each request because
# the chat services are stateless — they take history as an argument (see
# IVChatService.answer). Only the two most recent turns actually reach the
# LLM (iv_chat.py truncates), so sending more is harmless but pointless.
class ChatTurn(BaseModel):
    question: str = Field(max_length=800)
    answer: str
    # Present on turns the LLM failed to answer; those are dropped rather
    # than fed back as context.
    source: str | None = None
    comparison_focus: str | None = None


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=800)
    history: list[ChatTurn] = []
    # Returned by a previous answer and passed back unchanged. The services
    # use it to resume a clarification they had already started rather than
    # re-classifying the question from scratch.
    intent_checkpoint: dict = {}


class ExplainCurveChatRequest(ChatRequest):
    curves: list[CurveConfig]


class ExplainFieldChatRequest(ChatRequest):
    fields: list[FieldConfig]
    display: str
    scale_mode: str
    range_mode: str


class ChatResponse(BaseModel):
    answer: str
    # "external_llm" / "local_router" / "external_error" — the UI shows this
    # so a fallback answer isn't mistaken for a real one.
    source: str
    intent: str | None
    used_evidence_ids: list[str]
    suggested_followup: str | None
    # True when the question can't be answered from the current analysis and
    # the user needs to run a different device configuration.
    needs_new_experiment: bool
    intent_checkpoint: dict


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
def explain_curves(payload: ExplainCurveRequest) -> ExplainResponse:
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
def explain_curves_prompt(payload: ExplainCurveRequest) -> PromptResponse:
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
async def explain_fields_endpoint(payload: ExplainFieldRequest) -> ExplainResponse:
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
async def explain_fields_prompt(payload: ExplainFieldRequest) -> PromptResponse:
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


def _chat_history(turns: list[ChatTurn]) -> list[dict]:
    return [turn.model_dump() for turn in turns]


def _chat_response(response) -> ChatResponse:
    return ChatResponse(
        answer=response.answer,
        source=response.source,
        intent=response.intent.intent if response.intent else None,
        used_evidence_ids=list(response.used_evidence_ids),
        suggested_followup=response.suggested_followup,
        needs_new_experiment=response.needs_new_experiment,
        intent_checkpoint=dict(response.intent_checkpoint),
    )


# Free-form follow-up questions about an analysis. Unlike /explain/curves,
# which describes the result once, this answers whatever the user asks about
# it — the Tkinter app has had this (frontend/visualization/explanation_panel.py);
# the web API simply never exposed it.
#
# The request carries the device configuration rather than an analysis id
# because HTTP is stateless and the services need the prediction to build
# their evidence pack — so each question re-runs the curve prediction, same
# as /explain/curves does.
@router.post("/explain/curves/chat")
def explain_curves_chat(payload: ExplainCurveChatRequest) -> ChatResponse:
    results, configs = _predict_curve_results(payload.curves)
    snapshot = iv_chat_service.build_snapshot(results, configs)

    try:
        response = iv_chat_service.answer(
            snapshot,
            payload.question,
            history=_chat_history(payload.history),
            intent_checkpoint=payload.intent_checkpoint,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _chat_response(response)


@router.post("/explain/fields/chat")
async def explain_fields_chat(payload: ExplainFieldChatRequest) -> ChatResponse:
    outputs = _build_field_outputs(payload.fields)

    try:
        snapshot = field_chat_service.build_snapshot(
            outputs,
            payload.display,
            payload.scale_mode,
            payload.range_mode,
        )
        response = field_chat_service.answer(
            snapshot,
            payload.question,
            history=_chat_history(payload.history),
            intent_checkpoint=payload.intent_checkpoint,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _chat_response(response)
