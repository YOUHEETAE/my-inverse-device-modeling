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
from ai.curve_model.models.shared_encoder import (
    SharedCurvePredictor,
    SharedEncoderRegressor,
)
from ai.curve_model.training.preprocessing_config import (
    bias_spec,
    fit_configured_transformer,
    kind_spec,
    load_preprocessing_config,
)
from ai.curve_model.training.target_transforms import make_target_transformer


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train shared device encoder with IdVd/IdVg heads")
    parser.add_argument("--dataset", type=Path, default=_root() / "ai/model_artifacts/curve_model/dataset/curves.npz")
    parser.add_argument("--output-dir", type=Path, default=_root() / "ai/model_artifacts/curve_model/shared_encoder")
    parser.add_argument("--preprocessing-config", type=Path, default=None)
    parser.add_argument(
        "--domain",
        choices=("full",),
        default="full",
        help="Full prepared design domain; restricted-domain experiments are retired",
    )
    parser.add_argument("--width", type=int, default=256)
    parser.add_argument("--shared-blocks", type=int, default=3)
    parser.add_argument("--head-width", type=int, default=256)
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
        "--report-test",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Write test metrics only for the locked final experiment",
    )
    return parser.parse_args()


def _compute_device(value: str) -> str:
    if value == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if value == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    return value


def _fit_targets(
    arrays: np.lib.npyio.NpzFile,
    kind: str,
    train_mask: np.ndarray,
    config: dict[str, object] | None,
) -> tuple[np.ndarray, dict[str, object], dict[str, object]]:
    targets = arrays[f"{kind}_y_clean"]
    features = arrays[f"{kind}_x"]
    spec = kind_spec(config, kind)
    transformers: dict[str, object] = {}
    resolutions: dict[str, object] = {}
    transformed = np.empty_like(targets, dtype=np.float32)
    keys = np.unique(features[:, -1]) if kind == "idvd" else np.asarray([np.nan])
    for bias in keys:
        key = str(float(bias)) if kind == "idvd" else "default"
        task = (
            np.isclose(features[:, -1], bias, atol=1e-6, rtol=0.0)
            if kind == "idvd"
            else np.ones(len(features), dtype=bool)
        )
        local_train = train_mask & task
        local_spec = bias_spec(spec, float(bias)) if kind == "idvd" else spec
        if local_spec is not None:
            transformer, resolution = fit_configured_transformer(
                kind, targets[local_train], arrays[f"{kind}_grid"], local_spec
            )
        else:
            mode = (
                "signed_log"
                if kind == "idvg" or float(bias) <= 1.5 + 1e-6
                else "asinh"
            )
            transformer = make_target_transformer(kind, mode).fit(targets[local_train])
            resolution = transformer.state_dict()
        transformed[task] = transformer.transform(targets[task])
        transformers[key] = transformer
        resolutions[key] = resolution
    return transformed, transformers, resolutions


def main() -> int:
    args = _args()
    if args.threads > 0:
        torch.set_num_threads(args.threads)
    config = load_preprocessing_config(args.preprocessing_config)
    compute_device = _compute_device(args.device)
    policy = make_domain_policy(args.domain)
    with np.load(args.dataset, allow_pickle=False) as arrays:
        masks: dict[str, dict[str, np.ndarray]] = {}
        transformed: dict[str, np.ndarray] = {}
        transformers: dict[str, dict[str, object]] = {}
        resolutions: dict[str, object] = {}
        for kind in ("idvd", "idvg"):
            features = arrays[f"{kind}_x"]
            sample_split = arrays["device_split"][arrays[f"{kind}_device_index"]]
            supported = policy.supported(features)
            masks[kind] = {
                "train": (sample_split == 0) & supported,
                "validation": (sample_split == 1) & supported,
                "test": (sample_split == 2) & supported,
            }
            transformed[kind], transformers[kind], resolutions[kind] = _fit_targets(
                arrays, kind, masks[kind]["train"], config
            )
        regressor = SharedEncoderRegressor(
            width=args.width,
            shared_blocks=args.shared_blocks,
            head_width=args.head_width,
            dropout=args.dropout,
            idvd_points=len(arrays["idvd_grid"]),
            idvg_points=len(arrays["idvg_grid"]),
            random_state=args.seed,
        ).fit(
            {
                kind: (arrays[f"{kind}_x"][masks[kind]["train"]], transformed[kind][masks[kind]["train"]])
                for kind in ("idvd", "idvg")
            },
            {
                kind: (arrays[f"{kind}_x"][masks[kind]["validation"]], transformed[kind][masks[kind]["validation"]])
                for kind in ("idvd", "idvg")
            },
            epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate,
            weight_decay=args.weight_decay,
            derivative_weight=args.derivative_weight,
            patience=args.patience,
            device=compute_device,
        )
        predictor = SharedCurvePredictor(regressor, transformers)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        predictor.save(args.output_dir / "model.pt")
        result: dict[str, object] = {
            "model_family": "shared_encoder",
            "architecture": {
                "width": args.width,
                "shared_blocks": args.shared_blocks,
                "head_width": args.head_width,
                "dropout": args.dropout,
            },
            "optimization": {
                "batch_size": args.batch_size,
                "learning_rate": args.learning_rate,
                "weight_decay": args.weight_decay,
                "derivative_weight": args.derivative_weight,
                "patience": args.patience,
            },
            "training": {
                "best_epoch": regressor.best_epoch_,
                "best_validation_loss": regressor.best_validation_loss_,
                "epochs_ran": len(regressor.history_),
            },
            "preprocessing": {
                "config_name": config.get("name") if config else "legacy_baseline",
                "resolved": resolutions,
            },
            "device": compute_device,
            "kinds": {},
        }
        for kind in ("idvd", "idvg"):
            kind_result: dict[str, object] = {
                "samples": {name: int(mask.sum()) for name, mask in masks[kind].items()}
            }
            report_splits = ["validation"] + (["test"] if args.report_test else [])
            for split in report_splits:
                mask = masks[kind][split]
                prediction = constrain_current_predictions(
                    kind,
                    predictor.predict_current(kind, arrays[f"{kind}_x"][mask]),
                    arrays[f"{kind}_grid"],
                )
                kind_result[split] = curve_evaluation_report(
                    arrays[f"{kind}_y_clean"][mask], prediction, 1e-10
                )
            result["kinds"][kind] = kind_result
            kind_dir = args.output_dir / kind
            kind_dir.mkdir(parents=True, exist_ok=True)
            (kind_dir / "metrics.json").write_text(
                json.dumps({"kind": kind, **kind_result}, indent=2), encoding="utf-8"
            )
            (kind_dir / "target_transform.json").write_text(
                json.dumps(
                    {
                        "mode": "bias_separated" if len(transformers[kind]) > 1 else "single",
                        "transforms": {key: value.state_dict() for key, value in transformers[kind].items()},
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        (args.output_dir / "metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        (args.output_dir / "domain_policy.json").write_text(json.dumps(policy.state_dict(), indent=2), encoding="utf-8")
        if config is not None:
            state = dict(config)
            state.pop("source_file", None)
            (args.output_dir / "preprocessing_config.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(json.dumps({"saved": str(args.output_dir.resolve()), "best_epoch": regressor.best_epoch_}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
