from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from ai.curve_model.training.target_transforms import TargetTransformer


class ResidualBlock(nn.Module):
    def __init__(self, width: int, dropout: float) -> None:
        super().__init__()
        self.block = nn.Sequential(
            nn.LayerNorm(width),
            nn.Linear(width, width * 2),
            nn.SiLU(),
            nn.Dropout(dropout),
            nn.Linear(width * 2, width),
        )

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        return values + self.block(values)


class ResidualCurveMLP(nn.Module):
    """Directly predict every point of one transformed IdVd or IdVg curve."""

    def __init__(
        self,
        input_size: int,
        output_size: int,
        width: int = 256,
        blocks: int = 3,
        dropout: float = 0.05,
    ) -> None:
        super().__init__()
        self.input = nn.Sequential(nn.Linear(input_size, width), nn.SiLU())
        self.residual = nn.Sequential(
            *(ResidualBlock(width, dropout) for _ in range(blocks))
        )
        self.output = nn.Sequential(nn.LayerNorm(width), nn.Linear(width, output_size))

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.output(self.residual(self.input(features)))


class ResidualMLPRegressor:
    """Train and serialize one normalized-feature, transformed-target MLP."""

    def __init__(
        self,
        input_size: int,
        output_size: int,
        *,
        width: int = 256,
        blocks: int = 3,
        dropout: float = 0.05,
        random_state: int = 42,
    ) -> None:
        self.input_size = input_size
        self.output_size = output_size
        self.width = width
        self.blocks = blocks
        self.dropout = dropout
        self.random_state = random_state
        self.feature_mean_: np.ndarray | None = None
        self.feature_scale_: np.ndarray | None = None
        self.network_: ResidualCurveMLP | None = None
        self.best_epoch_: int | None = None
        self.best_validation_loss_: float | None = None
        self.history_: list[dict[str, float | int]] = []

    def fit(
        self,
        features: np.ndarray,
        targets: np.ndarray,
        *,
        validation_features: np.ndarray,
        validation_targets: np.ndarray,
        epochs: int = 800,
        batch_size: int = 128,
        learning_rate: float = 1e-3,
        weight_decay: float = 1e-5,
        derivative_weight: float = 0.1,
        patience: int = 80,
        device: str = "cpu",
        verbose_every: int = 25,
        label: str = "residual_mlp",
    ) -> "ResidualMLPRegressor":
        x = _matrix(features, "features")
        y = _matrix(targets, "targets")
        val_x = _matrix(validation_features, "validation_features")
        val_y = _matrix(validation_targets, "validation_targets")
        if len(x) != len(y) or len(val_x) != len(val_y):
            raise ValueError("Feature and target sample counts must match")
        if x.shape[1] != self.input_size or y.shape[1] != self.output_size:
            raise ValueError("Configured input/output size does not match training arrays")

        torch.manual_seed(self.random_state)
        np.random.seed(self.random_state)
        self.feature_mean_ = x.mean(axis=0, dtype=np.float64).astype(np.float32)
        scale = x.std(axis=0, dtype=np.float64).astype(np.float32)
        self.feature_scale_ = np.where(scale > 1e-12, scale, 1.0).astype(np.float32)
        train_x = self._normalize(x)
        validation_x = self._normalize(val_x)
        train_dataset = TensorDataset(
            torch.from_numpy(train_x), torch.from_numpy(y.astype(np.float32))
        )
        generator = torch.Generator().manual_seed(self.random_state)
        loader = DataLoader(
            train_dataset,
            batch_size=min(batch_size, len(train_dataset)),
            shuffle=True,
            generator=generator,
        )
        compute_device = torch.device(device)
        network = ResidualCurveMLP(
            self.input_size,
            self.output_size,
            width=self.width,
            blocks=self.blocks,
            dropout=self.dropout,
        ).to(compute_device)
        optimizer = torch.optim.AdamW(
            network.parameters(), lr=learning_rate, weight_decay=weight_decay
        )
        val_features_tensor = torch.from_numpy(validation_x).to(compute_device)
        val_targets_tensor = torch.from_numpy(val_y.astype(np.float32)).to(
            compute_device
        )
        best_state: dict[str, torch.Tensor] | None = None
        best_loss = float("inf")
        best_epoch = 0
        stale_epochs = 0
        self.history_ = []
        for epoch in range(1, epochs + 1):
            network.train()
            total = 0.0
            seen = 0
            for batch_features, batch_targets in loader:
                batch_features = batch_features.to(compute_device)
                batch_targets = batch_targets.to(compute_device)
                optimizer.zero_grad(set_to_none=True)
                prediction = network(batch_features)
                loss = _curve_loss(prediction, batch_targets, derivative_weight)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(network.parameters(), max_norm=5.0)
                optimizer.step()
                total += float(loss.detach()) * len(batch_features)
                seen += len(batch_features)
            network.eval()
            with torch.inference_mode():
                validation_prediction = network(val_features_tensor)
                validation_loss = float(
                    _curve_loss(
                        validation_prediction,
                        val_targets_tensor,
                        derivative_weight,
                    )
                )
            training_loss = total / max(seen, 1)
            self.history_.append(
                {
                    "epoch": epoch,
                    "training_loss": training_loss,
                    "validation_loss": validation_loss,
                }
            )
            if validation_loss < best_loss - 1e-7:
                best_loss = validation_loss
                best_epoch = epoch
                best_state = {
                    name: value.detach().cpu().clone()
                    for name, value in network.state_dict().items()
                }
                stale_epochs = 0
            else:
                stale_epochs += 1
            if verbose_every > 0 and (
                epoch == 1 or epoch % verbose_every == 0 or stale_epochs >= patience
            ):
                print(
                    f"{label} epoch={epoch} train={training_loss:.6g} "
                    f"validation={validation_loss:.6g} best={best_loss:.6g}",
                    flush=True,
                )
            if stale_epochs >= patience:
                break
        if best_state is None:
            raise RuntimeError("Residual MLP training did not produce a valid checkpoint")
        network.load_state_dict(best_state)
        self.network_ = network.cpu().eval()
        self.best_epoch_ = best_epoch
        self.best_validation_loss_ = best_loss
        return self

    def predict_transformed(
        self, features: np.ndarray, *, batch_size: int = 512
    ) -> np.ndarray:
        self._check_fitted()
        x = self._normalize(_matrix(features, "features"))
        output: list[np.ndarray] = []
        self.network_.eval()
        with torch.inference_mode():
            for start in range(0, len(x), batch_size):
                prediction = self.network_(torch.from_numpy(x[start : start + batch_size]))
                output.append(prediction.numpy())
        return np.concatenate(output, axis=0).astype(np.float32)

    def checkpoint(self) -> dict[str, object]:
        self._check_fitted()
        return {
            "input_size": self.input_size,
            "output_size": self.output_size,
            "width": self.width,
            "blocks": self.blocks,
            "dropout": self.dropout,
            "random_state": self.random_state,
            "feature_mean": torch.from_numpy(self.feature_mean_),
            "feature_scale": torch.from_numpy(self.feature_scale_),
            "network_state": deepcopy(self.network_.state_dict()),
            "best_epoch": self.best_epoch_,
            "best_validation_loss": self.best_validation_loss_,
            "history": self.history_,
        }

    @classmethod
    def from_checkpoint(cls, state: dict[str, object]) -> "ResidualMLPRegressor":
        regressor = cls(
            int(state["input_size"]),
            int(state["output_size"]),
            width=int(state["width"]),
            blocks=int(state["blocks"]),
            dropout=float(state["dropout"]),
            random_state=int(state["random_state"]),
        )
        regressor.feature_mean_ = state["feature_mean"].numpy().astype(np.float32)
        regressor.feature_scale_ = state["feature_scale"].numpy().astype(np.float32)
        regressor.network_ = ResidualCurveMLP(
            regressor.input_size,
            regressor.output_size,
            width=regressor.width,
            blocks=regressor.blocks,
            dropout=regressor.dropout,
        )
        regressor.network_.load_state_dict(state["network_state"])
        regressor.network_.eval()
        regressor.best_epoch_ = int(state["best_epoch"])
        regressor.best_validation_loss_ = float(state["best_validation_loss"])
        regressor.history_ = list(state.get("history", []))
        return regressor

    def _normalize(self, features: np.ndarray) -> np.ndarray:
        if self.feature_mean_ is None or self.feature_scale_ is None:
            raise RuntimeError("Feature normalization is not fitted")
        return ((features - self.feature_mean_) / self.feature_scale_).astype(np.float32)

    def _check_fitted(self) -> None:
        if self.network_ is None or self.feature_mean_ is None or self.feature_scale_ is None:
            raise RuntimeError("Residual MLP must be fitted first")


