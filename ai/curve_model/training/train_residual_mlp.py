from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch


sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from ai.curve_model.data.current_preprocessing import constrain_current_predictions
from ai.curve_model.data.domain_policy import make_domain_policy
from ai.curve_model.evaluation.metrics import curve_evaluation_report
from ai.curve_model.models.residual_mlp import (
    ResidualCurvePredictor,
    ResidualMLPRegressor,
)
from ai.curve_model.training.target_transforms import make_target_transformer
from ai.curve_model.training.preprocessing_config import (
    bias_spec,
    fit_configured_transformer,
    kind_spec,
    load_preprocessing_config,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _parse_args() -> argparse.Namespace:
    root = _repo_root()
    parser = argparse.ArgumentParser(description="Train the residual multi-output MLP")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=root / "ai" / "model_artifacts" / "curve_model" / "dataset" / "curves.npz",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "ai" / "model_artifacts" / "curve_model" / "residual_mlp",
    )
    parser.add_argument("--kind", choices=("idvd", "idvg", "both"), default="both")
    parser.add_argument(
        "--target-mode",
        choices=("auto", "standardized_raw", "signed_log", "asinh"),
        default="auto",
    )
    parser.add_argument(
        "--domain",
        choices=("full",),
        default="full",
        help="Full prepared design domain; restricted-domain experiments are retired",
    )
    parser.add_argument("--width", type=int, default=256)
    parser.add_argument("--blocks", type=int, default=3)
    parser.add_argument("--dropout", type=float, default=0.05)
    parser.add_argument("--epochs", type=int, default=800)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-5)
    parser.add_argument("--derivative-weight", type=float, default=0.1)
    parser.add_argument("--patience", type=int, default=80)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--threads", type=int, default=0)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument(
        "--preprocessing-config",
        type=Path,
        default=None,
        help="Shared physical target-preprocessing JSON; legacy behavior when omitted",
    )
    parser.add_argument(
        "--report-test",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Write test metrics only for the locked final experiment",
    )
    return parser.parse_args()


def _device(name: str) -> str:
    if name == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if name == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not available")
    return name


