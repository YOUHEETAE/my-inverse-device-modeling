from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import sklearn
import xgboost


sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from ai.curve_model.data.current_preprocessing import (
    EVALUATION_LOG_FLOOR_MA_PER_UM,
    constrain_current_predictions,
)
from ai.curve_model.data.domain_policy import make_domain_policy
from ai.curve_model.evaluation.metrics import curve_metric_arrays
from ai.curve_model.models.pca_xgboost import (
    BiasSeparatedPCAXGBoostRegressor,
    PCAXGBoostRegressor,
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
    parser = argparse.ArgumentParser(description="Train the PCA + XGBoost baseline")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=root / "ai" / "model_artifacts" / "curve_model" / "dataset" / "curves.npz",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "ai" / "model_artifacts" / "curve_model" / "pca_xgboost",
    )
    parser.add_argument("--kind", choices=("idvd", "idvg", "both"), default="both")
    parser.add_argument(
        "--target-mode",
        choices=("auto", "standardized_raw", "signed_log", "asinh"),
        default="auto",
    )
    parser.add_argument("--components", type=int, default=16)
    parser.add_argument(
        "--component-candidates", type=int, nargs="+", default=[4, 8, 12, 16]
    )
    parser.add_argument(
        "--feature-engineering",
        choices=("auto", "none", "physical_v1"),
        default="auto",
    )
    parser.add_argument(
        "--idvd-bias-separated",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--tail-weighting",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Emphasize low-current, thick-oxide, high-doping IdVd training cases",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--domain",
        choices=("full",),
        default="full",
        help="Full prepared design domain; restricted-domain experiments are retired",
    )
    parser.add_argument(
        "--xgb-params-file",
        type=Path,
        default=None,
        help="JSON containing per-kind/per-bias XGBoost parameter overrides",
    )
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


def _metrics(
    raw_target: np.ndarray, raw_prediction: np.ndarray, log_scale: float
) -> dict[str, float]:
    difference = raw_prediction.astype(np.float64) - raw_target.astype(np.float64)
    target_log = np.sign(raw_target) * np.log1p(np.abs(raw_target) / log_scale)
    prediction_log = np.sign(raw_prediction) * np.log1p(
        np.abs(raw_prediction) / log_scale
    )
    return {
        "mae_linear": float(np.mean(np.abs(difference))),
        "rmse_linear": float(np.sqrt(np.mean(np.square(difference)))),
        "mae_signed_log": float(np.mean(np.abs(prediction_log - target_log))),
        "log_metric_scale": log_scale,
    }


def _tail_score(kind: str, fixed_bias: float, metrics: dict[str, np.ndarray]) -> float:
    decade = metrics["decade_mae"]
    nrmse = metrics["nrmse"]
    worst_count = min(10, len(decade))
    worst_decade = float(np.mean(np.partition(decade, -worst_count)[-worst_count:]))
    if kind == "idvd" and fixed_bias <= 1.5 + 1e-6:
        return float(
            np.percentile(decade, 95)
            + np.percentile(decade, 99)
            + worst_decade
            + 0.1 * np.percentile(np.minimum(nrmse, 10.0), 95)
        )
    return float(
        np.percentile(nrmse, 95)
        + np.percentile(nrmse, 99)
        + np.percentile(decade, 95)
        + 0.5 * worst_decade
    )


def _select_components(
    model: PCAXGBoostRegressor,
    transformer,
    features: np.ndarray,
    targets: np.ndarray,
    grid: np.ndarray,
    kind: str,
    fixed_bias: float,
    candidates: list[int],
) -> dict[str, object]:
    trials: list[dict[str, float | int]] = []
    maximum = len(model.regressors_)
    for count in sorted(set(value for value in candidates if 0 < value <= maximum)):
        transformed = model.predict(features, n_components=count)
        prediction = transformer.inverse_transform(transformed)
        prediction = constrain_current_predictions(kind, prediction, grid)
        metrics = curve_metric_arrays(
            targets, prediction, EVALUATION_LOG_FLOOR_MA_PER_UM
        )
        trials.append(
            {
                "components": count,
                "tail_score": _tail_score(kind, fixed_bias, metrics),
                "p95_decade_mae": float(np.percentile(metrics["decade_mae"], 95)),
                "p99_decade_mae": float(np.percentile(metrics["decade_mae"], 99)),
                "worst_decade_mae": float(np.max(metrics["decade_mae"])),
                "p95_nrmse": float(np.percentile(metrics["nrmse"], 95)),
            }
        )
    if not trials:
        raise ValueError("No valid PCA component candidate")
    best = min(trials, key=lambda item: float(item["tail_score"]))
    model.select_components(int(best["components"]))
    return {"selected": best, "candidates": trials}


