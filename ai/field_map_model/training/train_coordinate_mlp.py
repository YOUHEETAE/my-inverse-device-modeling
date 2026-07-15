from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path

import h5py
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from ai.field_map_model.data.tecplot import ELEMENT_FIELD_NAMES
from ai.field_map_model.models.coordinate_mlp import CoordinateFieldMLP
from ai.field_map_model.training.screen_preprocessing import (
    INPUT_NAMES,
    NODE_TARGET_NAMES,
    RESOLUTION_FLOORS,
    SampleSet,
    _collect_samples,
    _evaluation_transformers,
    _metrics,
)
from ai.field_map_model.training.target_transforms import (
    FieldTransformer,
    fit_transformers,
    inverse_transform_matrix,
    transform_matrix,
)


@dataclass
class FeatureScaler:
    mean: np.ndarray
    scale: np.ndarray

    @classmethod
    def fit(cls, values: np.ndarray) -> "FeatureScaler":
        mean = np.mean(values, axis=0, dtype=np.float64)
        scale = np.std(values, axis=0, dtype=np.float64)
        scale[scale <= np.finfo(np.float64).eps] = 1.0
        return cls(mean, scale)

    def transform(self, values: np.ndarray) -> np.ndarray:
        return ((values - self.mean) / self.scale).astype(np.float32)

    def state_dict(self) -> dict[str, list[float]]:
        return {"mean": self.mean.tolist(), "scale": self.scale.tolist()}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _parse_args() -> argparse.Namespace:
    root = _repo_root()
    parser = argparse.ArgumentParser(description="Train coordinate MLP field-map baselines")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=root / "ai/model_artifacts/field_map_model/dataset/fieldmap_dataset.h5",
    )
    parser.add_argument(
        "--preprocessing-config",
        type=Path,
        default=root / "ai/field_map_model/configs/selected_preprocessing.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "ai/model_artifacts/field_map_model/baselines/coordinate_mlp",
    )
    parser.add_argument("--train-per-region", type=int, default=24)
    parser.add_argument("--validation-per-region", type=int, default=32)
    parser.add_argument("--hidden-size", type=int, default=192)
    parser.add_argument("--residual-blocks", type=int, default=4)
    parser.add_argument("--dropout", type=float, default=0.0)
    parser.add_argument("--batch-size", type=int, default=4096)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--patience", type=int, default=15)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    return parser.parse_args()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _device(requested: str) -> torch.device:
    if requested == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not available")
    return torch.device(requested)


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _target_transformers(
    targets: np.ndarray,
    field_names: tuple[str, ...],
    domain: str,
) -> list[FieldTransformer]:
    family = "signed_log1p" if domain == "node" else "asinh"
    return fit_transformers(
        targets,
        field_names,
        nonlinear_family=family,
        scaler_mode="standard",
        scale_quantile=10.0,
    )


def _predict_transformed(
    model: nn.Module,
    features: np.ndarray,
    device: torch.device,
    batch_size: int,
) -> np.ndarray:
    outputs: list[np.ndarray] = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(features), batch_size):
            batch = torch.from_numpy(features[start : start + batch_size]).to(device)
            outputs.append(model(batch).cpu().numpy())
    return np.concatenate(outputs).astype(np.float32)


