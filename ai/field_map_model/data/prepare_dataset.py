from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import h5py
import numpy as np

from ai.field_map_model.data.tecplot import (
    ELEMENT_FIELD_NAMES,
    NODE_FIELD_NAMES,
    ParsedFieldCase,
    parse_tecplot_field_case,
)


CASE_PATTERN = re.compile(
    r"^(?P<structure>L(?P<L>[-+0-9.eE]+)T(?P<T>[-+0-9.eE]+))"
    r"(?P<doping>B(?P<B>[-+0-9.eE]+)SD(?P<SD>[-+0-9.eE]+)"
    r"LDD(?P<LDD>[-+0-9.eE]+))_IdVd_Vg3p0_Vd3p0\.dat$"
)
REGION_IDS = {"bulk": 0, "oxide": 1, "gate": 2}
REGION_NAMES = ("bulk", "oxide", "gate")
SPLIT_NAMES = ("train", "validation", "test")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _parse_args() -> argparse.Namespace:
    root = _repo_root()
    dataset_root = Path(os.environ.get("IDM_DATASET_DIR", root / "tcad/data_extraction/dataset"))
    parser = argparse.ArgumentParser(description="Build the fixed-bias field-map HDF5 dataset")
    parser.add_argument("--field-dir", type=Path, default=dataset_root / "final_fields")
    parser.add_argument(
        "--curve-dataset",
        type=Path,
        default=root / "ai/model_artifacts/curve_model/dataset/curves.npz",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "ai/model_artifacts/field_map_model/dataset",
    )
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--limit", type=int, default=0, help="Optional parser smoke-test limit")
    return parser.parse_args()


@dataclass(frozen=True)
class CaseRecord:
    path: Path
    case_id: str
    case_key: str
    structure_id: str
    doping_id: str
    features: np.ndarray
    physical_doping: tuple[float, float, float]
    split_index: int


