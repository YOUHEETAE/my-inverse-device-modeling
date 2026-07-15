from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from ai.curve_model.evaluation.report import build_evaluation_report
from ai.curve_model.evaluation.visualization_app import EvaluationRepository


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate the trained curve model")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "ai" / "model_artifacts" / "curve_model" / "dataset" / "curves.npz",
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=ROOT / "ai" / "model_artifacts" / "curve_model" / "pca_xgboost",
    )
    parser.add_argument("--split", choices=("validation", "test"), default="validation")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--print-report", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    output = args.output or args.model_dir / "evaluation" / f"{args.split}_report.json"
    repository = EvaluationRepository(args.dataset.resolve(), args.model_dir.resolve())
    report = build_evaluation_report(repository, args.split)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.print_report:
        print(json.dumps(report, indent=2))
    else:
        summary = {
            kind: values["global"]
            for kind, values in report["curve_metrics"].items()
        }
        summary["domain_coverage"] = report["domain_coverage"]
        electrical = report["electrical_parameters"]
        summary["electrical_parameters"] = {
            "successful": electrical["successful"],
            "failed": electrical["failed"],
            "overall_score": electrical["overall_normalized_score"],
        }
        print(json.dumps(summary, indent=2))
    print(f"Saved: {output.resolve()}")


if __name__ == "__main__":
    main()
