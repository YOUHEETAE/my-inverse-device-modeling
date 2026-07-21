from app import REPO_ROOT

from ai.curve_model.inference import FinalCurvePredictor

curve_predictor = FinalCurvePredictor(
    REPO_ROOT / "ai/model_artifacts/curve_model/final/pca_xgboost"
)

from ai.field_map_model.inference import FieldMapPredictor

field_predictor = FieldMapPredictor(
    REPO_ROOT / "ai/model_artifacts/field_map_model/final/coordinate_mlp_physics"
)
