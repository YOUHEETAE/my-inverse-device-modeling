from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path

import h5py
import numpy as np
from sklearn.ensemble import ExtraTreesRegressor

from ai.field_map_model.data.tecplot import ELEMENT_FIELD_NAMES, NODE_FIELD_NAMES
from ai.field_map_model.training.target_transforms import (
    FieldTransformer,
    characteristic_scale,
    fit_transformers,
    inverse_transform_matrix,
    transform_matrix,
)


NODE_TARGET_NAMES = tuple(name for name in NODE_FIELD_NAMES if name != "NetDoping")
INPUT_NAMES = (
    "L_um",
    "Tox_over_50nm",
    "log10_B_minus_16",
    "log10_SD_minus_19",
    "log10_LDD_minus_17",
    "inverse_L_um",
    "L_over_Tox_div_100",
    "x_device_fraction",
    "x_channel_coordinate",
    "y_device_fraction",
    "y_um",
    "region_bulk",
    "region_oxide",
    "region_gate",
    "signed_log_local_net_doping",
)
# These data-driven resolution floors sit inside the large gaps between solver
# round-off values and the resolved field distributions. Values are not clipped;
# the floors only prevent a nonlinear transform from magnifying numerical noise.
RESOLUTION_FLOORS = {
    "Electrons": 1.0,
    "Holes": 1.0,
    "USRH": 1.0,
    "ElectricField_x": 1.0,
    "ElectricField_y": 1.0,
    "ElectronCurrent_x": 1e-9,
    "ElectronCurrent_y": 1e-9,
    "HoleCurrent_x": 1e-20,
    "HoleCurrent_y": 1e-20,
}
RECIPES = (
    {
        "name": "raw_standard",
        "nonlinear_family": "raw",
        "scaler_mode": "standard",
        "scale_quantile": 10.0,
    },
    {
        "name": "asinh_q10_standard",
        "nonlinear_family": "asinh",
        "scaler_mode": "standard",
        "scale_quantile": 10.0,
    },
    {
        "name": "asinh_q10_floor_standard",
        "nonlinear_family": "asinh",
        "scaler_mode": "standard",
        "scale_quantile": 10.0,
        "minimum_scales": RESOLUTION_FLOORS,
    },
    {
        "name": "asinh_q20_standard",
        "nonlinear_family": "asinh",
        "scaler_mode": "standard",
        "scale_quantile": 20.0,
    },
    {
        "name": "signed_log_q10_standard",
        "nonlinear_family": "signed_log1p",
        "scaler_mode": "standard",
        "scale_quantile": 10.0,
    },
    {
        "name": "asinh_q50_standard",
        "nonlinear_family": "asinh",
        "scaler_mode": "standard",
        "scale_quantile": 50.0,
    },
    {
        "name": "asinh_q10_robust",
        "nonlinear_family": "asinh",
        "scaler_mode": "robust",
        "scale_quantile": 10.0,
    },
)


