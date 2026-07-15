from __future__ import annotations

from copy import deepcopy
from itertools import cycle
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from ai.curve_model.models.residual_mlp.model import ResidualBlock
from ai.curve_model.training.target_transforms import TargetTransformer


class SharedCurveNetwork(nn.Module):
    """Encode one device once, then decode IdVd and IdVg with separate heads."""

    def __init__(
        self,
        *,
        device_features: int = 5,
        width: int = 256,
        shared_blocks: int = 3,
        head_width: int = 256,
        dropout: float = 0.05,
        idvd_points: int = 101,
        idvg_points: int = 135,
    ) -> None:
        super().__init__()
        self.encoder_input = nn.Sequential(
            nn.Linear(device_features, width), nn.SiLU()
        )
        self.encoder_blocks = nn.Sequential(
            *(ResidualBlock(width, dropout) for _ in range(shared_blocks))
        )
        self.idvd_head = _head(width + 1, head_width, idvd_points, dropout)
        self.idvg_head = _head(width + 1, head_width, idvg_points, dropout)

    def encode(self, device: torch.Tensor) -> torch.Tensor:
        return self.encoder_blocks(self.encoder_input(device))

    def forward(
        self, kind: str, device: torch.Tensor, fixed_bias: torch.Tensor
    ) -> torch.Tensor:
        latent = self.encode(device)
        values = torch.cat((latent, fixed_bias[:, None]), dim=1)
        if kind == "idvd":
            return self.idvd_head(values)
        if kind == "idvg":
            return self.idvg_head(values)
        raise ValueError(f"Unknown curve kind: {kind}")


def _head(input_size: int, width: int, output_size: int, dropout: float) -> nn.Sequential:
    return nn.Sequential(
        nn.Linear(input_size, width),
        nn.SiLU(),
        ResidualBlock(width, dropout),
        nn.LayerNorm(width),
        nn.Linear(width, output_size),
    )