def _train_bias_separated_idvd(
    features: np.ndarray,
    raw_targets: np.ndarray,
    train_mask: np.ndarray,
    validation_mask: np.ndarray,
    grid: np.ndarray,
    components: int,
    component_candidates: list[int],
    seed: int,
    feature_engineering: str | None,
    tail_weighting: bool,
    xgb_params_by_bias: dict[str, dict[str, object]],
    preprocessing_spec: dict[str, object] | None,
) -> BiasSeparatedPCAXGBoostRegressor:
    ensemble = BiasSeparatedPCAXGBoostRegressor()
    ensemble.preprocessing_resolution_ = {}
    for bias in np.unique(features[:, -1]):
        bias_mask = np.isclose(features[:, -1], bias, rtol=0.0, atol=1e-6)
        local_train = train_mask & bias_mask
        local_validation = validation_mask & bias_mask
        mode = "signed_log" if bias <= 1.5 + 1e-6 else "asinh"
        local_spec = bias_spec(preprocessing_spec, float(bias))
        if local_spec is None:
            transformer = make_target_transformer("idvd", mode).fit(
                raw_targets[local_train]
            )
            resolution = transformer.state_dict()
        else:
            transformer, resolution = fit_configured_transformer(
                "idvd", raw_targets[local_train], grid, local_spec
            )
            mode = transformer.mode
        ensemble.preprocessing_resolution_[str(float(bias))] = resolution
        transformed_targets = transformer.transform(raw_targets)
        model = PCAXGBoostRegressor(
            n_components=components,
            random_state=seed,
            feature_engineering=feature_engineering,
            xgb_params=xgb_params_by_bias.get(str(float(bias)), {}),
        )
        model.fit(
            features[local_train],
            transformed_targets[local_train],
            validation_features=features[local_validation],
            validation_targets=transformed_targets[local_validation],
            sample_weight=(
                _idvd_tail_weights(
                    features[local_train], raw_targets[local_train], float(bias)
                )
                if tail_weighting
                else None
            ),
        )
        selection = _select_components(
            model,
            transformer,
            features[local_validation],
            raw_targets[local_validation],
            grid,
            "idvd",
            float(bias),
            component_candidates,
        )
        ensemble.add_model(
            float(bias),
            model,
            transformer,
            target_mode=mode,
            component_selection=selection,
        )
    return ensemble


def _idvd_tail_weights(
    features: np.ndarray, targets: np.ndarray, fixed_bias: float
) -> np.ndarray:
    """Smoothly emphasize the difficult physical corner without naming test cases."""
    if fixed_bias > 1.5 + 1e-6:
        return np.ones(len(features), dtype=np.float32)
    amplitude = np.maximum(np.max(np.abs(targets), axis=1), 1e-10)
    log_amplitude = np.log10(amplitude)
    low_current = 2.0 * np.clip((-3.0 - log_amplitude) / 3.0, 0.0, 1.0)
    thickness = 0.5 * np.clip((features[:, 1] - 27.0) / 23.0, 0.0, 1.0)
    bulk = 0.5 * np.clip((features[:, 2] - 16.0) / 1.0, 0.0, 1.0)
    source_drain = 0.5 * np.clip((features[:, 3] - 20.0) / 0.699, 0.0, 1.0)
    ldd = 0.5 * np.clip((features[:, 4] - 18.0) / 0.699, 0.0, 1.0)
    return (1.0 + low_current + thickness + bulk + source_drain + ldd).astype(
        np.float32
    )


