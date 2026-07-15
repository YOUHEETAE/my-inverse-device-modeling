from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from ai.curve_model.data.current_preprocessing import (
    EVALUATION_LOG_FLOOR_MA_PER_UM,
    constrain_current_predictions,
)
from ai.curve_model.data.domain_policy import make_domain_policy
from ai.curve_model.evaluation.metrics import curve_metric_arrays
from ai.curve_model.models.pca_xgboost import (
    BiasSeparatedPCAXGBoostRegressor,
    load_curve_regressor,
)
from ai.curve_model.models.residual_mlp import ResidualCurvePredictor
from ai.curve_model.training.target_transforms import TargetTransformer


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare curve-model tail errors")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "ai" / "model_artifacts" / "curve_model" / "dataset" / "curves.npz",
    )
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--kind", choices=("idvd", "idvg"), required=True)
    parser.add_argument("--split", choices=("validation", "test"), default="test")
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def _predict(model_dir: Path, features: np.ndarray, kind: str, grid: np.ndarray) -> np.ndarray:
    kind_dir = model_dir / kind
    if (kind_dir / "model.pt").exists():
        prediction = ResidualCurvePredictor.load(
            kind_dir / "model.pt"
        ).predict_current(features)
        return constrain_current_predictions(kind, prediction, grid)
    model = load_curve_regressor(kind_dir / "model.pkl")
    if isinstance(model, BiasSeparatedPCAXGBoostRegressor):
        prediction = model.predict_current(features)
    else:
        state = json.loads((kind_dir / "target_transform.json").read_text())
        transformer = TargetTransformer.from_state_dict(state)
        prediction = transformer.inverse_transform(model.predict(features))
    return constrain_current_predictions(kind, prediction, grid)


def _summary(
    targets: np.ndarray, predictions: np.ndarray, biases: np.ndarray
) -> dict[str, object]:
    output: dict[str, object] = {}
    for bias in np.unique(biases):
        mask = np.isclose(biases, bias, rtol=0.0, atol=1e-6)
        metrics = curve_metric_arrays(
            targets[mask], predictions[mask], EVALUATION_LOG_FLOOR_MA_PER_UM
        )
        decade = metrics["decade_mae"]
        nrmse = metrics["nrmse"]
        worst_count = min(10, len(decade))
        output[str(float(bias))] = {
            "samples": int(mask.sum()),
            "mean_linear_mae": float(np.mean(metrics["linear_mae"])),
            "p95_nrmse": float(np.percentile(nrmse, 95)),
            "p99_nrmse": float(np.percentile(nrmse, 99)),
            "max_nrmse": float(np.max(nrmse)),
            "mean_decade_mae": float(np.mean(decade)),
            "p95_decade_mae": float(np.percentile(decade, 95)),
            "p99_decade_mae": float(np.percentile(decade, 99)),
            "worst10_mean_decade_mae": float(
                np.mean(np.partition(decade, -worst_count)[-worst_count:])
            ),
            "max_decade_mae": float(np.max(decade)),
        }
    return output


def main() -> None:
    args = _parse_args()
    split_index = {"validation": 1, "test": 2}[args.split]
    with np.load(args.dataset, allow_pickle=False) as arrays:
        device_indices = arrays[f"{args.kind}_device_index"]
        mask = arrays["device_split"][device_indices] == split_index
        candidate_policy_path = args.candidate / "domain_policy.json"
        candidate_policy = (
            make_domain_policy(
                str(json.loads(candidate_policy_path.read_text(encoding="utf-8"))["name"])
            )
            if candidate_policy_path.exists()
            else make_domain_policy("full")
        )
        supported = candidate_policy.supported(arrays[f"{args.kind}_x"])
        excluded_from_split = int(np.count_nonzero(mask & ~supported))
        mask &= supported
        features = arrays[f"{args.kind}_x"][mask]
        target_key = (
            f"{args.kind}_y_clean"
            if f"{args.kind}_y_clean" in arrays.files
            else f"{args.kind}_y_raw"
        )
        targets = arrays[target_key][mask]
        grid = arrays[f"{args.kind}_grid"]
        result = {
            "kind": args.kind,
            "split": args.split,
            "comparison_domain": candidate_policy.state_dict(),
            "excluded_samples_from_split": excluded_from_split,
            "baseline": _summary(
                targets, _predict(args.baseline, features, args.kind, grid), features[:, -1]
            ),
            "candidate": _summary(
                targets, _predict(args.candidate, features, args.kind, grid), features[:, -1]
            ),
        }
    rendered = json.dumps(result, indent=2)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Saved: {args.output.resolve()}")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
