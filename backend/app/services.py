from dataclasses import replace

from app import REPO_ROOT
from ai.curve_model.inference import FinalCurvePredictor
from ai.field_map_model.inference import FieldMapPredictor
from backend.explanation.providers import ProviderSettings, create_explanation_provider
from backend.explanation.service import ExplanationService
from backend.explanation.iv_chat import IVChatService
from backend.explanation.field_chat import FieldChatService
from ai.field_map_model.inference import generate_gmsh_mesh
from ai.shared.field_data import GeneratedFieldMap

_initial_provider = create_explanation_provider(
    ProviderSettings.from_environment("auto")
)
explanation_service = ExplanationService(_initial_provider)


def _create_chat_provider():
    """Strict provider for free-form questions — mirrors the Tkinter app's
    create_case_study_provider (frontend/app.py).

    Unlike the explanation service above, mock and "safe" fallbacks are
    disabled: a canned answer to a question the user actually typed reads as
    a real answer, which is worse than saying the LLM is unavailable. The
    chat services accept None and report provider_unavailable themselves.
    """
    try:
        settings = replace(
            ProviderSettings.from_environment("external_llm"),
            allow_mock_fallback=False,
            allow_safe_fallback=False,
        )
        return create_explanation_provider(settings)
    except RuntimeError:
        return None


_chat_provider = _create_chat_provider()
iv_chat_service = IVChatService(_chat_provider)
field_chat_service = FieldChatService(_chat_provider)


curve_predictor = FinalCurvePredictor(
    REPO_ROOT / "ai/model_artifacts/curve_model/final/pca_xgboost"
)


field_predictor = FieldMapPredictor(
    REPO_ROOT / "ai/model_artifacts/field_map_model/final/coordinate_mlp_physics"
)

GEO_TEMPLATE = REPO_ROOT / "tcad/data_extraction/base_case/gmsh_mos2d.geo"

# Mirrors the Tkinter app's mesh_cache: gmsh generation is expensive and only
# depends on (L, T), so repeated calls for the same device (e.g. switching
# field display/scale mode) reuse the mesh instead of regenerating it.
_mesh_cache: dict[tuple[float, float], object] = {}

# The model inference (field_predictor.predict) is the expensive part of
# build_field_map, but /fields/predict, /fields/display, and
# /fields/display/compare all call it independently — without this, revisiting
# the same device (all 5 params unchanged) re-runs the full prediction every
# time instead of reusing the mesh-cache-only savings above.
_field_map_cache: dict[tuple[float, float, float, float, float], GeneratedFieldMap] = {}


def build_field_map(values: dict[str, str]) -> GeneratedFieldMap:
    length = float(values["L"])
    tox = float(values["T"])
    body = float(values["B"])
    sd = float(values["SD"])
    ldd = float(values["LDD"])

    cache_key = (length, tox, body, sd, ldd)
    cached = _field_map_cache.get(cache_key)
    if cached is not None:
        return cached

    mesh = _mesh_cache.get((length, tox))
    if mesh is None:
        mesh = generate_gmsh_mesh(length, tox, GEO_TEMPLATE)
        _mesh_cache[(length, tox)] = mesh

    prediction = field_predictor.predict(mesh, length, tox, body, sd, ldd)
    result = GeneratedFieldMap(mesh, prediction, length, tox, body, sd, ldd)
    _field_map_cache[cache_key] = result
    return result
