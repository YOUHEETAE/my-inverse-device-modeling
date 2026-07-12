from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


CURVE_TYPES = {
    "IdVd": {
        "suffix": "_IdVd.csv",
        "x_column": "drain_v",
        "required": (
            "structure_id",
            "doping_run_id",
            "curve_tag",
            "gate_v",
            "drain_v",
            "drain_current",
        ),
    },
    "IdVg": {
        "suffix": "_IdVg.csv",
        "x_column": "gate_v",
        "required": (
            "structure_id",
            "doping_run_id",
            "curve_tag",
            "gate_v",
            "drain_v",
            "drain_current",
        ),
    },
}

PARAMETER_ID_COLUMNS = ("structure_id", "doping_run_id")
PARAMETER_META_COLUMNS = (*PARAMETER_ID_COLUMNS, "extraction_status", "error")
STEM_PATTERN = re.compile(r"(?P<structure>.+?)(?P<doping>B.+)$")


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    location: str
    message: str


def _default_dataset(script_file: Path) -> Path:
    return script_file.resolve().parents[1] / "dataset"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate extracted I-V curves and device parameter CSV files."
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=_default_dataset(Path(__file__)),
        help="Directory containing *_IdVd.csv, *_IdVg.csv, and device_parameters.csv",
    )
    parser.add_argument(
        "--parameters-csv",
        type=Path,
        default=None,
        help="Parameter CSV (default: <dataset-dir>/device_parameters.csv)",
    )
    parser.add_argument("--report", type=Path, help="Optional JSON report path")
    parser.add_argument(
        "--max-issues",
        type=int,
        default=100,
        help="Maximum issues retained in the report (default: 100)",
    )
    return parser.parse_args()


def _add_issue(
    issues: list[Issue], limit: int, severity: str, code: str, location: str, message: str
) -> None:
    if len(issues) < limit:
        issues.append(Issue(severity, code, location, message))


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _finite_number(value: str) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _expected_ids(stem: str) -> tuple[str, str] | None:
    match = STEM_PATTERN.fullmatch(stem)
    if not match:
        return None
    return match.group("structure"), match.group("doping")


def _monotonic_direction(values: list[float]) -> int:
    differences = [right - left for left, right in zip(values, values[1:])]
    if all(value > 0 for value in differences):
        return 1
    if all(value < 0 for value in differences):
        return -1
    return 0


def _validate_curve_file(
    path: Path,
    kind: str,
    stem: str,
    issues: list[Issue],
    limit: int,
) -> tuple[set[tuple[str, str]], dict[str, tuple[float, ...]], int]:
    config = CURVE_TYPES[kind]
    try:
        fields, rows = _read_csv(path)
    except (OSError, UnicodeError, csv.Error) as exc:
        _add_issue(issues, limit, "error", "unreadable_csv", path.name, str(exc))
        return set(), {}, 0

    missing = sorted(set(config["required"]) - set(fields))
    if missing:
        _add_issue(
            issues, limit, "error", "missing_columns", path.name, ", ".join(missing)
        )
        return set(), {}, len(rows)
    if not rows:
        _add_issue(issues, limit, "error", "empty_file", path.name, "CSV has no rows")
        return set(), {}, 0

    expected = _expected_ids(stem)
    ids: set[tuple[str, str]] = set()
    grouped: dict[str, list[tuple[int, float]]] = defaultdict(list)
    numeric_columns = ("gate_v", "drain_v", "drain_current")
    for line, row in enumerate(rows, start=2):
        current_id = tuple((row.get(name) or "").strip() for name in PARAMETER_ID_COLUMNS)
        ids.add(current_id)  # type: ignore[arg-type]
        tag = (row.get("curve_tag") or "").strip()
        if not tag:
            _add_issue(issues, limit, "error", "empty_curve_tag", f"{path.name}:{line}", "")
        invalid = [name for name in numeric_columns if not _finite_number(row.get(name, ""))]
        if invalid:
            _add_issue(
                issues,
                limit,
                "error",
                "non_finite_numeric",
                f"{path.name}:{line}",
                ", ".join(invalid),
            )
            continue
        grouped[tag].append((line, float(row[config["x_column"]])))

    if len(ids) != 1:
        _add_issue(
            issues, limit, "error", "mixed_device_ids", path.name, f"found {len(ids)} IDs"
        )
    elif expected is not None and next(iter(ids)) != expected:
        _add_issue(
            issues,
            limit,
            "error",
            "filename_id_mismatch",
            path.name,
            f"filename={expected}, rows={next(iter(ids))}",
        )

    grids: dict[str, tuple[float, ...]] = {}
    for tag, points in grouped.items():
        values = [value for _, value in points]
        duplicate_count = len(values) - len(set(values))
        if duplicate_count:
            _add_issue(
                issues,
                limit,
                "error",
                "duplicate_x",
                f"{path.name}:{tag}",
                f"{duplicate_count} duplicate coordinate(s)",
            )
        if len(values) > 1 and _monotonic_direction(values) == 0:
            _add_issue(
                issues,
                limit,
                "warning",
                "non_monotonic_x",
                f"{path.name}:{tag}",
                f"{config['x_column']} is not strictly monotonic",
            )
        grids[tag] = tuple(values)
    return ids, grids, len(rows)


