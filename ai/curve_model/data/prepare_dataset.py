from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import defaultdict
from pathlib import Path

import numpy as np


STRUCTURE_PATTERN = re.compile(r"L(?P<L>[-+0-9.eE]+)T(?P<T>[-+0-9.eE]+)$")
DOPING_PATTERN = re.compile(
    r"B(?P<B>[-+0-9.eE]+)SD(?P<SD>[-+0-9.eE]+)LDD(?P<LDD>[-+0-9.eE]+)$"
)
FEATURE_NAMES = ("L", "T", "log10_B", "log10_SD", "log10_LDD", "fixed_bias")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _parse_args() -> argparse.Namespace:
    root = _repo_root()
    parser = argparse.ArgumentParser(description="Build leakage-safe curve model arrays")
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=root / "tcad" / "data_extraction" / "dataset",
        help="Raw TCAD curve CSV directory",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "ai" / "model_artifacts" / "curve_model" / "dataset",
        help="Generated training-array directory",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train-fraction", type=float, default=0.70)
    parser.add_argument("--validation-fraction", type=float, default=0.15)
    return parser.parse_args()


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _device_features(structure_id: str, doping_id: str) -> np.ndarray:
    structure = STRUCTURE_PATTERN.fullmatch(structure_id)
    doping = DOPING_PATTERN.fullmatch(doping_id)
    if structure is None or doping is None:
        raise ValueError(f"Cannot parse device ID: {structure_id}, {doping_id}")
    length = float(structure.group("L"))
    thickness = float(structure.group("T"))
    concentrations = [float(doping.group(name)) for name in ("B", "SD", "LDD")]
    if length <= 0 or thickness <= 0 or any(value <= 0 for value in concentrations):
        raise ValueError(f"Non-positive device parameter: {structure_id}, {doping_id}")
    return np.asarray(
        [length, thickness, *(math.log10(value) for value in concentrations)],
        dtype=np.float64,
    )


def _group_curves(
    rows: list[dict[str, str]], kind: str
) -> list[tuple[float, np.ndarray, np.ndarray]]:
    x_column = "drain_v" if kind == "idvd" else "gate_v"
    fixed_column = "gate_v" if kind == "idvd" else "drain_v"
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["curve_tag"]].append(row)

    curves: list[tuple[float, np.ndarray, np.ndarray]] = []
    for tag, tag_rows in sorted(grouped.items()):
        ordered = sorted(tag_rows, key=lambda row: float(row[x_column]))
        grid = np.asarray([float(row[x_column]) for row in ordered], dtype=np.float64)
        current = np.asarray(
            [float(row["drain_current"]) for row in ordered], dtype=np.float64
        )
        fixed_values = {float(row[fixed_column]) for row in ordered}
        if len(fixed_values) != 1:
            raise ValueError(f"Fixed bias changes inside {kind}:{tag}")
        if not np.all(np.isfinite(grid)) or not np.all(np.isfinite(current)):
            raise ValueError(f"Non-finite value in {kind}:{tag}")
        if len(np.unique(grid)) != len(grid) or np.any(np.diff(grid) <= 0):
            raise ValueError(f"Invalid coordinate grid in {kind}:{tag}")
        curves.append((fixed_values.pop(), grid, current))
    return curves


def _split_devices(
    count: int, seed: int, train_fraction: float, validation_fraction: float
) -> np.ndarray:
    if count < 3:
        raise ValueError("At least three devices are required")
    if not 0 < train_fraction < 1 or not 0 < validation_fraction < 1:
        raise ValueError("Split fractions must be between zero and one")
    if train_fraction + validation_fraction >= 1:
        raise ValueError("Train and validation fractions must sum to less than one")
    order = np.random.default_rng(seed).permutation(count)
    train_end = round(count * train_fraction)
    validation_end = train_end + round(count * validation_fraction)
    split = np.full(count, 2, dtype=np.int8)
    split[order[:train_end]] = 0
    split[order[train_end:validation_end]] = 1
    return split


