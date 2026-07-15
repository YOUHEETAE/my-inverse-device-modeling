from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import h5py
import numpy as np

from ai.field_map_model.data.tecplot import ELEMENT_FIELD_NAMES
from ai.field_map_model.training.screen_preprocessing import SampleSet, _coordinate_features
from ai.field_map_model.training.train_coordinate_mlp import _device, _set_seed, _train_domain


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


def _args() -> argparse.Namespace:
    root = _root()
    parser = argparse.ArgumentParser(description="Train a bulk/channel-focused element MLP")
    parser.add_argument("--dataset", type=Path, default=root / "ai/model_artifacts/field_map_model/dataset/fieldmap_dataset.h5")
    parser.add_argument("--baseline-dir", type=Path, default=root / "ai/model_artifacts/field_map_model/baselines/coordinate_mlp")
    parser.add_argument("--output-dir", type=Path, default=root / "ai/model_artifacts/field_map_model/candidates/element_bulk_focused")
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


def _choose(candidates: np.ndarray, count: int, rng: np.random.Generator) -> np.ndarray:
    if not len(candidates) or count <= 0:
        return np.empty(0, dtype=np.int64)
    return rng.choice(candidates, size=min(count, len(candidates)), replace=False)


def _stratified_indices(
    coordinates_nm: np.ndarray,
    regions: np.ndarray,
    split: str,
    rng: np.random.Generator,
) -> np.ndarray:
    # Preserve the baseline point budget: 72 train / 96 validation per device.
    quotas = (32, 20, 8, 6, 6) if split == "train" else (44, 24, 8, 10, 10)
    surface_count, mid_count, deep_count, oxide_count, gate_count = quotas
    y = coordinates_nm[:, 1]
    bulk = regions == 0
    surface = np.flatnonzero(bulk & (y <= 100.0))
    middle = np.flatnonzero(bulk & (y > 100.0) & (y <= 500.0))
    deep = np.flatnonzero(bulk & (y > 500.0))
    selected = np.concatenate((
        _choose(surface, surface_count, rng),
        _choose(middle, mid_count, rng),
        _choose(deep, deep_count, rng),
        _choose(np.flatnonzero(regions == 1), oxide_count, rng),
        _choose(np.flatnonzero(regions == 2), gate_count, rng),
    ))
    return np.unique(selected)


def _negative_potential_direction(
    potential: np.ndarray, coordinates_nm: np.ndarray, triangles: np.ndarray
) -> np.ndarray:
    xy = np.asarray(coordinates_nm, dtype=np.float64) * 1e-7
    points = xy[triangles]; values = np.asarray(potential, dtype=np.float64)[triangles]
    x0, x1, x2 = points[:, 0, 0], points[:, 1, 0], points[:, 2, 0]
    y0, y1, y2 = points[:, 0, 1], points[:, 1, 1], points[:, 2, 1]
    denominator = x0*(y1-y2) + x1*(y2-y0) + x2*(y0-y1)
    gx = (values[:, 0]*(y1-y2) + values[:, 1]*(y2-y0) + values[:, 2]*(y0-y1)) / denominator
    gy = (values[:, 0]*(x2-x1) + values[:, 1]*(x0-x2) + values[:, 2]*(x1-x0)) / denominator
    direction = -np.column_stack((gx, gy))
    norm = np.linalg.norm(direction, axis=1, keepdims=True)
    return (direction / np.maximum(norm, 1e-30)).astype(np.float32)


def _collect(archive: h5py.File, split_index: int, seed: int) -> tuple[SampleSet, np.ndarray]:
    features: list[np.ndarray] = []; targets: list[np.ndarray] = []; cases: list[np.ndarray] = []
    directions: list[np.ndarray] = []
    case_keys = archive["case_keys"].asstr()[:]
    split_name = "train" if split_index == 0 else "validation"
    for case_index in np.flatnonzero(archive["case_split"][:] == split_index):
        case = archive[f"cases/{case_keys[case_index]}"]
        mesh = archive[f"meshes/{case.attrs['structure_id']}"]
        coordinates = mesh["element_centroid_xy_nm"][:]
        regions = mesh["element_region"][:]
        indices = _stratified_indices(coordinates, regions, split_name, np.random.default_rng(seed + int(case_index)*17 + 1))
        triangles = mesh["triangles"][indices]
        doping = case["node_fields"][:, 0][triangles].mean(axis=1)
        features.append(_coordinate_features(case["device_features"][:], coordinates[indices], regions[indices], doping, mesh["node_xy_nm"][:]))
        targets.append(case["element_fields"][indices])
        cases.append(np.full(len(indices), case_index, dtype=np.int32))
        directions.append(_negative_potential_direction(case["node_fields"][:, 1], mesh["node_xy_nm"][:], triangles))
    return SampleSet(np.concatenate(features), np.concatenate(targets), np.concatenate(cases)), np.concatenate(directions)


def main() -> None:
    args = _args(); _set_seed(args.seed); args.output_dir.mkdir(parents=True, exist_ok=True)
    device = _device(args.device)
    print(f"Training element candidate on {device}", flush=True)
    with h5py.File(args.dataset, "r") as archive:
        train, _train_directions = _collect(archive, 0, args.seed)
        validation, _validation_directions = _collect(archive, 1, args.seed)
    print(f"samples train={len(train.targets)} validation={len(validation.targets)}", flush=True)
    weights = np.asarray([1.15, 1.10, 0.90, 1.55, 0.85, 0.95], dtype=np.float32)
    report = _train_domain("element", ELEMENT_FIELD_NAMES, train, validation, args, device, args.output_dir, weights)
    source_node = args.baseline_dir / "node"; destination_node = args.output_dir / "node"
    if destination_node.exists(): shutil.rmtree(destination_node)
    shutil.copytree(source_node, destination_node)
    summary = {
        "name": "element_bulk_focused",
        "test_cases_loaded": 0,
        "sampling": {"train": {"surface_bulk": 32, "mid_bulk": 20, "deep_bulk": 8, "oxide": 6, "gate": 6}, "validation": {"surface_bulk": 44, "mid_bulk": 24, "deep_bulk": 8, "oxide": 10, "gate": 10}},
        "field_loss_weights": dict(zip(ELEMENT_FIELD_NAMES, weights.tolist())),
        "element_report": report,
        "node_model": "copied unchanged from coordinate_mlp baseline",
    }
    (args.output_dir / "candidate_report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(args.output_dir / "candidate_report.json")


if __name__ == "__main__":
    main()