class SharedEncoderRegressor:
    def __init__(
        self,
        *,
        width: int = 256,
        shared_blocks: int = 3,
        head_width: int = 256,
        dropout: float = 0.05,
        idvd_points: int = 101,
        idvg_points: int = 135,
        random_state: int = 42,
    ) -> None:
        self.width = width
        self.shared_blocks = shared_blocks
        self.head_width = head_width
        self.dropout = dropout
        self.idvd_points = idvd_points
        self.idvg_points = idvg_points
        self.random_state = random_state
        self.feature_mean_: np.ndarray | None = None
        self.feature_scale_: np.ndarray | None = None
        self.bias_stats_: dict[str, tuple[float, float]] = {}
        self.network_: SharedCurveNetwork | None = None
        self.best_epoch_: int | None = None
        self.best_validation_loss_: float | None = None
        self.history_: list[dict[str, float | int]] = []

    def fit(
        self,
        train: dict[str, tuple[np.ndarray, np.ndarray]],
        validation: dict[str, tuple[np.ndarray, np.ndarray]],
        *,
        epochs: int = 800,
        batch_size: int = 128,
        learning_rate: float = 1e-3,
        weight_decay: float = 1e-5,
        derivative_weight: float = 0.1,
        patience: int = 80,
        device: str = "cpu",
        verbose_every: int = 25,
    ) -> "SharedEncoderRegressor":
        torch.manual_seed(self.random_state)
        np.random.seed(self.random_state)
        all_device = np.concatenate([values[0][:, :5] for values in train.values()])
        self.feature_mean_ = all_device.mean(axis=0).astype(np.float32)
        scale = all_device.std(axis=0).astype(np.float32)
        self.feature_scale_ = np.where(scale > 1e-12, scale, 1.0).astype(np.float32)
        for kind, (features, _) in train.items():
            mean = float(features[:, -1].mean())
            std = float(features[:, -1].std())
            self.bias_stats_[kind] = (mean, std if std > 1e-12 else 1.0)

        loaders = {
            kind: DataLoader(
                self._dataset(kind, *values),
                batch_size=min(batch_size, len(values[0])),
                shuffle=True,
                generator=torch.Generator().manual_seed(self.random_state + index),
            )
            for index, (kind, values) in enumerate(train.items())
        }
        validation_tensors = {
            kind: tuple(t.to(device) for t in self._dataset(kind, *values).tensors)
            for kind, values in validation.items()
        }
        network = SharedCurveNetwork(
            width=self.width,
            shared_blocks=self.shared_blocks,
            head_width=self.head_width,
            dropout=self.dropout,
            idvd_points=self.idvd_points,
            idvg_points=self.idvg_points,
        ).to(device)
        optimizer = torch.optim.AdamW(
            network.parameters(), lr=learning_rate, weight_decay=weight_decay
        )
        best_state: dict[str, torch.Tensor] | None = None
        best_loss = float("inf")
        best_epoch = 0
        stale = 0
        self.history_ = []
        kinds = tuple(loaders)
        steps = max(len(loader) for loader in loaders.values())
        for epoch in range(1, epochs + 1):
            network.train()
            iterators = {kind: cycle(loader) for kind, loader in loaders.items()}
            running = 0.0
            for _ in range(steps):
                optimizer.zero_grad(set_to_none=True)
                losses = []
                for kind in kinds:
                    device_x, bias_x, targets = next(iterators[kind])
                    prediction = network(
                        kind, device_x.to(device), bias_x.to(device)
                    )
                    losses.append(
                        _curve_loss(prediction, targets.to(device), derivative_weight)
                    )
                loss = torch.stack(losses).mean()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(network.parameters(), 5.0)
                optimizer.step()
                running += float(loss.detach())
            network.eval()
            with torch.inference_mode():
                val_losses = []
                for kind, (device_x, bias_x, targets) in validation_tensors.items():
                    val_losses.append(
                        _curve_loss(
                            network(kind, device_x, bias_x),
                            targets,
                            derivative_weight,
                        )
                    )
                validation_loss = float(torch.stack(val_losses).mean())
            training_loss = running / steps
            self.history_.append(
                {"epoch": epoch, "training_loss": training_loss, "validation_loss": validation_loss}
            )
            if validation_loss < best_loss - 1e-7:
                best_loss = validation_loss
                best_epoch = epoch
                best_state = {
                    name: value.detach().cpu().clone()
                    for name, value in network.state_dict().items()
                }
                stale = 0
            else:
                stale += 1
            if verbose_every and (epoch == 1 or epoch % verbose_every == 0 or stale >= patience):
                print(
                    f"shared epoch={epoch} train={training_loss:.6g} "
                    f"validation={validation_loss:.6g} best={best_loss:.6g}",
                    flush=True,
                )
            if stale >= patience:
                break
        if best_state is None:
            raise RuntimeError("Shared encoder training produced no checkpoint")
        network.load_state_dict(best_state)
        self.network_ = network.cpu().eval()
        self.best_epoch_ = best_epoch
        self.best_validation_loss_ = best_loss
        return self

    def predict_transformed(self, kind: str, features: np.ndarray) -> np.ndarray:
        self._check_fitted()
        dataset = self._dataset(kind, features, np.zeros((len(features), self.idvd_points if kind == "idvd" else self.idvg_points), dtype=np.float32))
        device_x, bias_x, _ = dataset.tensors
        with torch.inference_mode():
            return self.network_(kind, device_x, bias_x).numpy().astype(np.float32)

    def checkpoint(self) -> dict[str, object]:
        self._check_fitted()
        return {
            "width": self.width,
            "shared_blocks": self.shared_blocks,
            "head_width": self.head_width,
            "dropout": self.dropout,
            "idvd_points": self.idvd_points,
            "idvg_points": self.idvg_points,
            "random_state": self.random_state,
            "feature_mean": torch.from_numpy(self.feature_mean_),
            "feature_scale": torch.from_numpy(self.feature_scale_),
            "bias_stats": self.bias_stats_,
            "network_state": deepcopy(self.network_.state_dict()),
            "best_epoch": self.best_epoch_,
            "best_validation_loss": self.best_validation_loss_,
            "history": self.history_,
        }

    @classmethod
    def from_checkpoint(cls, state: dict[str, object]) -> "SharedEncoderRegressor":
        model = cls(
            width=int(state["width"]),
            shared_blocks=int(state["shared_blocks"]),
            head_width=int(state["head_width"]),
            dropout=float(state["dropout"]),
            idvd_points=int(state["idvd_points"]),
            idvg_points=int(state["idvg_points"]),
            random_state=int(state["random_state"]),
        )
        model.feature_mean_ = state["feature_mean"].numpy().astype(np.float32)
        model.feature_scale_ = state["feature_scale"].numpy().astype(np.float32)
        model.bias_stats_ = {
            str(kind): (float(values[0]), float(values[1]))
            for kind, values in state["bias_stats"].items()
        }
        model.network_ = SharedCurveNetwork(
            width=model.width,
            shared_blocks=model.shared_blocks,
            head_width=model.head_width,
            dropout=model.dropout,
            idvd_points=model.idvd_points,
            idvg_points=model.idvg_points,
        )
        model.network_.load_state_dict(state["network_state"])
        model.network_.eval()
        model.best_epoch_ = int(state["best_epoch"])
        model.best_validation_loss_ = float(state["best_validation_loss"])
        model.history_ = list(state.get("history", []))
        return model

    def _dataset(self, kind: str, features: np.ndarray, targets: np.ndarray) -> TensorDataset:
        values = np.asarray(features, dtype=np.float32)
        device_x = (values[:, :5] - self.feature_mean_) / self.feature_scale_
        mean, scale = self.bias_stats_[kind]
        bias_x = (values[:, -1] - mean) / scale
        return TensorDataset(
            torch.from_numpy(device_x.astype(np.float32)),
            torch.from_numpy(bias_x.astype(np.float32)),
            torch.from_numpy(np.asarray(targets, dtype=np.float32)),
        )

    def _check_fitted(self) -> None:
        if self.network_ is None or self.feature_mean_ is None or self.feature_scale_ is None:
            raise RuntimeError("Shared encoder must be fitted first")


