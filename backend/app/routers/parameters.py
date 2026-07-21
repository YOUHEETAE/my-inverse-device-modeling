from fastapi import APIRouter
from pydantic import BaseModel
from ai.curve_model.inference import PARAMETER_OPTIONS, DEFAULT_PARAMETERS


class ParametersResponse(BaseModel):
    options: dict[str, list[str]]
    defaults: dict[str, str]


router = APIRouter()


@router.get("/parameters")
def get_parameters() -> ParametersResponse:
    return ParametersResponse(options=PARAMETER_OPTIONS, defaults=DEFAULT_PARAMETERS)
