from __future__ import annotations

import argparse
import csv
import math
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk

import matplotlib

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure


@dataclass
class CurveSet:
    stem: str
    structure_id: str
    doping_run_id: str
    idvd_csv: Path
    idvg_csv: Path


def _resolve_default_dataset(script_file: Path) -> Path:
    return script_file.resolve().parents[1] / "dataset"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive I-V CSV visualization")
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=_resolve_default_dataset(Path(__file__)),
        help="Directory containing *_IdVd.csv and *_IdVg.csv files",
    )
    return parser.parse_args()


def _discover_curve_sets(dataset_dir: Path) -> list[CurveSet]:
    idvd_files = {p.stem.removesuffix("_IdVd"): p for p in dataset_dir.glob("*_IdVd.csv")}
    idvg_files = {p.stem.removesuffix("_IdVg"): p for p in dataset_dir.glob("*_IdVg.csv")}
    stems = sorted(set(idvd_files) & set(idvg_files))
    curve_sets: list[CurveSet] = []
    for stem in stems:
        idvd_csv = idvd_files[stem]
        idvg_csv = idvg_files[stem]
        rows = _read_rows(idvd_csv)
        first = rows[0] if rows else {}
        curve_sets.append(
            CurveSet(
                stem=stem,
                structure_id=(first.get("structure_id") or "").strip() or stem,
                doping_run_id=(first.get("doping_run_id") or "").strip() or stem,
                idvd_csv=idvd_csv,
                idvg_csv=idvg_csv,
            )
        )
    return curve_sets


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _group_rows(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row["curve_tag"], []).append(row)
    return grouped


def _float(row: dict[str, str], name: str) -> float:
    return float(row[name])


def _positive_abs(values: list[float]) -> list[float]:
    floor = 1e-30
    return [max(abs(value), floor) for value in values]


def _plot_curve(
    axis,
    rows: list[dict[str, str]],
    x_name: str,
    title: str,
    x_label: str,
    log_scale: bool,
) -> None:
    if not rows:
        axis.set_title(title)
        axis.text(0.5, 0.5, "No data", ha="center", va="center", transform=axis.transAxes)
        axis.grid(True, alpha=0.3)
        return

    sorted_rows = sorted(rows, key=lambda row: _float(row, x_name))
    xs = [_float(row, x_name) for row in sorted_rows]
    ys = [_float(row, "drain_current") for row in sorted_rows]
    if log_scale:
        ys = _positive_abs(ys)
        axis.set_yscale("log")
        y_label = "|Drain current| (mA/um)"
    else:
        y_label = "Drain current (mA/um)"

    tag = sorted_rows[0].get("curve_tag", "")
    axis.plot(xs, ys, linewidth=1.8, label=tag)
    axis.set_title(title)
    axis.set_xlabel(x_label)
    axis.set_ylabel(y_label)
    axis.grid(True, alpha=0.3)
    axis.legend(fontsize=8)


