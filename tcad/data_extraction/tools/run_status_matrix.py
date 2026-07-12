from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


OK = 0
INITIAL_FAILURE = 1
SWEEP_FAILURE = 2
MISSING = 3


@dataclass(frozen=True)
class Cell:
    category: int
    label: str
    detail: str


def _default_dataset_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "dataset"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Visualize current IdVd/IdVg files in dataset as a status matrix."
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=_default_dataset_dir(),
        help="Directory containing *_IdVd.csv and *_IdVg.csv files",
    )
    parser.add_argument(
        "--save",
        type=Path,
        help="Save the figure (for example, run_status_matrix.png)",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Do not open the interactive window (useful with --save)",
    )
    return parser.parse_args()


def _ids_from_stem(stem: str) -> tuple[str, str]:
    match = re.match(r"(?P<structure>.+?)(?P<doping>B.+)$", stem)
    if not match:
        return stem, "unknown"
    return match.group("structure"), match.group("doping")


def _read_curve_file(path: Path, stem: str) -> tuple[str, str, dict[str, list[float]], int]:
    structure_id, doping_run_id = _ids_from_stem(stem)
    points: dict[str, list[float]] = {}
    row_count = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            row_count += 1
            structure_id = (row.get("structure_id") or structure_id).strip()
            doping_run_id = (row.get("doping_run_id") or doping_run_id).strip()
            tag = (row.get("curve_tag") or "").strip()
            x_name = "gate_v" if tag.startswith("IDVG") else "drain_v"
            try:
                points.setdefault(tag, []).append(float(row[x_name]))
            except (KeyError, ValueError):
                continue
    return structure_id, doping_run_id, points, row_count


def _dataset_cell(
    structure_id: str,
    doping_run_id: str,
    idvd_points: dict[str, list[float]],
    idvg_points: dict[str, list[float]],
    row_count: int,
) -> Cell:
    prefix = f"{structure_id} / {doping_run_id}"
    if row_count == 0:
        return Cell(INITIAL_FAILURE, "X", f"{prefix}\nNo IV points in current dataset files")

    expected = (
        ("IdVd", "Vd", idvd_points, ("IDVD_VG1P5", "IDVD_VG3P0"), 3.0),
        ("IdVg", "Vg", idvg_points, ("IDVG_VD0P05", "IDVG_VD1P5"), 3.0),
    )
    for stage, voltage_name, groups, tags, target in expected:
        for tag in tags:
            values = groups.get(tag, [])
            if not values or max(values) < target - 1e-9:
                voltage = max(values) if values else None
                voltage_label = "unknown" if voltage is None else f"{voltage:g} V"
                return Cell(
                    SWEEP_FAILURE,
                    f"X\n{stage}\n{voltage_label}",
                    f"{prefix}\nIncomplete {tag}; last {voltage_name}={voltage_label}",
                )

    return Cell(OK, "O", f"{prefix}\nComplete IdVd/IdVg files")


def _load_dataset(
    dataset_dir: Path,
) -> tuple[list[str], list[str], dict[tuple[str, str], Cell], Counter[int]]:
    structures: list[str] = []
    doping_runs: list[str] = []
    cells: dict[tuple[str, str], Cell] = {}

    idvd_files = {path.stem.removesuffix("_IdVd"): path for path in dataset_dir.glob("*_IdVd.csv")}
    idvg_files = {path.stem.removesuffix("_IdVg"): path for path in dataset_dir.glob("*_IdVg.csv")}
    for stem in sorted(idvd_files.keys() | idvg_files.keys()):
        structure_id, doping_run_id = _ids_from_stem(stem)
        idvd_points: dict[str, list[float]] = {}
        idvg_points: dict[str, list[float]] = {}
        row_count = 0
        if stem in idvd_files:
            structure_id, doping_run_id, idvd_points, count = _read_curve_file(idvd_files[stem], stem)
            row_count += count
        if stem in idvg_files:
            vg_structure, vg_doping, idvg_points, count = _read_curve_file(idvg_files[stem], stem)
            structure_id = vg_structure or structure_id
            doping_run_id = vg_doping or doping_run_id
            row_count += count

        if structure_id not in structures:
            structures.append(structure_id)
        if doping_run_id not in doping_runs:
            doping_runs.append(doping_run_id)
        cells[(structure_id, doping_run_id)] = _dataset_cell(
            structure_id, doping_run_id, idvd_points, idvg_points, row_count
        )

    counts: Counter[int] = Counter(cell.category for cell in cells.values())
    return structures, doping_runs, cells, counts


