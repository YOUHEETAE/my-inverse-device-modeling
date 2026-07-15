from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor


class PCAXGBoostRegressor:
    """Predict PCA curve coefficients with one XGBoost model per component."""

    def __init__(
        self,
        n_components: int = 16,
        *,
        random_state: int = 42,
        xgb_params: dict[str, object] | None = None,
        feature_engineering: str | None = None,
    ) -> None:
        self.n_components = n_components
        self.random_state = random_state
        self.xgb_params = xgb_params or {}
        self.feature_engineering = feature_engineering
        self.feature_scaler_: StandardScaler | None = None
        self.pca_: PCA | None = None
        self.regressors_: list[XGBRegressor] = []
        self.active_components_: int | None = None

    def fit(
        self,
        features: np.ndarray,
        targets: np.ndarray,
        *,
        validation_features: np.ndarray | None = None,
        validation_targets: np.ndarray | None = None,
        sample_weight: np.ndarray | None = None,
    ) -> "PCAXGBoostRegressor":
        x = _matrix(features, "features")
        y = _matrix(targets, "targets")
        if len(x) != len(y):
            raise ValueError("features and targets must contain the same samples")
        weights = None
        if sample_weight is not None:
            weights = np.asarray(sample_weight, dtype=np.float32)
            if weights.ndim != 1 or len(weights) != len(x):
                raise ValueError("sample_weight must contain one value per training sample")
            if not np.all(np.isfinite(weights)) or np.any(weights <= 0):
                raise ValueError("sample_weight values must be finite and positive")
        has_validation = validation_features is not None or validation_targets is not None
        if has_validation and (
            validation_features is None or validation_targets is None
        ):
            raise ValueError("Provide both validation_features and validation_targets")

        x_model = self._model_features(x)
        self.feature_scaler_ = StandardScaler().fit(x_model)
        x_scaled = self.feature_scaler_.transform(x_model)
        count = min(self.n_components, len(y), y.shape[1])
        self.pca_ = PCA(n_components=count, svd_solver="full")
        coefficients = self.pca_.fit_transform(y)

        validation_scaled: np.ndarray | None = None
        validation_coefficients: np.ndarray | None = None
        if has_validation:
            validation_x = _matrix(validation_features, "validation_features")
            validation_y = _matrix(validation_targets, "validation_targets")
            if len(validation_x) != len(validation_y):
                raise ValueError("Validation features and targets must have equal length")
            validation_scaled = self.feature_scaler_.transform(
                self._model_features(validation_x)
            )
            validation_coefficients = self.pca_.transform(validation_y)

        defaults: dict[str, object] = {
            "n_estimators": 5000,
            "max_depth": 5,
            "learning_rate": 0.03,
            "subsample": 0.85,
            "colsample_bytree": 0.9,
            "objective": "reg:squarederror",
            "eval_metric": "rmse",
            "tree_method": "hist",
            "random_state": self.random_state,
            "n_jobs": -1,
        }
        if has_validation:
            defaults["early_stopping_rounds"] = 150
        defaults.update(self.xgb_params)
        self.regressors_ = []
        for column in range(count):
            regressor = XGBRegressor(**defaults)
            fit_options: dict[str, object] = {"verbose": False}
            if weights is not None:
                fit_options["sample_weight"] = weights
            if validation_scaled is not None and validation_coefficients is not None:
                fit_options["eval_set"] = [
                    (validation_scaled, validation_coefficients[:, column])
                ]
            regressor.fit(x_scaled, coefficients[:, column], **fit_options)
            self.regressors_.append(regressor)
        self.active_components_ = count
        return self

    def predict(
        self, features: np.ndarray, *, n_components: int | None = None
    ) -> np.ndarray:
        self._check_fitted()
        x = _matrix(features, "features")
        x_scaled = self.feature_scaler_.transform(self._model_features(x))
        count = n_components or self.active_components_ or len(self.regressors_)
        if count not in range(1, len(self.regressors_) + 1):
            raise ValueError(f"n_components must be in 1..{len(self.regressors_)}")
        selected = np.column_stack(
            [regressor.predict(x_scaled) for regressor in self.regressors_[:count]]
        )
        coefficients = np.zeros((len(x), len(self.regressors_)), dtype=np.float32)
        coefficients[:, :count] = selected
        return self.pca_.inverse_transform(coefficients).astype(np.float32)

    def select_components(self, count: int) -> None:
        self._check_fitted()
        if count not in range(1, len(self.regressors_) + 1):
            raise ValueError(f"count must be in 1..{len(self.regressors_)}")
        self.active_components_ = count

    @property
    def explained_variance_ratio(self) -> float:
        self._check_fitted()
        return float(self.pca_.explained_variance_ratio_.sum())

    @property
    def best_iterations(self) -> list[int]:
        self._check_fitted()
        return [
            int(getattr(regressor, "best_iteration", regressor.n_estimators - 1))
            for regressor in self.regressors_
        ]

    def save(self, path: Path) -> None:
        self._check_fitted()
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path, compress=3)

    @classmethod
    def load(cls, path: Path) -> "PCAXGBoostRegressor":
        model = joblib.load(path)
        if not isinstance(model, cls):
            raise TypeError(f"Unexpected model type in {path}")
        if not hasattr(model, "active_components_"):
            model.active_components_ = len(model.regressors_)
        return model

    def _check_fitted(self) -> None:
        if self.feature_scaler_ is None or self.pca_ is None or not self.regressors_:
            raise RuntimeError("Model must be fitted first")

    def _model_features(self, values: np.ndarray) -> np.ndarray:
        mode = getattr(self, "feature_engineering", None)
        if mode is None:
            return values
        if mode != "physical_v1":
            raise ValueError(f"Unknown feature engineering mode: {mode}")
        if values.shape[1] != 6:
            raise ValueError("physical_v1 expects the six prepared input features")
        length, thickness, bulk, source_drain, ldd, _bias = values.T
        eps = np.finfo(np.float32).eps
        derived = np.column_stack(
            (
                1.0 / np.maximum(length, eps),
                1.0 / np.maximum(thickness, eps),
                length / np.maximum(thickness, eps),
                source_drain - bulk,
                ldd - bulk,
                source_drain - ldd,
            )
        )
        return np.column_stack((values, derived)).astype(np.float32)