class IVVisualizationApp:
    def __init__(self, root: tk.Tk, dataset_dir: Path) -> None:
        self.root = root
        self.dataset_dir = dataset_dir
        self.curve_sets: list[CurveSet] = []

        root.title("I-V Visualization")
        root.geometry("1500x900")

        self.selected_structure_id = tk.StringVar()
        self.selected_doping_run_id = tk.StringVar()
        self.status_text = tk.StringVar()

        controls = ttk.Frame(root, padding=(10, 8))
        controls.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(controls, text="Structure").pack(side=tk.LEFT)
        self.structure_combo = ttk.Combobox(
            controls,
            textvariable=self.selected_structure_id,
            state="readonly",
            width=24,
        )
        self.structure_combo.pack(side=tk.LEFT, padx=(8, 12))
        self.structure_combo.bind("<<ComboboxSelected>>", lambda _event: self.structure_changed())

        ttk.Label(controls, text="Doping").pack(side=tk.LEFT)
        self.doping_combo = ttk.Combobox(
            controls,
            textvariable=self.selected_doping_run_id,
            state="readonly",
            width=24,
        )
        self.doping_combo.pack(side=tk.LEFT, padx=(8, 12))
        self.doping_combo.bind("<<ComboboxSelected>>", lambda _event: self.plot_selected())

        ttk.Button(controls, text="Refresh", command=self.refresh).pack(side=tk.LEFT)
        ttk.Label(controls, textvariable=self.status_text).pack(side=tk.LEFT, padx=(12, 0))

        self.figure = Figure(figsize=(15, 8), dpi=100)
        self.axes = self.figure.subplots(2, 3)
        self.canvas = FigureCanvasTkAgg(self.figure, master=root)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        toolbar_frame = ttk.Frame(root)
        toolbar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        NavigationToolbar2Tk(self.canvas, toolbar_frame)

        self.refresh()

    def refresh(self) -> None:
        self.curve_sets = _discover_curve_sets(self.dataset_dir)
        structure_ids = sorted({curve_set.structure_id for curve_set in self.curve_sets})
        self.structure_combo["values"] = structure_ids

        if self.selected_structure_id.get() not in structure_ids:
            self.selected_structure_id.set(structure_ids[0] if structure_ids else "")

        self._refresh_doping_values()
        self.status_text.set(f"{len(self.curve_sets)} set(s) in {self.dataset_dir}")
        self.plot_selected()

    def structure_changed(self) -> None:
        self._refresh_doping_values()
        self.plot_selected()

    def _refresh_doping_values(self) -> None:
        structure_id = self.selected_structure_id.get()
        doping_run_ids = sorted(
            {
                curve_set.doping_run_id
                for curve_set in self.curve_sets
                if curve_set.structure_id == structure_id
            }
        )
        self.doping_combo["values"] = doping_run_ids
        if self.selected_doping_run_id.get() not in doping_run_ids:
            self.selected_doping_run_id.set(doping_run_ids[0] if doping_run_ids else "")

    def _selected_curve_set(self) -> CurveSet | None:
        structure_id = self.selected_structure_id.get()
        doping_run_id = self.selected_doping_run_id.get()
        for curve_set in self.curve_sets:
            if (
                curve_set.structure_id == structure_id
                and curve_set.doping_run_id == doping_run_id
            ):
                return curve_set
        return None

    def plot_selected(self) -> None:
        for axis in self.axes.ravel():
            axis.clear()

        curve_set = self._selected_curve_set()
        if curve_set is None:
            self.axes[0][1].text(
                0.5,
                0.5,
                "No *_IdVd/*_IdVg CSV pairs found",
                ha="center",
                va="center",
                transform=self.axes[0][1].transAxes,
            )
            self.figure.tight_layout()
            self.canvas.draw()
            return

        idvd_groups = _group_rows(_read_rows(curve_set.idvd_csv))
        idvg_groups = _group_rows(_read_rows(curve_set.idvg_csv))

        idvd_tag = sorted(idvd_groups)[0] if idvd_groups else ""
        idvg_tags = sorted(idvg_groups)
        idvg_tag_0 = idvg_tags[0] if len(idvg_tags) > 0 else ""
        idvg_tag_1 = idvg_tags[1] if len(idvg_tags) > 1 else ""

        plots = [
            (idvd_groups.get(idvd_tag, []), "drain_v", f"IdVd {idvd_tag}", "Vd (V)"),
            (idvg_groups.get(idvg_tag_0, []), "gate_v", f"IdVg {idvg_tag_0}", "Vg (V)"),
            (idvg_groups.get(idvg_tag_1, []), "gate_v", f"IdVg {idvg_tag_1}", "Vg (V)"),
        ]

        for col, (rows, x_name, title, x_label) in enumerate(plots):
            _plot_curve(self.axes[0][col], rows, x_name, title, x_label, log_scale=False)
            _plot_curve(
                self.axes[1][col],
                rows,
                x_name,
                f"{title} log scale",
                x_label,
                log_scale=True,
            )

        self.figure.suptitle(curve_set.stem, fontsize=14)
        self.figure.tight_layout()
        self.canvas.draw()


def main() -> None:
    args = _parse_args()
    root = tk.Tk()
    IVVisualizationApp(root, args.dataset_dir.resolve())
    root.mainloop()


if __name__ == "__main__":
    main()