@dataclass(frozen=True)
class SampleSet:
    features: np.ndarray
    targets: np.ndarray
    case_indices: np.ndarray


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _parse_args() -> argparse.Namespace:
    root = _repo_root()
    parser = argparse.ArgumentParser(description="Screen field-map target preprocessing")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=root / "ai/model_artifacts/field_map_model/dataset/fieldmap_dataset.h5",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "ai/model_artifacts/field_map_model/preprocessing_screening",
    )
    parser.add_argument("--train-per-region", type=int, default=24)
    parser.add_argument("--validation-per-region", type=int, default=32)
    parser.add_argument("--trees", type=int, default=48)
    parser.add_argument("--max-depth", type=int, default=18)
    parser.add_argument("--min-samples-leaf", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def _sample_indices(
    region_ids: np.ndarray,
    per_region: int,
    rng: np.random.Generator,
) -> np.ndarray:
    selected: list[np.ndarray] = []
    for region_id in (0, 1, 2):
        candidates = np.flatnonzero(region_ids == region_id)
        if not len(candidates):
            continue
        count = min(per_region, len(candidates))
        selected.append(rng.choice(candidates, size=count, replace=False))
    if not selected:
        raise ValueError("Mesh contains no recognized region IDs")
    # h5py requires monotonically increasing indices for dataset fancy indexing.
    return np.sort(np.concatenate(selected))


def _coordinate_features(
    device_features: np.ndarray,
    coordinates_nm: np.ndarray,
    region_ids: np.ndarray,
    local_net_doping: np.ndarray,
    mesh_node_xy_nm: np.ndarray,
) -> np.ndarray:
    length_nm, tox_nm, log_bulk, log_sd, log_ldd = np.asarray(
        device_features, dtype=np.float64
    )
    x_min, y_min = np.min(mesh_node_xy_nm, axis=0)
    x_max, y_max = np.max(mesh_node_xy_nm, axis=0)
    width = max(float(x_max - x_min), 1.0)
    height = max(float(y_max - y_min), 1.0)
    side_extension = max((width - length_nm) / 2.0, 0.0)
    x = coordinates_nm[:, 0].astype(np.float64)
    y = coordinates_nm[:, 1].astype(np.float64)
    region_one_hot = np.eye(3, dtype=np.float64)[region_ids.astype(np.int64)]
    local_doping = np.sign(local_net_doping) * np.log1p(
        np.abs(local_net_doping) / 1e15
    )
    global_columns = np.column_stack(
        (
            np.full(len(x), length_nm / 1000.0),
            np.full(len(x), tox_nm / 50.0),
            np.full(len(x), log_bulk - 16.0),
            np.full(len(x), log_sd - 19.0),
            np.full(len(x), log_ldd - 17.0),
            np.full(len(x), 1000.0 / max(length_nm, 1.0)),
            np.full(len(x), (length_nm / max(tox_nm, 1.0)) / 100.0),
        )
    )
    spatial_columns = np.column_stack(
        (
            (x - x_min) / width,
            (x - (x_min + side_extension)) / max(length_nm, 1.0),
            (y - y_min) / height,
            y / 1000.0,
        )
    )
    return np.column_stack(
        (global_columns, spatial_columns, region_one_hot, local_doping)
    ).astype(np.float32)


def _collect_samples(
    archive: h5py.File,
    split_index: int,
    domain: str,
    per_region: int,
    seed: int,
) -> SampleSet:
    feature_batches: list[np.ndarray] = []
    target_batches: list[np.ndarray] = []
    case_batches: list[np.ndarray] = []
    case_keys = archive["case_keys"].asstr()[:]
    splits = archive["case_split"][:]
    for case_index in np.flatnonzero(splits == split_index):
        case_key = str(case_keys[case_index])
        case = archive[f"cases/{case_key}"]
        mesh = archive[f"meshes/{case.attrs['structure_id']}"]
        rng = np.random.default_rng(seed + int(case_index) * 17 + (0 if domain == "node" else 1))
        if domain == "node":
            regions = mesh["node_region"][:]
            indices = _sample_indices(regions, per_region, rng)
            coordinates = mesh["node_xy_nm"][indices]
            node_fields = case["node_fields"][:]
            local_doping = node_fields[indices, 0]
            targets = node_fields[indices, 1:]
        elif domain == "element":
            regions = mesh["element_region"][:]
            indices = _sample_indices(regions, per_region, rng)
            coordinates = mesh["element_centroid_xy_nm"][indices]
            triangles = mesh["triangles"][indices]
            local_doping = case["node_fields"][:, 0][triangles].mean(axis=1)
            targets = case["element_fields"][indices]
        else:
            raise ValueError(f"Unknown domain: {domain}")
        features = _coordinate_features(
            case["device_features"][:],
            coordinates,
            regions[indices],
            local_doping,
            mesh["node_xy_nm"][:],
        )
        feature_batches.append(features)
        target_batches.append(np.asarray(targets, dtype=np.float32))
        case_batches.append(np.full(len(indices), case_index, dtype=np.int32))
    return SampleSet(
        features=np.concatenate(feature_batches),
        targets=np.concatenate(target_batches),
        case_indices=np.concatenate(case_batches),
    )


def _evaluation_transformers(
    targets: np.ndarray,
    field_names: tuple[str, ...],
) -> list[FieldTransformer]:
    transformers: list[FieldTransformer] = []
    for column, name in enumerate(field_names):
        values = targets[:, column]
        if name == "Potential":
            mode, scale = "identity", 1.0
        elif name in {"Electrons", "Holes"}:
            mode = "log1p"
            scale = max(
                characteristic_scale(values, 10.0),
                RESOLUTION_FLOORS.get(name, 0.0),
            )
        else:
            mode = "asinh"
            scale = characteristic_scale(values, 10.0)
        transformers.append(FieldTransformer(mode, scale, "standard").fit(values))
    return transformers


def _metrics(
    truth: np.ndarray,
    prediction: np.ndarray,
    field_names: tuple[str, ...],
    evaluators: list[FieldTransformer],
) -> dict[str, object]:
    fields: dict[str, object] = {}
    normalized_scores: list[float] = []
    for column, name in enumerate(field_names):
        target = truth[:, column].astype(np.float64)
        predicted = prediction[:, column].astype(np.float64)
        difference = predicted - target
        target_eval = evaluators[column].transform(target).astype(np.float64)
        prediction_eval = evaluators[column].transform(predicted).astype(np.float64)
        eval_difference = prediction_eval - target_eval
        score = float(np.sqrt(np.mean(np.square(eval_difference))))
        normalized_scores.append(score)
        significant = np.abs(target) >= evaluators[column].nonlinear_scale
        sign_accuracy = (
            float(np.mean(np.sign(target[significant]) == np.sign(predicted[significant])))
            if np.any(significant)
            else math.nan
        )
        fields[name] = {
            "raw_mae": float(np.mean(np.abs(difference))),
            "raw_rmse": float(np.sqrt(np.mean(np.square(difference)))),
            "evaluation_space_mae": float(np.mean(np.abs(eval_difference))),
            "evaluation_space_rmse": score,
            "sign_accuracy_significant": sign_accuracy,
            "evaluation_mode": evaluators[column].mode,
            "evaluation_scale": evaluators[column].nonlinear_scale,
        }
    return {
        "aggregate_mean_evaluation_rmse": float(np.mean(normalized_scores)),
        "fields": fields,
    }


def _screen_domain(
    train: SampleSet,
    validation: SampleSet,
    field_names: tuple[str, ...],
    args: argparse.Namespace,
) -> dict[str, object]:
    evaluators = _evaluation_transformers(train.targets, field_names)
    results: dict[str, object] = {}
    for recipe_index, recipe in enumerate(RECIPES):
        started = time.perf_counter()
        transformers = fit_transformers(
            train.targets,
            field_names,
            str(recipe["nonlinear_family"]),
            str(recipe["scaler_mode"]),
            float(recipe["scale_quantile"]),
            recipe.get("minimum_scales"),
        )
        transformed_train = transform_matrix(train.targets, transformers)
        model = ExtraTreesRegressor(
            n_estimators=args.trees,
            max_depth=args.max_depth,
            min_samples_leaf=args.min_samples_leaf,
            max_features=1.0,
            n_jobs=-1,
            random_state=args.seed + recipe_index,
        )
        model.fit(train.features, transformed_train)
        transformed_prediction = model.predict(validation.features)
        prediction = inverse_transform_matrix(transformed_prediction, transformers)
        for column, field_name in enumerate(field_names):
            if field_name in {"Electrons", "Holes"}:
                prediction[:, column] = np.maximum(prediction[:, column], 0.0)
        metrics = _metrics(validation.targets, prediction, field_names, evaluators)
        results[str(recipe["name"])] = {
            "recipe": recipe,
            "elapsed_seconds": time.perf_counter() - started,
            "metrics": metrics,
            "transformers": {
                name: transformers[index].state_dict()
                for index, name in enumerate(field_names)
            },
        }
        print(
            f"{recipe['name']}: score="
            f"{metrics['aggregate_mean_evaluation_rmse']:.6f}",
            flush=True,
        )
    selected_name = min(
        results,
        key=lambda name: results[name]["metrics"]["aggregate_mean_evaluation_rmse"],
    )
    return {
        "field_names": list(field_names),
        "train_samples": len(train.targets),
        "validation_samples": len(validation.targets),
        "selected_recipe": selected_name,
        "results": results,
    }


def _markdown(report: dict[str, object]) -> str:
    lines = [
        "# Field-map preprocessing screening",
        "",
        "The curve-model device split is reused exactly. All transform and scaler ",
        "parameters are fitted on train samples only; test cases are not loaded.",
        "",
    ]
    for domain in ("node", "element"):
        item = report["domains"][domain]
        lines.extend(
            [
                f"## {domain.title()} targets",
                "",
                f"Selected: `{item['selected_recipe']}`",
                "",
                "| Recipe | Validation score | Time (s) |",
                "|---|---:|---:|",
            ]
        )
        ordered = sorted(
            item["results"].items(),
            key=lambda pair: pair[1]["metrics"]["aggregate_mean_evaluation_rmse"],
        )
        for name, result in ordered:
            lines.append(
                f"| {name} | "
                f"{result['metrics']['aggregate_mean_evaluation_rmse']:.6f} | "
                f"{result['elapsed_seconds']:.1f} |"
            )
        lines.extend(["", "Per-field validation RMSE in the fixed evaluation space:", ""])
        lines.append("| Recipe | " + " | ".join(item["field_names"]) + " |")
        lines.append("|---|" + "---:|" * len(item["field_names"]))
        for name, result in ordered:
            values = [
                result["metrics"]["fields"][field]["evaluation_space_rmse"]
                for field in item["field_names"]
            ]
            lines.append(
                "| " + name + " | " + " | ".join(f"{value:.6f}" for value in values) + " |"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = _parse_args()
    dataset_path = args.dataset.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    with h5py.File(dataset_path, "r") as archive:
        split_counts = {
            name: int(np.count_nonzero(archive["case_split"][:] == index))
            for index, name in enumerate(("train", "validation", "test"))
        }
        print("Collecting node samples", flush=True)
        node_train = _collect_samples(
            archive, 0, "node", args.train_per_region, args.seed
        )
        node_validation = _collect_samples(
            archive, 1, "node", args.validation_per_region, args.seed
        )
        print("Collecting element samples", flush=True)
        element_train = _collect_samples(
            archive, 0, "element", args.train_per_region, args.seed
        )
        element_validation = _collect_samples(
            archive, 1, "element", args.validation_per_region, args.seed
        )
    report = {
        "schema_version": 1,
        "dataset": str(dataset_path),
        "split_counts": split_counts,
        "test_cases_loaded": 0,
        "input_names": list(INPUT_NAMES),
        "local_net_doping_role": "input only; not a learned target",
        "evaluation_resolution_floors": RESOLUTION_FLOORS,
        "sampling": {
            "method": "equal random samples per device and mesh region",
            "train_per_region_per_case": args.train_per_region,
            "validation_per_region_per_case": args.validation_per_region,
            "seed": args.seed,
        },
        "screening_model": {
            "type": "ExtraTreesRegressor multi-output",
            "n_estimators": args.trees,
            "max_depth": args.max_depth,
            "min_samples_leaf": args.min_samples_leaf,
        },
        "domains": {
            "node": _screen_domain(
                node_train, node_validation, NODE_TARGET_NAMES, args
            ),
            "element": _screen_domain(
                element_train, element_validation, ELEMENT_FIELD_NAMES, args
            ),
        },
    }
    selected = {
        "schema_version": 1,
        "selection_source": "preprocessing_screening_report.json",
        "input_names": list(INPUT_NAMES),
        "local_net_doping_role": report["local_net_doping_role"],
        "node": {
            "recipe": report["domains"]["node"]["selected_recipe"],
            "transformers": report["domains"]["node"]["results"][
                report["domains"]["node"]["selected_recipe"]
            ]["transformers"],
        },
        "element": {
            "recipe": report["domains"]["element"]["selected_recipe"],
            "transformers": report["domains"]["element"]["results"][
                report["domains"]["element"]["selected_recipe"]
            ]["transformers"],
        },
    }
    (output_dir / "preprocessing_screening_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (output_dir / "single_seed_selection.json").write_text(
        json.dumps(selected, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (output_dir / "preprocessing_screening_report.md").write_text(
        _markdown(report), encoding="utf-8"
    )
    print(_markdown(report), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