def _train_kind(
    arrays: np.lib.npyio.NpzFile,
    kind: str,
    output_dir: Path,
    target_mode: str,
    components: int,
    component_candidates: list[int],
    seed: int,
    feature_engineering: str | None,
    idvd_bias_separated: bool,
    tail_weighting: bool,
    domain_name: str,
    xgb_config: dict[str, object],
    preprocessing_config: dict[str, object] | None,
    report_test: bool,
) -> dict[str, object]:
    device_split = arrays["device_split"]
    sample_split = device_split[arrays[f"{kind}_device_index"]]
    features = arrays[f"{kind}_x"]
    target_key = f"{kind}_y_clean" if f"{kind}_y_clean" in arrays.files else f"{kind}_y_raw"
    raw_targets = arrays[target_key]
    domain = make_domain_policy(domain_name)
    supported = domain.supported(features)
    train_mask = (sample_split == 0) & supported
    validation_mask = (sample_split == 1) & supported
    test_mask = (sample_split == 2) & supported
    preprocessing_spec = kind_spec(preprocessing_config, kind)
    use_bias_separation = kind == "idvd" and idvd_bias_separated and (
        target_mode == "auto" or preprocessing_spec is not None
    )
    transformer = None
    if use_bias_separation:
        model = _train_bias_separated_idvd(
            features,
            raw_targets,
            train_mask,
            validation_mask,
            arrays[f"{kind}_grid"],
            components,
            component_candidates,
            seed,
            feature_engineering,
            tail_weighting,
            dict(xgb_config.get("idvd", {})),
            preprocessing_spec,
        )
        selected_mode: str | dict[str, str] = {
            str(bias): mode for bias, mode in model.target_modes_.items()
        }
    else:
        if preprocessing_spec is None:
            transformer = make_target_transformer(kind, target_mode).fit(
                raw_targets[train_mask]
            )
            preprocessing_resolution = transformer.state_dict()
        else:
            transformer, preprocessing_resolution = fit_configured_transformer(
                kind,
                raw_targets[train_mask],
                arrays[f"{kind}_grid"],
                preprocessing_spec,
            )
        selected_mode = transformer.mode
        transformed_targets = transformer.transform(raw_targets)
        model = PCAXGBoostRegressor(
            n_components=components,
            random_state=seed,
            feature_engineering=feature_engineering,
            xgb_params=dict(xgb_config.get(kind, {}).get("default", {})),
        )
        model.fit(
            features[train_mask],
            transformed_targets[train_mask],
            validation_features=features[validation_mask],
            validation_targets=transformed_targets[validation_mask],
        )
        selection = _select_components(
            model,
            transformer,
            features[validation_mask],
            raw_targets[validation_mask],
            arrays[f"{kind}_grid"],
            kind,
            float(np.median(features[validation_mask, -1])),
            component_candidates,
        )

    kind_dir = output_dir / kind
    model.save(kind_dir / "model.pkl")
    kind_dir.mkdir(parents=True, exist_ok=True)
    transform_state = (
        {
            "mode": "bias_separated",
            "bias_transforms": {
                str(bias): item.state_dict()
                for bias, item in model.transformers_.items()
            },
        }
        if use_bias_separation
        else transformer.state_dict()
    )
    (kind_dir / "target_transform.json").write_text(
        json.dumps(transform_state, indent=2), encoding="utf-8"
    )
    inference_metadata = {
        "schema_version": 1,
        "kind": kind,
        "model_file": "model.pkl",
        "model_format": "joblib",
        "target_transform_file": "target_transform.json",
        "input_features": [
            "L",
            "T",
            "log10_B",
            "log10_SD",
            "log10_LDD",
            "fixed_bias",
        ],
        "fixed_bias": "gate_v" if kind == "idvd" else "drain_v",
        "sweep_coordinate": "drain_v" if kind == "idvd" else "gate_v",
        "sweep_grid": arrays[f"{kind}_grid"].tolist(),
        "prediction_api": "raw_current" if use_bias_separation else "transformed_target",
        "feature_engineering": feature_engineering,
        "preprocessing": {
            "config_name": (
                preprocessing_config.get("name")
                if preprocessing_config is not None
                else "legacy_baseline"
            ),
            "resolved": (
                model.preprocessing_resolution_
                if use_bias_separation
                else {"default": preprocessing_resolution}
            ),
        },
        "tail_weighting": bool(use_bias_separation and tail_weighting),
        "domain_policy": domain.state_dict(),
        "xgboost_parameter_overrides": xgb_config.get(kind, {}),
    }
    (kind_dir / "inference_metadata.json").write_text(
        json.dumps(inference_metadata, indent=2), encoding="utf-8"
    )
    results: dict[str, object] = {
        "kind": kind,
        "target_mode": selected_mode,
        "pca_components": (
            {str(bias): child.active_components_ for bias, child in model.models_.items()}
            if use_bias_separation
            else model.active_components_
        ),
        "component_selection": (
            {str(bias): value for bias, value in model.component_selection_.items()}
            if use_bias_separation
            else selection
        ),
        "pca_explained_variance_ratio": (
            {str(bias): child.explained_variance_ratio for bias, child in model.models_.items()}
            if use_bias_separation
            else model.explained_variance_ratio
        ),
        "xgboost_best_iterations": (
            {str(bias): child.best_iterations for bias, child in model.models_.items()}
            if use_bias_separation
            else model.best_iterations
        ),
        "feature_engineering": feature_engineering,
        "preprocessing": {
            "config_name": (
                preprocessing_config.get("name")
                if preprocessing_config is not None
                else "legacy_baseline"
            ),
            "resolved": (
                model.preprocessing_resolution_
                if use_bias_separation
                else {"default": preprocessing_resolution}
            ),
        },
        "library_versions": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
            "xgboost": xgboost.__version__,
            "joblib": joblib.__version__,
        },
        "samples": {
            "train": int(train_mask.sum()),
            "validation": int(validation_mask.sum()),
            "test": int(test_mask.sum()),
        },
    }
    report_masks = [("validation", validation_mask)]
    if report_test:
        report_masks.append(("test", test_mask))
    for name, mask in report_masks:
        if use_bias_separation:
            raw_prediction = model.predict_current(features[mask])
        else:
            transformed_prediction = model.predict(features[mask])
            raw_prediction = transformer.inverse_transform(transformed_prediction)
        raw_prediction = constrain_current_predictions(
            kind, raw_prediction, arrays[f"{kind}_grid"]
        )
        results[name] = _metrics(
            raw_targets[mask],
            raw_prediction,
            EVALUATION_LOG_FLOOR_MA_PER_UM,
        )
    (kind_dir / "metrics.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    return results


def main() -> int:
    args = _parse_args()
    preprocessing_config = load_preprocessing_config(args.preprocessing_config)
    xgb_config: dict[str, object] = {}
    if args.xgb_params_file is not None:
        xgb_config = json.loads(args.xgb_params_file.read_text(encoding="utf-8"))
    kinds = ("idvd", "idvg") if args.kind == "both" else (args.kind,)
    with np.load(args.dataset, allow_pickle=False) as arrays:
        results = [
            _train_kind(
                arrays,
                kind,
                args.output_dir,
                args.target_mode,
                args.components,
                args.component_candidates,
                args.seed,
                (
                    "physical_v1"
                    if args.feature_engineering == "auto" and kind == "idvd"
                    else None
                    if args.feature_engineering in {"auto", "none"}
                    else args.feature_engineering
                ),
                args.idvd_bias_separated,
                args.tail_weighting,
                args.domain,
                xgb_config,
                preprocessing_config,
                args.report_test,
            )
            for kind in kinds
        ]
    policy = make_domain_policy(args.domain)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "domain_policy.json").write_text(
        json.dumps(policy.state_dict(), indent=2), encoding="utf-8"
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
