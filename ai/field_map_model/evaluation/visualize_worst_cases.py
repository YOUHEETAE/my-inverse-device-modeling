from __future__ import annotations

import argparse
import csv
from pathlib import Path

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from ai.field_map_model.evaluation.visualization_app import (
    FIELD_NAMES,
    FieldMapComparison,
    render_comparison,
)


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


def main() -> None:
    root = _root()
    parser = argparse.ArgumentParser(description="Render worst full-validation field maps")
    parser.add_argument("--dataset", type=Path, default=root / "ai/model_artifacts/field_map_model/dataset/fieldmap_dataset.h5")
    parser.add_argument("--model-dir", type=Path, default=root / "ai/model_artifacts/field_map_model/baselines/coordinate_mlp")
    parser.add_argument("--metrics", type=Path, default=root / "ai/model_artifacts/field_map_model/baselines/coordinate_mlp/full_validation/device_metrics.csv")
    parser.add_argument("--output-dir", type=Path, default=root / "ai/model_artifacts/field_map_model/baselines/coordinate_mlp/full_validation/worst_cases")
    parser.add_argument("--top", type=int, default=3)
    args = parser.parse_args()
    with args.metrics.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    comparison = FieldMapComparison(args.dataset, args.model_dir)
    try:
        for field_name in FIELD_NAMES:
            ranked = sorted(rows, key=lambda row: float(row[f"{field_name}_evaluation_rmse"]), reverse=True)[:args.top]
            field_dir = args.output_dir / field_name; field_dir.mkdir(parents=True, exist_ok=True)
            for rank, row in enumerate(ranked, start=1):
                data = comparison.field_data(row["case_id"], field_name, "Physics-aware")
                figure = Figure(figsize=(15, 4.8), dpi=120); FigureCanvasAgg(figure)
                render_comparison(figure, data, "Robust 1-99%")
                figure.savefig(field_dir / f"rank_{rank:02d}.png", dpi=150, facecolor="white")
            print(f"rendered {field_name}", flush=True)
    finally:
        comparison.close()


if __name__ == "__main__":
    main()