def _validate_parameters(
    path: Path,
    curve_ids: set[tuple[str, str]],
    issues: list[Issue],
    limit: int,
) -> dict[str, object]:
    if not path.exists():
        _add_issue(issues, limit, "error", "missing_parameters_csv", str(path), "")
        return {"rows": 0, "statuses": {}, "numeric_columns": []}
    try:
        fields, rows = _read_csv(path)
    except (OSError, UnicodeError, csv.Error) as exc:
        _add_issue(issues, limit, "error", "unreadable_csv", str(path), str(exc))
        return {"rows": 0, "statuses": {}, "numeric_columns": []}

    missing = sorted(set(PARAMETER_META_COLUMNS) - set(fields))
    if missing:
        _add_issue(
            issues, limit, "error", "missing_parameter_columns", path.name, ", ".join(missing)
        )
    numeric_columns = [name for name in fields if name not in PARAMETER_META_COLUMNS]
    ids: list[tuple[str, str]] = []
    statuses: Counter[str] = Counter()
    for line, row in enumerate(rows, start=2):
        device_id = tuple((row.get(name) or "").strip() for name in PARAMETER_ID_COLUMNS)
        ids.append(device_id)  # type: ignore[arg-type]
        status = (row.get("extraction_status") or "").strip()
        statuses[status] += 1
        if status == "ok":
            invalid = [name for name in numeric_columns if not _finite_number(row.get(name, ""))]
            if invalid:
                _add_issue(
                    issues,
                    limit,
                    "error",
                    "invalid_extracted_parameter",
                    f"{path.name}:{line}",
                    ", ".join(invalid),
                )

    duplicates = [device_id for device_id, count in Counter(ids).items() if count > 1]
    for device_id in duplicates:
        _add_issue(
            issues, limit, "error", "duplicate_parameter_id", path.name, str(device_id)
        )
    parameter_ids = set(ids)
    for device_id in sorted(curve_ids - parameter_ids):
        _add_issue(
            issues, limit, "error", "missing_parameter_row", path.name, str(device_id)
        )
    for device_id in sorted(parameter_ids - curve_ids):
        _add_issue(
            issues, limit, "warning", "parameter_without_curves", path.name, str(device_id)
        )
    return {
        "rows": len(rows),
        "unique_device_ids": len(parameter_ids),
        "statuses": dict(statuses),
        "numeric_columns": numeric_columns,
    }


def _grid_summary(
    grid_counts: dict[tuple[str, str], Counter[tuple[float, ...]]],
    grid_locations: dict[tuple[str, str, tuple[float, ...]], list[str]],
    issues: list[Issue],
    limit: int,
) -> dict[str, object]:
    result: dict[str, object] = {}
    for (kind, tag), counts in sorted(grid_counts.items()):
        canonical, canonical_count = counts.most_common(1)[0]
        variant_count = sum(counts.values()) - canonical_count
        non_canonical_files = sorted(
            path
            for grid in counts
            if grid != canonical
            for path in grid_locations[(kind, tag, grid)]
        )
        key = f"{kind}:{tag}"
        result[key] = {
            "files": sum(counts.values()),
            "canonical_points": len(canonical),
            "grid_variants": len(counts),
            "non_canonical_files": variant_count,
            "non_canonical_file_names": non_canonical_files,
            "x_min": min(canonical) if canonical else None,
            "x_max": max(canonical) if canonical else None,
        }
        if variant_count:
            _add_issue(
                issues,
                limit,
                "error",
                "inconsistent_grid",
                key,
                f"{variant_count} file(s) differ: {', '.join(non_canonical_files)}",
            )
    return result