class BiasSeparatedPCAXGBoostRegressor:
    """Dispatch fixed-bias curves to independently trained PCA/XGBoost models."""

    def __init__(self) -> None:
        self.models_: dict[float, PCAXGBoostRegressor] = {}
        self.transformers_: dict[float, object] = {}
        self.target_modes_: dict[float, str] = {}
        self.component_selection_: dict[float, dict[str, object]] = {}

    def add_model(
        self,
        bias: float,
        model: PCAXGBoostRegressor,
        transformer: object,
        *,
        target_mode: str,
        component_selection: dict[str, object],
    ) -> None:
        key = float(bias)
        self.models_[key] = model
        self.transformers_[key] = transformer
        self.target_modes_[key] = target_mode
        self.component_selection_[key] = component_selection

    def predict_current(self, features: np.ndarray) -> np.ndarray:
        x = _matrix(features, "features")
        output: np.ndarray | None = None
        assigned = np.zeros(len(x), dtype=bool)
        for bias, model in self.models_.items():
            mask = np.isclose(x[:, -1], bias, rtol=0.0, atol=1e-6)
            if not np.any(mask):
                continue
            transformed = model.predict(x[mask])
            raw = self.transformers_[bias].inverse_transform(transformed)
            if output is None:
                output = np.empty((len(x), raw.shape[1]), dtype=np.float32)
            output[mask] = raw
            assigned[mask] = True
        if output is None or not np.all(assigned):
            unknown = np.unique(x[~assigned, -1]).tolist()
            raise ValueError(f"No fixed-bias model is available for {unknown}")
        return output

    def save(self, path: Path) -> None:
        if not self.models_:
            raise RuntimeError("Add at least one bias model before saving")
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path, compress=3)


def load_curve_regressor(
    path: Path,
) -> PCAXGBoostRegressor | BiasSeparatedPCAXGBoostRegressor:
    model = joblib.load(path)
    if not isinstance(model, (PCAXGBoostRegressor, BiasSeparatedPCAXGBoostRegressor)):
        raise TypeError(f"Unexpected model type in {path}")
    if isinstance(model, PCAXGBoostRegressor) and not hasattr(
        model, "active_components_"
    ):
        model.active_components_ = len(model.regressors_)
    return model


def _matrix(values: np.ndarray, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=np.float32)
    if array.ndim != 2 or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be a finite 2D array")
    return array