def _plot_matrix(
    structures: list[str],
    doping_runs: list[str],
    cells: dict[tuple[str, str], Cell],
    counts: Counter[int],
):
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch

    values = np.full((len(structures), len(doping_runs)), MISSING, dtype=int)
    for y, structure_id in enumerate(structures):
        for x, doping_run_id in enumerate(doping_runs):
            cell = cells.get((structure_id, doping_run_id))
            if cell:
                values[y, x] = cell.category

    figure_width = max(18.0, len(doping_runs) * 1.2)
    figure_height = max(10.0, len(structures) * 0.31)
    fig, ax = plt.subplots(figsize=(figure_width, figure_height))
    colors = ["#cfe8ff", "#f6b26b", "#f4cccc", "#eeeeee"]
    ax.imshow(values, cmap=ListedColormap(colors), vmin=0, vmax=3, aspect="auto")

    ax.set_xticks(range(len(doping_runs)), labels=doping_runs, rotation=55, ha="right")
    ax.set_yticks(range(len(structures)), labels=structures)
    ax.set_xlabel("doping_run_id")
    ax.set_ylabel("structure_id")
    ax.set_title(
        "Run status matrix\n"
        f"OK {counts[OK]} | initial convergence failure {counts[INITIAL_FAILURE]} | "
        f"sweep failure {counts[SWEEP_FAILURE]}"
    )

    ax.set_xticks(np.arange(-0.5, len(doping_runs), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(structures), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=0.45)
    ax.tick_params(which="minor", bottom=False, left=False)

    for y, structure_id in enumerate(structures):
        for x, doping_run_id in enumerate(doping_runs):
            cell = cells.get((structure_id, doping_run_id))
            if not cell:
                continue
            if cell.category == SWEEP_FAILURE:
                ax.text(x, y, cell.label, ha="center", va="center", fontsize=5.5, color="#8b0000")
            else:
                ax.text(x, y, cell.label, ha="center", va="center", fontsize=5.5, color="#333333")

    legend = [
        Patch(facecolor=colors[OK], label="O: OK"),
        Patch(facecolor=colors[INITIAL_FAILURE], label="X: initial convergence failure"),
        Patch(facecolor=colors[SWEEP_FAILURE], label="X: sweep failure (last converged voltage shown)"),
        Patch(facecolor=colors[MISSING], label="Missing pair"),
    ]
    ax.legend(handles=legend, loc="upper left", bbox_to_anchor=(1.005, 1.0))

    annotation = ax.annotate(
        "",
        xy=(0, 0),
        xytext=(12, 12),
        textcoords="offset points",
        bbox={"boxstyle": "round", "fc": "white", "alpha": 0.95},
        arrowprops={"arrowstyle": "->"},
    )
    annotation.set_visible(False)

    def on_move(event) -> None:
        if event.inaxes is not ax or event.xdata is None or event.ydata is None:
            if annotation.get_visible():
                annotation.set_visible(False)
                fig.canvas.draw_idle()
            return
        x, y = int(round(event.xdata)), int(round(event.ydata))
        if not (0 <= x < len(doping_runs) and 0 <= y < len(structures)):
            return
        cell = cells.get((structures[y], doping_runs[x]))
        if cell is None:
            return
        annotation.xy = (x, y)
        annotation.set_text(cell.detail)
        annotation.set_visible(True)
        fig.canvas.draw_idle()

    fig.canvas.mpl_connect("motion_notify_event", on_move)
    fig.tight_layout()
    return fig


def main() -> None:
    args = _parse_args()
    structures, doping_runs, cells, counts = _load_dataset(args.dataset_dir.resolve())
    fig = _plot_matrix(structures, doping_runs, cells, counts)

    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(args.save, dpi=180, bbox_inches="tight")
        print(f"Saved: {args.save.resolve()}")
    if not args.no_show:
        import matplotlib.pyplot as plt

        plt.show()


if __name__ == "__main__":
    main()