class ResidualCurvePredictor:
    """Inference artifact that returns raw-current curves for one curve kind."""

    def __init__(self, kind: str) -> None:
        self.kind = kind
        self.models_: dict[str, ResidualMLPRegressor] = {}
        self.transformers_: dict[str, TargetTransformer] = {}

    def add_model(
        self,
        key: str,
        model: ResidualMLPRegressor,
        transformer: TargetTransformer,
    ) -> None:
        self.models_[key] = model
        self.transformers_[key] = transformer

    def predict_current(self, features: np.ndarray) -> np.ndarray:
        x = _matrix(features, "features")
        if "default" in self.models_:
            transformed = self.models_["default"].predict_transformed(x)
            return self.transformers_["default"].inverse_transform(transformed)
        output: np.ndarray | None = None
        assigned = np.zeros(len(x), dtype=bool)
        for key, model in self.models_.items():
            bias = float(key)
            mask = np.isclose(x[:, -1], bias, rtol=0.0, atol=1e-6)
            if not np.any(mask):
                continue
            transformed = model.predict_transformed(x[mask])
            raw = self.transformers_[key].inverse_transform(transformed)
            if output is None:
                output = np.empty((len(x), raw.shape[1]), dtype=np.float32)
            output[mask] = raw
            assigned[mask] = True
        if output is None or not np.all(assigned):
            unknown = np.unique(x[~assigned, -1]).tolist()
            raise ValueError(f"No residual MLP is available for fixed biases {unknown}")
        return output

    def save(self, path: Path) -> None:
        if not self.models_:
            raise RuntimeError("Add at least one residual MLP before saving")
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "schema_version": 1,
                "model_family": "residual_mlp",
                "kind": self.kind,
                "models": {
                    key: model.checkpoint() for key, model in self.models_.items()
                },
                "target_transforms": {
                    key: transformer.state_dict()
                    for key, transformer in self.transformers_.items()
                },
            },
            path,
        )

    @classmethod
    def load(cls, path: Path) -> "ResidualCurvePredictor":
        state = torch.load(path, map_location="cpu", weights_only=True)
        if state.get("model_family") != "residual_mlp":
            raise TypeError(f"Unexpected residual MLP artifact: {path}")
        predictor = cls(str(state["kind"]))
        for key, model_state in state["models"].items():
            predictor.add_model(
                str(key),
                ResidualMLPRegressor.from_checkpoint(model_state),
                TargetTransformer.from_state_dict(state["target_transforms"][key]),
            )
        return predictor


def _curve_loss(
    prediction: torch.Tensor, target: torch.Tensor, derivative_weight: float
) -> torch.Tensor:
    point_loss = nn.functional.mse_loss(prediction, target)
    if derivative_weight <= 0 or prediction.shape[1] < 2:
        return point_loss
    prediction_slope = prediction[:, 1:] - prediction[:, :-1]
    target_slope = target[:, 1:] - target[:, :-1]
    return point_loss + derivative_weight * nn.functional.mse_loss(
        prediction_slope, target_slope
    )


def _matrix(values: np.ndarray, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=np.float32)
    if array.ndim != 2 or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be a finite 2D array")
    return array