def _train_kind(
    arrays: np.lib.npyio.NpzFile,
    kind: str,
    args: argparse.Namespace,
    compute_device: str,
    preprocessing_config: dict[str, object] | None,
) -> dict[str, object]:
    features = arrays[f"{kind}_x"]
    target_key = f"{kind}_y_clean" if f"{kind}_y_clean" in arrays.files else f"{kind}_y_raw"
    targets = arrays[target_key]
    sample_split = arrays["device_split"][arrays[f"{kind}_device_index"]]
    domain = make_domain_policy(args.domain)
    supported = domain.supported(features)
    train_mask = (sample_split == 0) & supported
    validation_mask = (sample_split == 1) & supported
    test_mask = (sample_split == 2) & supported
    predictor = ResidualCurvePredictor(kind)
    training: dict[str, object] = {}
    resolved_preprocessing: dict[str, object] = {}
    configured_spec = kind_spec(preprocessing_config, kind)

    if kind == "idvd" and (args.target_mode == "auto" or configured_spec is not None):
        tasks = [
            (str(float(bias)), np.isclose(features[:, -1], bias, rtol=0.0, atol=1e-6),
             "signed_log" if bias <= 1.5 + 1e-6 else "asinh")
            for bias in np.unique(features[:, -1])
        ]
    else:
        mode = "auto" if args.target_mode == "auto" else args.target_mode
        tasks = [("default", np.ones(len(features), dtype=bool), mode)]

    for task_index, (key, task_mask, mode) in enumerate(tasks):
        local_train = train_mask & task_mask
        local_validation = validation_mask & task_mask
        local_spec = (
            bias_spec(configured_spec, float(key)) if kind == "idvd" else configured_spec
        )
        if local_spec is None:
            transformer = make_target_transformer(kind, mode).fit(targets[local_train])
            resolution = transformer.state_dict()
        else:
            transformer, resolution = fit_configured_transformer(
                kind,
                targets[local_train],
                arrays[f"{kind}_grid"],
                local_spec,
            )
        resolved_preprocessing[key] = resolution
        transformed_targets = transformer.transform(targets)
        model = ResidualMLPRegressor(
            features.shape[1],
            targets.shape[1],
            width=args.width,
            blocks=args.blocks,
            dropout=args.dropout,
            random_state=args.seed + task_index,
        )
        model.fit(
            features[local_train],
            transformed_targets[local_train],
            validation_features=features[local_validation],
            validation_targets=transformed_targets[local_validation],
            epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate,
            weight_decay=args.weight_decay,
            derivative_weight=args.derivative_weight,
            patience=args.patience,
            device=compute_device,
            label=f"{kind}:{key}",
        )
        predictor.add_model(key, model, transformer)
        training[key] = {
            "target_mode": transformer.mode,
            "samples": {
                "train": int(local_train.sum()),
                "validation": int(local_validation.sum()),
            },
            "best_epoch": model.best_epoch_,
            "best_validation_loss": model.best_validation_loss_,
            "epochs_ran": len(model.history_),
        }

    kind_dir = args.output_dir / kind
    predictor.save(kind_dir / "model.pt")
    transform_state = {
        "mode": "bias_separated" if len(predictor.models_) > 1 else "single",
        "transforms": {
            key: transformer.state_dict()
            for key, transformer in predictor.transformers_.items()
        },
    }
    kind_dir.mkdir(parents=True, exist_ok=True)
    (kind_dir / "target_transform.json").write_text(
        json.dumps(transform_state, indent=2), encoding="utf-8"
    )
    inference_metadata = {
        "schema_version": 1,
        "model_family": "residual_mlp",
        "kind": kind,
        "model_file": "model.pt",
        "model_format": "pytorch_state_dict",
        "prediction_api": "raw_current",
        "input_features": [
            "L", "T", "log10_B", "log10_SD", "log10_LDD", "fixed_bias"
        ],
        "fixed_bias": "gate_v" if kind == "idvd" else "drain_v",
        "sweep_coordinate": "drain_v" if kind == "idvd" else "gate_v",
        "sweep_grid": arrays[f"{kind}_grid"].tolist(),
        "domain_policy": domain.state_dict(),
    }
    (kind_dir / "inference_metadata.json").write_text(
        json.dumps(inference_metadata, indent=2), encoding="utf-8"
    )
    result: dict[str, object] = {
        "kind": kind,
        "model_family": "residual_mlp",
        "architecture": {
            "width": args.width,
            "blocks": args.blocks,
            "dropout": args.dropout,
        },
        "optimization": {
            "batch_size": args.batch_size,
            "learning_rate": args.learning_rate,
            "weight_decay": args.weight_decay,
            "derivative_weight": args.derivative_weight,
            "patience": args.patience,
        },
        "device": compute_device,
        "preprocessing": {
            "config_name": (
                preprocessing_config.get("name")
                if preprocessing_config is not None
                else "legacy_baseline"
            ),
            "resolved": resolved_preprocessing,
        },
        "training": training,
        "samples": {
            "train": int(train_mask.sum()),
            "validation": int(validation_mask.sum()),
            "test": int(test_mask.sum()),
        },
        "library_versions": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "torch": torch.__version__,
        },
    }
    report_masks = [("validation", validation_mask)]
    if args.report_test:
        report_masks.append(("test", test_mask))
    for split_name, mask in report_masks:
        prediction = predictor.predict_current(features[mask])
        prediction = constrain_current_predictions(
            kind, prediction, arrays[f"{kind}_grid"]
        )
        result[split_name] = curve_evaluation_report(
            targets[mask], prediction, 1e-10
        )
    (kind_dir / "metrics.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def main() -> int:
    args = _parse_args()
    preprocessing_config = load_preprocessing_config(args.preprocessing_config)
    if args.threads > 0:
        torch.set_num_threads(args.threads)
    compute_device = _device(args.device)
    kinds = ("idvd", "idvg") if args.kind == "both" else (args.kind,)
    with np.load(args.dataset, allow_pickle=False) as arrays:
        results = [
            _train_kind(arrays, kind, args, compute_device, preprocessing_config)
            for kind in kinds
        ]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "domain_policy.json").write_text(
        json.dumps(make_domain_policy(args.domain).state_dict(), indent=2),
        encoding="utf-8",
    )
    if preprocessing_config is not None:
        state = dict(preprocessing_config)
        state.pop("source_file", None)
        (args.output_dir / "preprocessing_config.json").write_text(
            json.dumps(state, indent=2), encoding="utf-8"
        )
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
