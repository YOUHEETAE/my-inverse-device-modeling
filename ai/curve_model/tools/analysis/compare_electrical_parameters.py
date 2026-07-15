from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from ai.curve_model.evaluation.electrical_parameters import (
    evaluate_parameters,
    parameter_evaluation_report,
)
from ai.curve_model.evaluation.visualization_app import EvaluationRepository


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare electrical-parameter errors on one shared model domain"
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "ai" / "model_artifacts" / "curve_model" / "dataset" / "curves.npz",
    )
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--split", choices=("validation", "test"), default="test")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    baseline = EvaluationRepository(args.dataset.resolve(), args.baseline.resolve())
    candidate = EvaluationRepository(args.dataset.resolve(), args.candidate.resolve())
    split_index = {"validation": 1, "test": 2}[args.split]
    device_mask = (
        (candidate.arrays["device_split"] == split_index)
        & candidate.domain_policy.supported(candidate.arrays["device_features"])
    )
    devices = [int(value) for value in np.flatnonzero(device_mask)]
    baseline_results = evaluate_parameters(
        devices, baseline.bundle("idvd", args.split), baseline.bundle("idvg", args.split)
    )
    candidate_results = evaluate_parameters(
        devices, candidate.bundle("idvd", args.split), candidate.bundle("idvg", args.split)
    )
    report = {
        "split": args.split,
        "devices": len(devices),
        "comparison_domain": candidate.domain_policy.state_dict(),
        "baseline": parameter_evaluation_report(baseline_results),
        "candidate": parameter_evaluation_report(candidate_results),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved: {args.output.resolve()}")


if __name__ == "__main__":
    main()