@dataclass
class RunningStats:
    sample_limit_per_update: int = 64
    count: int = 0
    finite_count: int = 0
    nonfinite_count: int = 0
    zero_count: int = 0
    positive_count: int = 0
    negative_count: int = 0
    minimum: float = math.inf
    maximum: float = -math.inf
    total: float = 0.0
    total_square: float = 0.0
    samples: list[np.ndarray] = field(default_factory=list)

    def update(self, values: np.ndarray, rng: np.random.Generator) -> None:
        array = np.asarray(values, dtype=np.float64).ravel()
        self.count += len(array)
        finite = array[np.isfinite(array)]
        self.finite_count += len(finite)
        self.nonfinite_count += len(array) - len(finite)
        if not len(finite):
            return
        self.zero_count += int(np.count_nonzero(finite == 0.0))
        self.positive_count += int(np.count_nonzero(finite > 0.0))
        self.negative_count += int(np.count_nonzero(finite < 0.0))
        self.minimum = min(self.minimum, float(finite.min()))
        self.maximum = max(self.maximum, float(finite.max()))
        self.total += float(np.sum(finite, dtype=np.float64))
        self.total_square += float(np.sum(np.square(finite), dtype=np.float64))
        take = min(self.sample_limit_per_update, len(finite))
        indices = rng.choice(len(finite), size=take, replace=False)
        self.samples.append(finite[indices].astype(np.float32))

    def report(self) -> dict[str, object]:
        if not self.finite_count:
            return {
                "count": self.count,
                "finite_count": 0,
                "nonfinite_count": self.nonfinite_count,
            }
        mean = self.total / self.finite_count
        variance = max(self.total_square / self.finite_count - mean * mean, 0.0)
        sample = np.concatenate(self.samples) if self.samples else np.empty(0)
        percentiles = (0.1, 1.0, 5.0, 50.0, 95.0, 99.0, 99.9)
        return {
            "count": self.count,
            "finite_count": self.finite_count,
            "nonfinite_count": self.nonfinite_count,
            "zero_count": self.zero_count,
            "positive_count": self.positive_count,
            "negative_count": self.negative_count,
            "min": self.minimum,
            "max": self.maximum,
            "mean": mean,
            "std": math.sqrt(variance),
            "percentile_sample_count": int(len(sample)),
            "percentiles": {
                str(value): float(np.percentile(sample, value)) for value in percentiles
            },
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_curve_split(path: Path) -> tuple[dict[str, tuple[int, np.ndarray]], dict[str, object]]:
    with np.load(path, allow_pickle=False) as archive:
        case_ids = [str(value) for value in archive["device_ids"]]
        features = archive["device_features"].astype(np.float32)
        split = archive["device_split"].astype(np.int8)
    mapping = {
        case_id: (int(split[index]), features[index]) for index, case_id in enumerate(case_ids)
    }
    return mapping, {
        "path": str(path.resolve()),
        "sha256": _sha256(path),
        "case_count": len(mapping),
        "split_counts": {
            name: int(np.count_nonzero(split == index))
            for index, name in enumerate(SPLIT_NAMES)
        },
    }


def _records(field_dir: Path, split_mapping: dict[str, tuple[int, np.ndarray]]) -> tuple[list[CaseRecord], list[dict[str, str]]]:
    records: list[CaseRecord] = []
    issues: list[dict[str, str]] = []
    seen: set[str] = set()
    for path in sorted(field_dir.glob("*.dat")):
        match = CASE_PATTERN.fullmatch(path.name)
        if match is None:
            issues.append({"path": str(path), "reason": "filename does not match fixed-bias case pattern"})
            continue
        structure_id = match.group("structure")
        doping_id = match.group("doping")
        case_id = f"{structure_id}|{doping_id}"
        if case_id in seen:
            issues.append({"path": str(path), "reason": f"duplicate case {case_id}"})
            continue
        seen.add(case_id)
        if case_id not in split_mapping:
            issues.append({"path": str(path), "reason": f"case missing from curve split: {case_id}"})
            continue
        split_index, curve_features = split_mapping[case_id]
        parsed_features = np.asarray(
            [
                float(match.group("L")),
                float(match.group("T")),
                math.log10(float(match.group("B"))),
                math.log10(float(match.group("SD"))),
                math.log10(float(match.group("LDD"))),
            ],
            dtype=np.float32,
        )
        if not np.allclose(parsed_features, curve_features, rtol=0.0, atol=1e-5):
            issues.append({"path": str(path), "reason": f"feature mismatch for {case_id}"})
            continue
        records.append(
            CaseRecord(
                path=path,
                case_id=case_id,
                case_key=case_id.replace("|", "__"),
                structure_id=structure_id,
                doping_id=doping_id,
                features=parsed_features,
                physical_doping=(
                    float(match.group("B")),
                    float(match.group("SD")),
                    float(match.group("LDD")),
                ),
                split_index=split_index,
            )
        )
    missing_dat = sorted(set(split_mapping).difference(seen))
    issues.extend({"path": "", "reason": f"curve split case has no DAT: {case_id}"} for case_id in missing_dat)
    return records, issues


def _combine_zones(parsed: ParsedFieldCase) -> dict[str, np.ndarray | str]:
    by_name = {zone.name.lower(): zone for zone in parsed.zones}
    missing = set(REGION_NAMES).difference(by_name)
    extra = set(by_name).difference(REGION_NAMES)
    if missing or extra:
        raise ValueError(f"Unexpected zones: missing={sorted(missing)}, extra={sorted(extra)}")

    node_xy: list[np.ndarray] = []
    node_regions: list[np.ndarray] = []
    triangles: list[np.ndarray] = []
    element_centroids: list[np.ndarray] = []
    element_regions: list[np.ndarray] = []
    node_fields: list[np.ndarray] = []
    element_fields: list[np.ndarray] = []
    node_offset = 0
    for region_name in REGION_NAMES:
        zone = by_name[region_name]
        count = len(zone.coordinates_cm)
        region_id = REGION_IDS[region_name]
        node_xy.append(zone.coordinates_cm * np.float32(1e7))
        node_regions.append(np.full(count, region_id, dtype=np.uint8))
        triangles.append(zone.triangles + node_offset)
        element_centroids.append(zone.coordinates_cm[zone.triangles].mean(axis=1) * np.float32(1e7))
        element_regions.append(np.full(len(zone.triangles), region_id, dtype=np.uint8))
        node_fields.append(zone.node_fields)
        element_fields.append(zone.element_fields)
        node_offset += count
    combined = {
        "node_xy_nm": np.concatenate(node_xy).astype(np.float32),
        "node_region": np.concatenate(node_regions),
        "triangles": np.concatenate(triangles).astype(np.int32),
        "element_centroid_xy_nm": np.concatenate(element_centroids).astype(np.float32),
        "element_region": np.concatenate(element_regions),
        "node_fields": np.concatenate(node_fields).astype(np.float32),
        "element_fields": np.concatenate(element_fields).astype(np.float32),
    }
    for name in (
        "node_xy_nm",
        "element_centroid_xy_nm",
        "node_fields",
        "element_fields",
    ):
        values = np.asarray(combined[name])
        nonfinite_count = int(values.size - np.count_nonzero(np.isfinite(values)))
        if nonfinite_count:
            raise ValueError(f"{name} contains {nonfinite_count} NaN/Inf values")
    digest = hashlib.sha256()
    for name in ("node_xy_nm", "node_region", "triangles", "element_centroid_xy_nm", "element_region"):
        digest.update(np.asarray(combined[name]).tobytes())
    combined["mesh_sha256"] = digest.hexdigest()
    return combined


def _write_dataset_array(group: h5py.Group, name: str, values: np.ndarray) -> None:
    group.create_dataset(name, data=values, compression="lzf", shuffle=True)


def _update_distribution(
    stats: dict[str, RunningStats],
    combined: dict[str, np.ndarray | str],
    rng: np.random.Generator,
) -> None:
    node_values = np.asarray(combined["node_fields"])
    element_values = np.asarray(combined["element_fields"])
    node_region = np.asarray(combined["node_region"])
    element_region = np.asarray(combined["element_region"])
    for column, name in enumerate(NODE_FIELD_NAMES):
        stats[name].update(node_values[:, column], rng)
        for region_name, region_id in REGION_IDS.items():
            stats[f"{name}.{region_name}"].update(node_values[node_region == region_id, column], rng)
    for column, name in enumerate(ELEMENT_FIELD_NAMES):
        stats[name].update(element_values[:, column], rng)
        for region_name, region_id in REGION_IDS.items():
            stats[f"{name}.{region_name}"].update(
                element_values[element_region == region_id, column], rng
            )


def _summarize_counts(values: Iterable[int]) -> dict[str, float | int]:
    array = np.asarray(list(values), dtype=np.float64)
    return {
        "count": int(len(array)),
        "min": int(array.min()),
        "max": int(array.max()),
        "mean": float(array.mean()),
        "p50": float(np.percentile(array, 50)),
        "p95": float(np.percentile(array, 95)),
    }


def _write_manifests(
    output_dir: Path,
    records: list[CaseRecord],
    source: dict[str, object],
    suffix: str = "",
) -> None:
    with (output_dir / f"raw_manifest{suffix}.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "case_id", "structure_id", "doping_id", "split", "L_nm", "Tox_nm",
                "bulk_doping", "sd_doping", "ldd_doping", "field_file", "field_file_bytes",
            ),
        )
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "case_id": record.case_id,
                    "structure_id": record.structure_id,
                    "doping_id": record.doping_id,
                    "split": SPLIT_NAMES[record.split_index],
                    "L_nm": float(record.features[0]),
                    "Tox_nm": float(record.features[1]),
                    "bulk_doping": record.physical_doping[0],
                    "sd_doping": record.physical_doping[1],
                    "ldd_doping": record.physical_doping[2],
                    "field_file": str(record.path.resolve()),
                    "field_file_bytes": record.path.stat().st_size,
                }
            )
    split_manifest = {
        "schema_version": 1,
        "source_curve_dataset": source,
        "split_names": list(SPLIT_NAMES),
        "method": "exact reuse of curve-model device_split",
        "cases": {record.case_id: SPLIT_NAMES[record.split_index] for record in records},
    }
    (output_dir / f"split_manifest{suffix}.json").write_text(
        json.dumps(split_manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _ldd_sensitivity_checks(h5_path: Path, records: list[CaseRecord], limit: int = 32) -> dict[str, object]:
    groups: dict[tuple[str, float, float], list[CaseRecord]] = defaultdict(list)
    for record in records:
        bulk, sd, _ldd = record.physical_doping
        groups[(record.structure_id, bulk, sd)].append(record)
    candidates = [items for items in groups.values() if len({item.physical_doping[2] for item in items}) >= 2]
    if len(candidates) > limit:
        indices = np.linspace(0, len(candidates) - 1, limit, dtype=int)
        candidates = [candidates[index] for index in indices]
    checks: list[dict[str, object]] = []
    with h5py.File(h5_path, "r") as archive:
        for items in candidates:
            ordered = sorted(items, key=lambda item: item.physical_doping[2])
            low, high = ordered[0], ordered[-1]
            low_values = archive[f"cases/{low.case_key}/node_fields"][:, 0]
            high_values = archive[f"cases/{high.case_key}/node_fields"][:, 0]
            max_abs_delta = float(np.max(np.abs(high_values - low_values)))
            expected_delta = high.physical_doping[2] - low.physical_doping[2]
            checks.append(
                {
                    "structure_id": low.structure_id,
                    "bulk_doping": low.physical_doping[0],
                    "sd_doping": low.physical_doping[1],
                    "low_ldd": low.physical_doping[2],
                    "high_ldd": high.physical_doping[2],
                    "max_abs_net_doping_delta": max_abs_delta,
                    "passed": bool(max_abs_delta >= 0.5 * expected_delta),
                }
            )
    return {
        "groups_checked": len(checks),
        "passed": sum(bool(item["passed"]) for item in checks),
        "failed": sum(not bool(item["passed"]) for item in checks),
        "checks": checks,
    }


def build_dataset(args: argparse.Namespace) -> dict[str, object]:
    field_dir = args.field_dir.resolve()
    curve_dataset = args.curve_dataset.resolve()
    output_dir = args.output_dir.resolve()
    if not field_dir.is_dir():
        raise FileNotFoundError(f"Field directory not found: {field_dir}")
    if not curve_dataset.exists():
        raise FileNotFoundError(f"Curve split dataset not found: {curve_dataset}")
    output_dir.mkdir(parents=True, exist_ok=True)

    split_mapping, split_source = _load_curve_split(curve_dataset)
    records, manifest_issues = _records(field_dir, split_mapping)
    if args.limit:
        records = records[: args.limit]
    artifact_suffix = "_smoke" if args.limit else ""
    _write_manifests(output_dir, records, split_source, artifact_suffix)

    output_path = output_dir / ("fieldmap_dataset_smoke.h5" if args.limit else "fieldmap_dataset.h5")
    partial_path = output_path.with_suffix(output_path.suffix + ".partial")
    partial_path.unlink(missing_ok=True)
    errors: list[dict[str, str]] = list(manifest_issues)
    mesh_hashes: dict[str, str] = {}
    node_counts: list[int] = []
    element_counts: list[int] = []
    zone_counter: Counter[str] = Counter()
    stats = defaultdict(RunningStats)
    rng = np.random.default_rng(42)
    started = time.perf_counter()

    string_dtype = h5py.string_dtype(encoding="utf-8")
    successful_records: list[CaseRecord] = []
    with h5py.File(partial_path, "w") as archive:
        archive.attrs["schema_version"] = 1
        archive.attrs["fixed_gate_v"] = 3.0
        archive.attrs["fixed_drain_v"] = 3.0
        archive.attrs["node_field_names"] = json.dumps(NODE_FIELD_NAMES)
        archive.attrs["element_field_names"] = json.dumps(ELEMENT_FIELD_NAMES)
        archive.attrs["region_ids"] = json.dumps(REGION_IDS)
        meshes_group = archive.create_group("meshes")
        cases_group = archive.create_group("cases")

        for position, record in enumerate(records, start=1):
            try:
                parsed = parse_tecplot_field_case(record.path)
                combined = _combine_zones(parsed)
                mesh_hash = str(combined["mesh_sha256"])
                previous_hash = mesh_hashes.get(record.structure_id)
                if previous_hash is not None and previous_hash != mesh_hash:
                    raise ValueError(
                        f"Mesh differs within structure {record.structure_id}: "
                        f"{previous_hash} != {mesh_hash}"
                    )
                if previous_hash is None:
                    mesh_hashes[record.structure_id] = mesh_hash
                    mesh_group = meshes_group.create_group(record.structure_id)
                    mesh_group.attrs["mesh_sha256"] = mesh_hash
                    for name in (
                        "node_xy_nm", "node_region", "triangles",
                        "element_centroid_xy_nm", "element_region",
                    ):
                        _write_dataset_array(mesh_group, name, np.asarray(combined[name]))

                case_group = cases_group.create_group(record.case_key)
                case_group.attrs["case_id"] = record.case_id
                case_group.attrs["structure_id"] = record.structure_id
                case_group.attrs["doping_id"] = record.doping_id
                case_group.attrs["split_index"] = record.split_index
                case_group.attrs["split"] = SPLIT_NAMES[record.split_index]
                case_group.attrs["source_file"] = str(record.path.resolve())
                case_group.create_dataset("device_features", data=record.features)
                case_group.create_dataset(
                    "physical_doping", data=np.asarray(record.physical_doping, dtype=np.float64)
                )
                _write_dataset_array(case_group, "node_fields", np.asarray(combined["node_fields"]))
                _write_dataset_array(
                    case_group, "element_fields", np.asarray(combined["element_fields"])
                )

                node_count = len(np.asarray(combined["node_fields"]))
                element_count = len(np.asarray(combined["element_fields"]))
                node_counts.append(node_count)
                element_counts.append(element_count)
                zone_counter.update(zone.name.lower() for zone in parsed.zones)
                if record.split_index == 0:
                    _update_distribution(stats, combined, rng)
                successful_records.append(record)
            except Exception as exc:
                errors.append({"path": str(record.path), "case_id": record.case_id, "reason": str(exc)})

            if position % args.progress_every == 0 or position == len(records):
                elapsed = time.perf_counter() - started
                rate = position / elapsed if elapsed else 0.0
                remaining = (len(records) - position) / rate if rate else math.inf
                print(
                    f"[{position}/{len(records)}] valid={len(successful_records)} "
                    f"errors={len(errors)} elapsed={elapsed:.1f}s eta={remaining:.1f}s",
                    flush=True,
                )

        archive.create_dataset(
            "case_ids",
            data=np.asarray([record.case_id for record in successful_records], dtype=object),
            dtype=string_dtype,
        )
        archive.create_dataset(
            "case_keys",
            data=np.asarray([record.case_key for record in successful_records], dtype=object),
            dtype=string_dtype,
        )
        archive.create_dataset(
            "case_split",
            data=np.asarray([record.split_index for record in successful_records], dtype=np.int8),
        )
        archive.create_dataset(
            "case_features",
            data=np.stack([record.features for record in successful_records]),
        )

    if errors:
        final_path = partial_path
    else:
        partial_path.replace(output_path)
        final_path = output_path

    elapsed = time.perf_counter() - started
    integrity = {
        "schema_version": 1,
        "status": "complete" if not errors else "completed_with_errors",
        "source_field_dir": str(field_dir),
        "source_dat_files": len(list(field_dir.glob("*.dat"))),
        "source_total_bytes": sum(path.stat().st_size for path in field_dir.glob("*.dat")),
        "curve_split": split_source,
        "manifest_records": len(records),
        "valid_cases": len(successful_records),
        "errors": errors,
        "structures": len(mesh_hashes),
        "zone_occurrences": dict(zone_counter),
        "node_counts_per_case": _summarize_counts(node_counts) if node_counts else {},
        "element_counts_per_case": _summarize_counts(element_counts) if element_counts else {},
        "elapsed_seconds": elapsed,
        "hdf5_path": str(final_path),
        "hdf5_bytes": final_path.stat().st_size,
    }
    if not errors and not args.limit:
        integrity["ldd_sensitivity"] = _ldd_sensitivity_checks(final_path, successful_records)
    (output_dir / f"raw_integrity_report{artifact_suffix}.json").write_text(
        json.dumps(integrity, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    distribution = {
        "schema_version": 1,
        "source": str(final_path),
        "split": "train only",
        "train_cases": sum(record.split_index == 0 for record in successful_records),
        "sampling": {
            "exact_statistics": ["count", "finite/nonfinite", "sign counts", "min/max", "mean/std"],
            "percentiles": "up to 64 deterministic random values per case/field/region",
            "seed": 42,
        },
        "node_fields": {
            name: {
                "all": stats[name].report(),
                "regions": {
                    region: stats[f"{name}.{region}"].report() for region in REGION_NAMES
                },
            }
            for name in NODE_FIELD_NAMES
        },
        "element_fields": {
            name: {
                "all": stats[name].report(),
                "regions": {
                    region: stats[f"{name}.{region}"].report() for region in REGION_NAMES
                },
            }
            for name in ELEMENT_FIELD_NAMES
        },
    }
    (output_dir / f"distribution_report{artifact_suffix}.json").write_text(
        json.dumps(distribution, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return integrity


def main() -> int:
    args = _parse_args()
    report = build_dataset(args)
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