def _stack_curve_records(
    records: list[tuple[int, np.ndarray, float, np.ndarray, np.ndarray]], kind: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if not records:
        raise ValueError(f"No {kind} records found")
    canonical_grid = records[0][3]
    for device_index, _, _, grid, _ in records:
        if not np.array_equal(grid, canonical_grid):
            raise ValueError(f"Non-canonical {kind} grid for device index {device_index}")
    device_indices = np.asarray([record[0] for record in records], dtype=np.int32)
    features = np.stack([np.append(record[1], record[2]) for record in records]).astype(
        np.float32
    )
    targets = np.stack([record[4] for record in records]).astype(np.float32)
    return device_indices, features, targets, canonical_grid.astype(np.float32)


def build_dataset(
    dataset_dir: Path, seed: int, train: float, validation: float
) -> tuple[dict[str, np.ndarray], dict[str, object]]:
    pairs: dict[str, dict[str, Path]] = defaultdict(dict)
    for kind, suffix in (("idvd", "_IdVd.csv"), ("idvg", "_IdVg.csv")):
        for path in dataset_dir.glob(f"*{suffix}"):
            pairs[path.name.removesuffix(suffix)][kind] = path
    incomplete = [stem for stem, paths in pairs.items() if set(paths) != {"idvd", "idvg"}]
    if incomplete:
        raise ValueError(f"Incomplete IdVd/IdVg pairs: {incomplete[:5]}")

    device_ids: list[str] = []
    idvd_records: list[tuple[int, np.ndarray, float, np.ndarray, np.ndarray]] = []
    idvg_records: list[tuple[int, np.ndarray, float, np.ndarray, np.ndarray]] = []
    for device_index, (_, paths) in enumerate(sorted(pairs.items())):
        idvd_rows = _read_rows(paths["idvd"])
        if not idvd_rows:
            raise ValueError(f"Empty curve file: {paths['idvd']}")
        structure_id = idvd_rows[0]["structure_id"].strip()
        doping_id = idvd_rows[0]["doping_run_id"].strip()
        base_features = _device_features(structure_id, doping_id)
        device_ids.append(f"{structure_id}|{doping_id}")
        for fixed, grid, current in _group_curves(idvd_rows, "idvd"):
            idvd_records.append((device_index, base_features, fixed, grid, current))
        for fixed, grid, current in _group_curves(_read_rows(paths["idvg"]), "idvg"):
            idvg_records.append((device_index, base_features, fixed, grid, current))

    device_split = _split_devices(len(device_ids), seed, train, validation)
    idvd_device, idvd_x, idvd_y, idvd_grid = _stack_curve_records(idvd_records, "idvd")
    idvg_device, idvg_x, idvg_y, idvg_grid = _stack_curve_records(idvg_records, "idvg")
    split_names = np.asarray(("train", "validation", "test"))
    arrays = {
        "device_ids": np.asarray(device_ids),
        "device_split": device_split,
        "split_names": split_names,
        "idvd_device_index": idvd_device,
        "idvd_x": idvd_x,
        "idvd_y_raw": idvd_y,
        "idvd_grid": idvd_grid,
        "idvg_device_index": idvg_device,
        "idvg_x": idvg_x,
        "idvg_y_raw": idvg_y,
        "idvg_grid": idvg_grid,
    }
    counts = {
        str(name): int(np.sum(device_split == index))
        for index, name in enumerate(split_names)
    }
    metadata: dict[str, object] = {
        "schema_version": 1,
        "source_dataset": str(dataset_dir.resolve()),
        "seed": seed,
        "feature_names": list(FEATURE_NAMES),
        "feature_transforms": {"B": "log10", "SD": "log10", "LDD": "log10"},
        "target_storage": "raw drain_current in mA/um",
        "devices": len(device_ids),
        "device_split_counts": counts,
        "idvd": {"samples": len(idvd_x), "points": len(idvd_grid)},
        "idvg": {"samples": len(idvg_x), "points": len(idvg_grid)},
    }
    return arrays, metadata


def main() -> int:
    args = _parse_args()
    arrays, metadata = build_dataset(
        args.dataset_dir.resolve(),
        args.seed,
        args.train_fraction,
        args.validation_fraction,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output_dir / "curves.npz", **arrays)
    (args.output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
    print(f"Saved: {(args.output_dir / 'curves.npz').resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