class SharedCurvePredictor:
    def __init__(
        self,
        regressor: SharedEncoderRegressor,
        transformers: dict[str, dict[str, TargetTransformer]],
    ) -> None:
        self.regressor = regressor
        self.transformers = transformers

    def predict_current(self, kind: str, features: np.ndarray) -> np.ndarray:
        values = np.asarray(features, dtype=np.float32)
        transformed = self.regressor.predict_transformed(kind, values)
        mapping = self.transformers[kind]
        if "default" in mapping:
            return mapping["default"].inverse_transform(transformed)
        output = np.empty_like(transformed)
        assigned = np.zeros(len(values), dtype=bool)
        for key, transformer in mapping.items():
            mask = np.isclose(values[:, -1], float(key), atol=1e-6, rtol=0.0)
            output[mask] = transformer.inverse_transform(transformed[mask])
            assigned[mask] = True
        if not np.all(assigned):
            raise ValueError(f"Missing shared-head transform for {np.unique(values[~assigned, -1])}")
        return output

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "schema_version": 1,
                "model_family": "shared_encoder",
                "regressor": self.regressor.checkpoint(),
                "target_transforms": {
                    kind: {key: value.state_dict() for key, value in mapping.items()}
                    for kind, mapping in self.transformers.items()
                },
            },
            path,
        )

    @classmethod
    def load(cls, path: Path) -> "SharedCurvePredictor":
        state = torch.load(path, map_location="cpu", weights_only=True)
        if state.get("model_family") != "shared_encoder":
            raise TypeError(f"Unexpected shared encoder artifact: {path}")
        return cls(
            SharedEncoderRegressor.from_checkpoint(state["regressor"]),
            {
                str(kind): {
                    str(key): TargetTransformer.from_state_dict(transform)
                    for key, transform in mapping.items()
                }
                for kind, mapping in state["target_transforms"].items()
            },
        )


def _curve_loss(
    prediction: torch.Tensor, target: torch.Tensor, derivative_weight: float
) -> torch.Tensor:
    point = nn.functional.mse_loss(prediction, target)
    if derivative_weight <= 0:
        return point
    return point + derivative_weight * nn.functional.mse_loss(
        prediction[:, 1:] - prediction[:, :-1],
        target[:, 1:] - target[:, :-1],
    )
