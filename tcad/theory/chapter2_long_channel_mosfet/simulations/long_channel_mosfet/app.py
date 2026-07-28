from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import matplotlib.tri as mtri
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.colors import ListedColormap, LogNorm, Normalize, SymLogNorm
from matplotlib.figure import Figure

from data_loader import load_saved_result
from result_types import LongChannelResult, MOSFETSnapshot, RegionSnapshot


FIELDS = ("Net Doping", "Potential", "Electrons", "Holes")
FIELD_VOLTAGES = (0.0, 0.5, 1.0, 1.5, 2.0)
FIELD_DRAIN_VOLTAGES = (0.0, 0.5, 1.0, 1.5, 2.0)
CURVE_COLORS = ("#3568c0", "#16a085", "#e08b2c", "#c44e52")


class LongChannelMOSFETApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.result: LongChannelResult | None = None
        self.idvg_axis = None
        self.idvd_axis = None

        root.title("Chapter 2 · Long-Channel MOSFET")
        width = min(1500, max(1120, int(root.winfo_screenwidth() * 0.92)))
        height = min(940, max(760, int(root.winfo_screenheight() * 0.9)))
        root.geometry(f"{width}x{height}")
        root.minsize(1050, 700)

        header = ttk.Frame(root, padding=(14, 10, 14, 6))
        header.pack(fill=tk.X)
        ttk.Label(
            header,
            text="Long-Channel NMOS · Field Map and I–V Characteristics",
            font=("TkDefaultFont", 16, "bold"),
        ).pack(side=tk.LEFT)
        ttk.Label(
            header,
            text="saved DEVSIM result viewer",
            foreground="#667085",
        ).pack(side=tk.RIGHT)

        body = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        controls = ttk.Frame(body, padding=(8, 6), width=285)
        plots = ttk.Frame(body, padding=2)
        body.add(controls, weight=0)
        body.add(plots, weight=1)

        self.field_var = tk.StringVar(value="Electrons")
        self.vg_var = tk.StringVar(value="1")
        self.vd_var = tk.StringVar(value="1")
        self.status_var = tk.StringVar(value="Loading saved result…")
        self.bias_var = tk.StringVar()

        settings = ttk.LabelFrame(controls, text="Field-map condition", padding=10)
        settings.pack(fill=tk.X)
        self._combo(settings, "Displayed quantity", self.field_var, FIELDS)
        self._combo(
            settings,
            "Gate voltage  VG (V)",
            self.vg_var,
            tuple(f"{value:g}" for value in FIELD_VOLTAGES),
        )
        self._combo(
            settings,
            "Drain voltage  VD (V)",
            self.vd_var,
            tuple(f"{value:g}" for value in FIELD_DRAIN_VOLTAGES),
        )
        ttk.Label(
            settings,
            textvariable=self.bias_var,
            foreground="#315b8a",
        ).pack(anchor="w", pady=(2, 8))
        self.reload_button = ttk.Button(
            settings,
            text="Reload Saved Data",
            command=self.load,
        )
        self.reload_button.pack(fill=tk.X)

        structure = ttk.LabelFrame(controls, text="Device", padding=10)
        structure.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(
            structure,
            text=(
                "Gate length       0.5 µm\n"
                "Device width      1.0 µm\n"
                "Oxide thickness   0.1 µm\n"
                "Body              p-type\n"
                "Source / Drain    n+"
            ),
            justify=tk.LEFT,
        ).pack(anchor="w")

        guide = ttk.LabelFrame(controls, text="How to read", padding=10)
        guide.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        ttk.Label(
            guide,
            text=(
                "1. Change VG and observe the electron channel below the oxide.\n\n"
                "2. Compare the selected VG with the marker on ID–VG.\n\n"
                "3. Change VD and follow the operating point on the highlighted "
                "ID–VD curve.\n\n"
                "Tip: click either lower graph to move to the nearest saved "
                "field-map condition."
            ),
            justify=tk.LEFT,
            wraplength=245,
        ).pack(anchor="nw")
        ttk.Label(
            controls,
            textvariable=self.status_var,
            foreground="#667085",
            wraplength=255,
        ).pack(fill=tk.X, pady=(10, 0))

        self.figure = Figure(figsize=(10.5, 8), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, master=plots)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        toolbar = ttk.Frame(plots)
        toolbar.pack(fill=tk.X)
        NavigationToolbar2Tk(self.canvas, toolbar)
        self.canvas.mpl_connect("button_press_event", self._graph_clicked)
        self._empty_plot()
        root.after_idle(self.load)

    def _combo(self, parent, label, variable, values) -> None:
        ttk.Label(parent, text=label).pack(anchor="w")
        combo = ttk.Combobox(
            parent,
            textvariable=variable,
            values=values,
            state="readonly",
        )
        combo.pack(fill=tk.X, pady=(2, 8))
        combo.bind("<<ComboboxSelected>>", lambda _event: self.render())

    def _empty_plot(self) -> None:
        self.figure.clear()
        axis = self.figure.add_subplot(111)
        axis.text(
            0.5,
            0.5,
            "Loading the precomputed Gmsh / DEVSIM result…",
            transform=axis.transAxes,
            ha="center",
            va="center",
            color="#667085",
        )
        axis.set_axis_off()
        self.canvas.draw_idle()

    def load(self) -> None:
        self.reload_button.configure(state=tk.DISABLED)
        self.status_var.set("Loading compressed result…")
        self.root.update_idletasks()
        try:
            result = load_saved_result()
        except Exception as exc:
            self.status_var.set("Could not load saved data.")
            messagebox.showerror("Saved result unavailable", str(exc))
        else:
            self.result = result
            if result.idvd_currents.size:
                self.status_var.set(
                    f"Loaded {len(result.gate_voltages)} ID–VG points, "
                    f"{result.idvd_currents.size} ID–VD points."
                )
            else:
                self.status_var.set(
                    "Legacy ID–VG data loaded. Run generate_dataset.py once "
                    "to add ID–VD curves and bias-dependent field maps."
                )
            self.render()
        finally:
            self.reload_button.configure(state=tk.NORMAL)

    @staticmethod
    def _nearest(values, requested: float) -> float:
        array = np.asarray(values, dtype=float)
        return float(array[np.argmin(np.abs(array - requested))])

    def _selected_snapshot(self) -> MOSFETSnapshot:
        assert self.result is not None
        vg = float(self.vg_var.get())
        vd = float(self.vd_var.get())
        if self.result.idvd_snapshots:
            key = min(
                self.result.idvd_snapshots,
                key=lambda item: abs(item[0] - vg) + abs(item[1] - vd),
            )
            return self.result.idvd_snapshots[key]
        old_vg = self._nearest(tuple(self.result.snapshots), vg)
        return self.result.snapshots[old_vg]

    def render(self) -> None:
        if self.result is None:
            return
        snapshot = self._selected_snapshot()
        self.bias_var.set(
            f"Showing  VG={snapshot.gate_voltage:g} V, "
            f"VD={snapshot.drain_voltage:g} V"
        )

        self.figure.clear()
        grid = self.figure.add_gridspec(
            2,
            2,
            height_ratios=(1.12, 1.0),
            hspace=0.42,
            wspace=0.28,
            left=0.075,
            right=0.94,
            bottom=0.08,
            top=0.95,
        )
        field_axis = self.figure.add_subplot(grid[0, :])
        self.idvg_axis = self.figure.add_subplot(grid[1, 0])
        self.idvd_axis = self.figure.add_subplot(grid[1, 1])
        self._draw_field_map(field_axis, snapshot)
        self._draw_idvg(self.idvg_axis, snapshot.gate_voltage)
        self._draw_idvd(
            self.idvd_axis,
            snapshot.gate_voltage,
            snapshot.drain_voltage,
        )
        self.canvas.draw_idle()

    def _all_snapshots(self) -> list[MOSFETSnapshot]:
        assert self.result is not None
        if self.result.idvd_snapshots:
            return list(self.result.idvd_snapshots.values())
        return list(self.result.snapshots.values())

    def _field_scale(self):
        field = self.field_var.get()
        snapshots = self._all_snapshots()
        if field == "Net Doping":
            arrays = [
                region.net_doping
                for snapshot in snapshots
                for region in snapshot.regions.values()
                if region.net_doping is not None
            ]
            maximum = max(
                max(float(np.max(np.abs(values))) for values in arrays),
                1.0,
            )
            return (
                "Net doping (cm⁻³)",
                SymLogNorm(linthresh=1e12, vmin=-maximum, vmax=maximum),
                "coolwarm",
            )
        if field == "Potential":
            arrays = [
                region.potential
                for snapshot in snapshots
                for region in snapshot.regions.values()
            ]
            minimum = min(float(np.min(values)) for values in arrays)
            maximum = max(float(np.max(values)) for values in arrays)
            if np.isclose(minimum, maximum):
                maximum = minimum + 1.0
            return "Potential (V)", Normalize(minimum, maximum), "viridis"
        model = "electrons" if field == "Electrons" else "holes"
        arrays = [
            getattr(region, model)
            for snapshot in snapshots
            for region in snapshot.regions.values()
            if getattr(region, model) is not None
        ]
        maximum = max(float(np.max(values)) for values in arrays)
        return (
            "Electron density (cm⁻³)"
            if field == "Electrons"
            else "Hole density (cm⁻³)",
            LogNorm(vmin=1.0, vmax=max(maximum, 10.0)),
            "viridis" if field == "Electrons" else "magma",
        )

    def _draw_field_map(self, axis, snapshot: MOSFETSnapshot) -> None:
        label, norm, cmap = self._field_scale()
        image = None
        for region_name in ("gate", "oxide", "bulk"):
            region = snapshot.regions[region_name]
            values = self._region_values(region)
            triangulation = mtri.Triangulation(region.x_um, region.y_um)
            if values is None:
                axis.tripcolor(
                    triangulation,
                    np.zeros_like(region.x_um),
                    shading="flat",
                    cmap=ListedColormap(["#d9dde3"]),
                    norm=Normalize(0.0, 1.0),
                )
            else:
                image = axis.tripcolor(
                    triangulation,
                    values,
                    shading="gouraud",
                    norm=norm,
                    cmap=cmap,
                )
        if image is not None:
            colorbar = self.figure.colorbar(
                image,
                ax=axis,
                label=label,
                pad=0.018,
                fraction=0.035,
            )
            colorbar.ax.tick_params(labelsize=8)
        axis.set_title(
            f"{self.field_var.get()} field map  ·  "
            f"VG={snapshot.gate_voltage:g} V, VD={snapshot.drain_voltage:g} V",
            pad=7,
        )
        axis.set_xlabel("Lateral position x (µm)")
        axis.set_ylabel("Depth y (µm)")
        axis.set_xlim(0.0, 1.0)
        axis.set_ylim(0.35, -0.21)
        axis.set_aspect("auto")
        axis.text(0.5, -0.15, "Gate", ha="center", weight="bold", fontsize=9)
        axis.text(0.5, -0.045, "Oxide", ha="center", weight="bold", fontsize=8)
        axis.text(0.12, 0.035, "Source n+", ha="center", weight="bold", fontsize=8)
        axis.text(0.88, 0.035, "Drain n+", ha="center", weight="bold", fontsize=8)
        axis.text(0.5, 0.28, "p-type body", ha="center", weight="bold", fontsize=8)

    def _draw_idvg(self, axis, selected_vg: float) -> None:
        assert self.result is not None
        currents = np.maximum(np.abs(self.result.drain_currents), 1e-30)
        axis.semilogy(
            self.result.gate_voltages,
            currents,
            marker="o",
            markersize=3.5,
            linewidth=1.8,
            color="#c44e52",
        )
        nearest_vg = self._nearest(self.result.gate_voltages, selected_vg)
        index = int(np.argmin(np.abs(self.result.gate_voltages - nearest_vg)))
        axis.scatter(
            [nearest_vg],
            [currents[index]],
            s=58,
            facecolor="white",
            edgecolor="#222222",
            linewidth=1.4,
            zorder=5,
        )
        axis.axvline(selected_vg, color="#555555", linestyle=":", linewidth=1)
        axis.set_title(f"Transfer characteristic  ID–VG  (VD={self.result.drain_voltage:g} V)")
        axis.set_xlabel("Gate voltage VG (V)")
        axis.set_ylabel("|Drain current| (A/cm)")
        axis.grid(True, which="both", alpha=0.25)

    def _draw_idvd(self, axis, selected_vg: float, selected_vd: float) -> None:
        assert self.result is not None
        if not self.result.idvd_currents.size:
            axis.text(
                0.5,
                0.5,
                "ID–VD data not found\nRun generate_dataset.py",
                transform=axis.transAxes,
                ha="center",
                va="center",
                color="#667085",
            )
            axis.set_title("Output characteristics  ID–VD")
            axis.set_axis_off()
            return

        nearest_gate = self._nearest(
            self.result.idvd_gate_voltages,
            selected_vg,
        )
        selected_family = 0
        for index, (gate_voltage, currents) in enumerate(
            zip(self.result.idvd_gate_voltages, self.result.idvd_currents)
        ):
            highlighted = np.isclose(gate_voltage, nearest_gate)
            if highlighted:
                selected_family = index
            axis.plot(
                self.result.idvd_drain_voltages,
                np.abs(currents),
                marker="o" if highlighted else None,
                markersize=3,
                linewidth=2.5 if highlighted else 1.35,
                alpha=1.0 if highlighted else 0.72,
                color=CURVE_COLORS[index % len(CURVE_COLORS)],
                label=f"VG={gate_voltage:g} V",
                zorder=3 if highlighted else 2,
            )
        nearest_drain = self._nearest(
            self.result.idvd_drain_voltages,
            selected_vd,
        )
        drain_index = int(
            np.argmin(np.abs(self.result.idvd_drain_voltages - nearest_drain))
        )
        axis.scatter(
            [nearest_drain],
            [abs(self.result.idvd_currents[selected_family, drain_index])],
            s=58,
            facecolor="white",
            edgecolor="#222222",
            linewidth=1.4,
            zorder=5,
        )
        axis.axvline(selected_vd, color="#555555", linestyle=":", linewidth=1)
        axis.set_title("Output characteristics  ID–VD")
        axis.set_xlabel("Drain voltage VD (V)")
        axis.set_ylabel("|Drain current| (A/cm)")
        axis.grid(True, alpha=0.25)
        axis.legend(fontsize=8, frameon=False, ncol=2)

    def _graph_clicked(self, event) -> None:
        if self.result is None or event.xdata is None:
            return
        if event.inaxes is self.idvg_axis:
            gate_voltage = self._nearest(FIELD_VOLTAGES, event.xdata)
            self.vg_var.set(f"{gate_voltage:g}")
            self.render()
        elif event.inaxes is self.idvd_axis and self.result.idvd_currents.size:
            drain_voltage = self._nearest(FIELD_DRAIN_VOLTAGES, event.xdata)
            self.vd_var.set(f"{drain_voltage:g}")
            self.render()

    def _region_values(self, region: RegionSnapshot) -> np.ndarray | None:
        field = self.field_var.get()
        if field == "Potential":
            return region.potential
        if field == "Net Doping":
            return region.net_doping
        if field == "Electrons":
            return (
                None
                if region.electrons is None
                else np.maximum(region.electrons, 1.0)
            )
        return None if region.holes is None else np.maximum(region.holes, 1.0)


def main() -> None:
    root = tk.Tk()
    LongChannelMOSFETApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