def validate_dataset(dataset_dir: Path, parameters_csv: Path, max_issues: int) -> dict[str, object]:
    issues: list[Issue] = []
    files_by_stem: dict[str, dict[str, Path]] = defaultdict(dict)
    for kind, config in CURVE_TYPES.items():
        suffix = str(config["suffix"])
        for path in dataset_dir.glob(f"*{suffix}"):
            files_by_stem[path.name.removesuffix(suffix)][kind] = path

    all_ids: set[tuple[str, str]] = set()
    grid_counts: dict[tuple[str, str], Counter[tuple[float, ...]]] = defaultdict(Counter)
    grid_locations: dict[tuple[str, str, tuple[float, ...]], list[str]] = defaultdict(list)
    file_counts: Counter[str] = Counter()
    row_counts: Counter[str] = Counter()
    complete_pairs = 0
    for stem, paths in sorted(files_by_stem.items()):
        missing = sorted(set(CURVE_TYPES) - set(paths))
        if missing:
            _add_issue(
                issues, max_issues, "error", "missing_curve_pair", stem, ", ".join(missing)
            )
        else:
            complete_pairs += 1
        for kind, path in paths.items():
            file_counts[kind] += 1
            ids, grids, row_count = _validate_curve_file(
                path, kind, stem, issues, max_issues
            )
            all_ids.update(ids)
            row_counts[kind] += row_count
            for tag, grid in grids.items():
                grid_counts[(kind, tag)][grid] += 1
                grid_locations[(kind, tag, grid)].append(path.name)

    grid_info = _grid_summary(grid_counts, grid_locations, issues, max_issues)
    parameter_info = _validate_parameters(
        parameters_csv, all_ids, issues, max_issues
    )
    severity_counts = Counter(issue.severity for issue in issues)
    return {
        "dataset_dir": str(dataset_dir.resolve()),
        "curve_files": dict(file_counts),
        "curve_rows": dict(row_counts),
        "curve_stems": len(files_by_stem),
        "complete_pairs": complete_pairs,
        "unique_curve_device_ids": len(all_ids),
        "grids": grid_info,
        "parameters": parameter_info,
        "issue_counts_retained": dict(severity_counts),
        "issues_truncated": len(issues) >= max_issues,
        "issues": [asdict(issue) for issue in issues],
    }


def _print_report(report: dict[str, object]) -> None:
    print(f"Dataset: {report['dataset_dir']}")
    print(
        f"Curve files: {report['curve_files']} | rows: {report['curve_rows']} | "
        f"complete pairs: {report['complete_pairs']}/{report['curve_stems']}"
    )
    parameters = report["parameters"]
    assert isinstance(parameters, dict)
    print(
        f"Parameters: {parameters.get('rows', 0)} rows | "
        f"statuses: {parameters.get('statuses', {})}"
    )
    print("Canonical grids:")
    grids = report["grids"]
    assert isinstance(grids, dict)
    for name, info in grids.items():
        assert isinstance(info, dict)
        print(
            f"  {name}: {info['canonical_points']} points, {info['files']} files, "
            f"{info['non_canonical_files']} non-canonical"
        )
    issues = report["issues"]
    assert isinstance(issues, list)
    print(f"Issues retained: {report['issue_counts_retained']}")
    for issue in issues:
        assert isinstance(issue, dict)
        print(
            f"  [{str(issue['severity']).upper()}] {issue['code']} "
            f"@ {issue['location']}: {issue['message']}"
        )


def main() -> int:
    args = _parse_args()
    dataset_dir = args.dataset_dir.resolve()
    parameters_csv = (args.parameters_csv or dataset_dir / "device_parameters.csv").resolve()
    if not dataset_dir.is_dir():
        raise SystemExit(f"Dataset directory does not exist: {dataset_dir}")
    if args.max_issues < 1:
        raise SystemExit("--max-issues must be at least 1")
    report = validate_dataset(dataset_dir, parameters_csv, args.max_issues)
    _print_report(report)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"JSON report: {args.report.resolve()}")
    return 1 if any(issue["severity"] == "error" for issue in report["issues"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