def _train_domain(
    domain: str,
    field_names: tuple[str, ...],
    train: SampleSet,
    validation: SampleSet,
    args: argparse.Namespace,
    device: torch.device,
    output_dir: Path,
    field_loss_weights: np.ndarray | None = None,
    train_electric_directions: np.ndarray | None = None,
    validation_electric_directions: np.ndarray | None = None,
    physics_direction_weight: float = 0.0,
) -> dict[str, object]:
    domain_dir = output_dir / domain
    evaluation_dir = domain_dir / "evaluation"
    evaluation_dir.mkdir(parents=True, exist_ok=True)
    feature_scaler = FeatureScaler.fit(train.features)
    train_features = feature_scaler.transform(train.features)
    validation_features = feature_scaler.transform(validation.features)
    transformers = _target_transformers(train.targets, field_names, domain)
    train_targets = transform_matrix(train.targets, transformers)
    validation_targets = transform_matrix(validation.targets, transformers)

    model = CoordinateFieldMLP(
        input_size=train_features.shape[1],
        output_size=train_targets.shape[1],
        hidden_size=args.hidden_size,
        residual_blocks=args.residual_blocks,
        dropout=args.dropout,
    ).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=max(2, args.patience // 3)
    )
    if field_loss_weights is None:
        field_loss_weights = np.ones(len(field_names), dtype=np.float32)
    field_loss_weights = np.asarray(field_loss_weights, dtype=np.float32)
    field_loss_weights /= np.mean(field_loss_weights)
    loss_weights = torch.from_numpy(field_loss_weights).to(device)

    electric_parameters = [
        (
            float(transformers[index].nonlinear_scale),
            float(transformers[index].center),
            float(transformers[index].spread),
        )
        for index in (0, 1)
    ] if domain == "element" else []

    def loss_function(
        prediction: torch.Tensor,
        target: torch.Tensor,
        electric_direction: torch.Tensor | None = None,
    ) -> torch.Tensor:
        supervised = torch.mean((prediction - target) ** 2 * loss_weights)
        if electric_direction is None or physics_direction_weight <= 0.0:
            return supervised
        decoded: list[torch.Tensor] = []
        for column, (scale, center, spread) in enumerate(electric_parameters):
            nonlinear = torch.clamp(prediction[:, column] * spread + center, -30.0, 30.0)
            decoded.append(scale * torch.sinh(nonlinear))
        electric = torch.stack(decoded, dim=1)
        electric_unit = electric / torch.clamp(torch.linalg.vector_norm(electric, dim=1, keepdim=True), min=1e-20)
        cosine = torch.sum(electric_unit * electric_direction, dim=1)
        direction_loss = torch.mean(1.0 - torch.clamp(cosine, -1.0, 1.0))
        return supervised + physics_direction_weight * direction_loss
    generator = torch.Generator().manual_seed(args.seed + (0 if domain == "node" else 1))
    train_tensors = [torch.from_numpy(train_features), torch.from_numpy(train_targets)]
    if train_electric_directions is not None:
        train_tensors.append(torch.from_numpy(np.asarray(train_electric_directions, dtype=np.float32)))
    loader = DataLoader(
        TensorDataset(*train_tensors),
        batch_size=args.batch_size,
        shuffle=True,
        generator=generator,
        num_workers=0,
        pin_memory=device.type == "cuda",
    )

    validation_x = torch.from_numpy(validation_features).to(device)
    validation_y = torch.from_numpy(validation_targets).to(device)
    validation_direction = (
        torch.from_numpy(np.asarray(validation_electric_directions, dtype=np.float32)).to(device)
        if validation_electric_directions is not None else None
    )
    best_loss = float("inf")
    best_epoch = 0
    best_state: dict[str, torch.Tensor] | None = None
    epochs_without_improvement = 0
    history: list[dict[str, float | int]] = []
    started = time.perf_counter()
    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0.0
        total_samples = 0
        for batch in loader:
            batch_x, batch_y = batch[:2]
            batch_direction = batch[2].to(device, non_blocking=True) if len(batch) == 3 else None
            batch_x = batch_x.to(device, non_blocking=True)
            batch_y = batch_y.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            prediction = model(batch_x)
            loss = loss_function(prediction, batch_y, batch_direction)
            loss.backward()
            optimizer.step()
            total_loss += float(loss.detach()) * len(batch_x)
            total_samples += len(batch_x)
        train_loss = total_loss / total_samples
        model.eval()
        with torch.no_grad():
            validation_loss = float(loss_function(model(validation_x), validation_y, validation_direction))
        scheduler.step(validation_loss)
        learning_rate = float(optimizer.param_groups[0]["lr"])
        history.append(
            {
                "epoch": epoch,
                "train_mse": train_loss,
                "validation_mse": validation_loss,
                "learning_rate": learning_rate,
            }
        )
        improved = validation_loss < best_loss - 1e-7
        if improved:
            best_loss = validation_loss
            best_epoch = epoch
            best_state = copy.deepcopy(model.state_dict())
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
        if epoch == 1 or epoch % 5 == 0 or improved:
            print(
                f"[{domain}] epoch={epoch} train={train_loss:.6f} "
                f"validation={validation_loss:.6f} best={best_loss:.6f} "
                f"lr={learning_rate:.2e}",
                flush=True,
            )
        if epochs_without_improvement >= args.patience:
            print(f"[{domain}] early stopping at epoch {epoch}", flush=True)
            break
    if best_state is None:
        raise RuntimeError(f"{domain} training did not produce a checkpoint")
    model.load_state_dict(best_state)

    transformed_prediction = _predict_transformed(
        model, validation_features, device, args.batch_size
    )
    raw_prediction = inverse_transform_matrix(transformed_prediction, transformers)
    for column, field_name in enumerate(field_names):
        if field_name in {"Electrons", "Holes"}:
            raw_prediction[:, column] = np.maximum(raw_prediction[:, column], 0.0)
    evaluators = _evaluation_transformers(train.targets, field_names)
    validation_metrics = _metrics(
        validation.targets, raw_prediction, field_names, evaluators
    )
    elapsed = time.perf_counter() - started
    transformer_state = {
        name: transformers[index].state_dict() for index, name in enumerate(field_names)
    }
    checkpoint = {
        "schema_version": 1,
        "domain": domain,
        "architecture": model.architecture(),
        "model_state_dict": model.state_dict(),
        "input_names": list(INPUT_NAMES),
        "field_names": list(field_names),
        "feature_scaler": feature_scaler.state_dict(),
        "target_transformers": transformer_state,
        "field_loss_weights": dict(zip(field_names, field_loss_weights.tolist())),
        "physics_direction_weight": float(physics_direction_weight),
    }
    torch.save(checkpoint, domain_dir / "model.pt")
    (domain_dir / "feature_scaler.json").write_text(
        json.dumps(feature_scaler.state_dict(), indent=2), encoding="utf-8"
    )
    (domain_dir / "target_transform.json").write_text(
        json.dumps(transformer_state, indent=2), encoding="utf-8"
    )
    report = {
        "schema_version": 1,
        "domain": domain,
        "architecture": model.architecture(),
        "device": str(device),
        "train_samples": len(train.targets),
        "validation_samples": len(validation.targets),
        "train_devices": int(len(np.unique(train.case_indices))),
        "validation_devices": int(len(np.unique(validation.case_indices))),
        "test_cases_loaded": 0,
        "best_epoch": best_epoch,
        "best_validation_transformed_mse": best_loss,
        "elapsed_seconds": elapsed,
        "field_loss_weights": dict(zip(field_names, field_loss_weights.tolist())),
        "physics_direction_weight": float(physics_direction_weight),
        "validation_metrics": validation_metrics,
        "history": history,
    }
    (evaluation_dir / "validation_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report


def _markdown(report: dict[str, object]) -> str:
    lines = [
        "# Coordinate MLP field-map baseline",
        "",
        "The node and element models are trained separately. Test cases were not loaded.",
        "",
        "| Domain | Train points | Validation points | Best epoch | Validation score |",
        "|---|---:|---:|---:|---:|",
    ]
    for domain in ("node", "element"):
        item = report["domains"][domain]
        lines.append(
            f"| {domain} | {item['train_samples']} | {item['validation_samples']} | "
            f"{item['best_epoch']} | "
            f"{item['validation_metrics']['aggregate_mean_evaluation_rmse']:.6f} |"
        )
    for domain in ("node", "element"):
        item = report["domains"][domain]
        lines.extend(
            [
                "",
                f"## {domain.title()} fields",
                "",
                "| Field | Evaluation-space RMSE | Raw MAE | Significant sign accuracy |",
                "|---|---:|---:|---:|",
            ]
        )
        for name, metrics in item["validation_metrics"]["fields"].items():
            lines.append(
                f"| {name} | {metrics['evaluation_space_rmse']:.6f} | "
                f"{metrics['raw_mae']:.6g} | "
                f"{metrics['sign_accuracy_significant']:.6f} |"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = _parse_args()
    _set_seed(args.seed)
    device = _device(args.device)
    dataset_path = args.dataset.resolve()
    preprocessing_path = args.preprocessing_config.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    selected_config = json.loads(preprocessing_path.read_text(encoding="utf-8"))
    if selected_config["selection"]["selected_recipe"] != {
        "node": "signed_log_q10_standard",
        "element": "asinh_q10_standard",
    }:
        raise ValueError("Training code and selected preprocessing config disagree")
    print(f"Training on {device}", flush=True)
    with h5py.File(dataset_path, "r") as archive:
        splits = archive["case_split"][:]
        split_counts = {
            name: int(np.count_nonzero(splits == index))
            for index, name in enumerate(("train", "validation", "test"))
        }
        print("Collecting balanced node samples", flush=True)
        node_train = _collect_samples(
            archive, 0, "node", args.train_per_region, args.seed
        )
        node_validation = _collect_samples(
            archive, 1, "node", args.validation_per_region, args.seed
        )
        print("Collecting balanced element samples", flush=True)
        element_train = _collect_samples(
            archive, 0, "element", args.train_per_region, args.seed
        )
        element_validation = _collect_samples(
            archive, 1, "element", args.validation_per_region, args.seed
        )
    if set(node_train.case_indices).intersection(node_validation.case_indices):
        raise RuntimeError("Train/validation device leakage was detected")
    report = {
        "schema_version": 1,
        "dataset": str(dataset_path),
        "dataset_sha256": _sha256(dataset_path),
        "preprocessing_config": str(preprocessing_path),
        "preprocessing_config_sha256": _sha256(preprocessing_path),
        "split_counts": split_counts,
        "test_cases_loaded": 0,
        "evaluation_resolution_floors": RESOLUTION_FLOORS,
        "training": {
            "seed": args.seed,
            "batch_size": args.batch_size,
            "max_epochs": args.epochs,
            "patience": args.patience,
            "learning_rate": args.learning_rate,
            "weight_decay": args.weight_decay,
            "train_per_region_per_device": args.train_per_region,
            "validation_per_region_per_device": args.validation_per_region,
        },
        "domains": {},
    }
    report["domains"]["node"] = _train_domain(
        "node",
        NODE_TARGET_NAMES,
        node_train,
        node_validation,
        args,
        device,
        output_dir,
    )
    report["domains"]["element"] = _train_domain(
        "element",
        ELEMENT_FIELD_NAMES,
        element_train,
        element_validation,
        args,
        device,
        output_dir,
    )
    (output_dir / "baseline_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (output_dir / "baseline_report.md").write_text(
        _markdown(report), encoding="utf-8"
    )
    print(_markdown(report), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
