from app import REPO_ROOT
from ai.curve_model.inference import FinalCurvePredictor
from ai.field_map_model.inference import FieldMapPredictor
from backend.explanation.providers import ProviderSettings, create_explanation_provider
from backend.explanation.service import ExplanationService
from ai.field_map_model.inference import generate_gmsh_mesh
from ai.shared.field_data import GeneratedFieldMap

_initial_provider = create_explanation_provider(
    ProviderSettings.from_environment("auto")
)
explanation_service = ExplanationService(_initial_provider)


curve_predictor = FinalCurvePredictor(
    REPO_ROOT / "ai/model_artifacts/curve_model/final/pca_xgboost"
)


field_predictor = FieldMapPredictor(
    REPO_ROOT / "ai/model_artifacts/field_map_model/final/coordinate_mlp_physics"
)

GEO_TEMPLATE = REPO_ROOT / "tcad/data_extraction/base_case/gmsh_mos2d.geo"


def build_field_map(values: dict[str, str]) -> GeneratedFieldMap:
    length = float(values["L"])
    tox = float(values["T"])
    mesh = generate_gmsh_mesh(length, tox, GEO_TEMPLATE)
    prediction = field_predictor.predict(
        mesh, length, tox, float(values["B"]), float(values["SD"]), float(values["LDD"])
    )
    return GeneratedFieldMap(
        mesh,
        prediction,
        length,
        tox,
        float(values["B"]),
        float(values["SD"]),
        float(values["LDD"]),
    )
