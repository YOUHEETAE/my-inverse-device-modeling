from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import matplotlib.tri as mtri
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.colors import LogNorm, SymLogNorm
from matplotlib.figure import Figure

from data_loader import Dataset
from result_types import PNResult


FIELD_OPTIONS = (
    "Net Doping",
    "Potential",
    "Electric Field",
    "Electrons",
    "Holes",
)

LOWER_PLOT_OPTIONS = (
    "Forward I–V",
    "Carrier Concentrations (line cut)",
    "Charge Density (line cut)",
    "Electric Field (line cut)",
    "Potential (line cut)",
    "Band Diagram (line cut)",
)


class PNJunctionApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.result: PNResult | None = None
        self.dataset = Dataset()
        root.title("Chapter 1 — 2D PN Junction")
        width = min(1450, max(1050, int(root.winfo_screenwidth() * 0.9)))
        height = min(880, max(680, int(root.winfo_screenheight() * 0.85)))
        root.geometry(f"{width}x{height}")

        header = ttk.Frame(root, padding=(12, 10))
        header.pack(fill=tk.X)
        ttk.Label(
            header,
            text="Chapter 1. PN Junction",
            font=("TkDefaultFont", 16, "bold"),
        ).pack(side=tk.LEFT)
        ttk.Label(
            header,
            text="DEVSIM 2D drift–diffusion",
            foreground="#52606d",
        ).pack(side=tk.LEFT, padx=(14, 0))

        body = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        controls = ttk.Frame(body, padding=10, width=290)
        plots = ttk.Frame(body, padding=4)
        body.add(controls, weight=0)
        body.add(plots, weight=1)

        self.na_var = tk.StringVar(value="1e18")
        self.nd_var = tk.StringVar(value="1e18")
        self.bias_var = tk.StringVar(value="0.0")
        self.field_var = tk.StringVar(value=FIELD_OPTIONS[0])
        self.lower_plot_var = tk.StringVar(value=LOWER_PLOT_OPTIONS[0])
        self.status_var = tk.StringVar(value="Ready")

        parameters = ttk.LabelFrame(controls, text="Simulation parameters", padding=10)
        parameters.pack(fill=tk.X)
        doping_values = tuple(f"{value:.0e}" for value in self.dataset.dopings)
        self._combo(parameters, "Acceptor NA (cm⁻³)", self.na_var, doping_values, 0)
        self._combo(parameters, "Donor ND (cm⁻³)", self.nd_var, doping_values, 1)
        ttk.Label(parameters, text="Field-map bias (V)").grid(
            row=2, column=0, sticky="w", pady=4
        )
        ttk.Combobox(
            parameters,
            textvariable=self.bias_var,
            values=tuple(f"{value:g}" for value in self.dataset.biases),
            state="readonly",
            width=10,
        ).grid(row=2, column=1, sticky="ew", pady=4)
        parameters.columnconfigure(1, weight=1)

        self.run_button = ttk.Button(
            parameters, text="Load Saved Result", command=self.run
        )
        self.run_button.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        view = ttk.LabelFrame(controls, text="Displayed field", padding=10)
        view.pack(fill=tk.X, pady=(10, 0))
        field_box = ttk.Combobox(
            view,
            textvariable=self.field_var,
            values=FIELD_OPTIONS,
            state="readonly",
        )
        field_box.pack(fill=tk.X)
        field_box.bind("<<ComboboxSelected>>", lambda _event: self.render())

        lower_view = ttk.LabelFrame(controls, text="Lower graph", padding=10)
        lower_view.pack(fill=tk.X, pady=(10, 0))
        lower_box = ttk.Combobox(
            lower_view,
            textvariable=self.lower_plot_var,
            values=LOWER_PLOT_OPTIONS,
            state="readonly",
        )
        lower_box.pack(fill=tk.X)
        lower_box.bind("<<ComboboxSelected>>", lambda _event: self.render())
        ttk.Label(
            lower_view,
            text="Line cuts use the horizontal centerline (y = Ly/2).",
            foreground="#667085",
            wraplength=240,
        ).pack(anchor="w", pady=(6, 0))

        theory = ttk.LabelFrame(controls, text="What to observe", padding=10)
        theory.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        ttk.Label(
            theory,
            text=(
                "• The p-side has negative ionized acceptors.\n\n"
                "• The n-side has positive ionized donors.\n\n"
                "• Carrier diffusion creates the depletion region and "
                "built-in potential.\n\n"
                "• Forward bias lowers the barrier and increases current "
                "exponentially.\n\n"
                "Change NA and ND to compare junction asymmetry."
            ),
            justify=tk.LEFT,
            wraplength=250,
        ).pack(anchor="nw")

        ttk.Label(
            controls, textvariable=self.status_var, foreground="#375a7f", wraplength=260
        ).pack(fill=tk.X, pady=(10, 0))

        self.figure = Figure(figsize=(10, 7), dpi=100, constrained_layout=True)
        grid = self.figure.add_gridspec(2, 1, height_ratios=(1.0, 1.0))
        self.field_axis = self.figure.add_subplot(grid[0])
        self.iv_axis = self.figure.add_subplot(grid[1])
        self.canvas = FigureCanvasTkAgg(self.figure, master=plots)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        toolbar_frame = ttk.Frame(plots)
        toolbar_frame.pack(fill=tk.X)
        NavigationToolbar2Tk(self.canvas, toolbar_frame)
        self._empty_plot()

    @staticmethod
    def _combo(
        parent: ttk.Frame,
        label: str,
        variable: tk.StringVar,
        values: tuple[str, ...],
        row: int,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Combobox(
            parent,
            textvariable=variable,
            values=values,
            state="readonly",
            width=12,
        ).grid(
            row=row, column=1, sticky="ew", pady=4
        )

    def _empty_plot(self) -> None:
        self.field_axis.set_title("Load a saved result to display the 2D field map")
        self.field_axis.set_xlabel("x (µm)")
        self.field_axis.set_ylabel("y (µm)")
        self.iv_axis.set_title("Forward-bias I–V")
        self.iv_axis.set_xlabel("Applied voltage (V)")
        self.iv_axis.set_ylabel("Current (A/cm)")
        self.iv_axis.grid(True, alpha=0.3)
        self.canvas.draw_idle()

    def run(self) -> None:
        try:
            acceptors = float(self.na_var.get())
            donors = float(self.nd_var.get())
            bias = float(self.bias_var.get())
        except ValueError:
            messagebox.showerror("Invalid input", "Enter numeric doping values.")
            return

        self.run_button.configure(state=tk.DISABLED)
        self.status_var.set("Loading precomputed result…")
        self.root.update_idletasks()
        try:
            self.result = self.dataset.load(acceptors, donors, bias)
        except Exception as exc:
            messagebox.showerror("Saved result unavailable", str(exc))
            self.status_var.set("Load failed")
        else:
            self.status_var.set(
                f"Complete — {len(self.result.x_um)} silicon nodes, "
                f"field map at {self.result.selected_bias:.1f} V"
            )
            self.render()
        finally:
            self.run_button.configure(state=tk.NORMAL)

    def render(self) -> None:
        if self.result is None:
            return
        result = self.result
        field = self.field_var.get()
        values, label, norm = self._field_values(result, field)

        self.figure.clear()
        grid = self.figure.add_gridspec(2, 1, height_ratios=(1.0, 1.0))
        self.field_axis = self.figure.add_subplot(grid[0])
        self.iv_axis = self.figure.add_subplot(grid[1])
        triangulation = mtri.Triangulation(result.x_um, result.y_um)
        image = self.field_axis.tripcolor(
            triangulation, values, shading="gouraud", cmap="viridis", norm=norm
        )
        self.figure.colorbar(image, ax=self.field_axis, label=label)
        self.field_axis.axvline(0.05, color="white", linestyle="--", linewidth=1)
        y_min, y_max = float(np.min(result.y_um)), float(np.max(result.y_um))
        y_text = y_min + 0.84 * (y_max - y_min)
        self.field_axis.text(
            0.025,
            y_text,
            "P-type",
            color="white",
            weight="bold",
            ha="center",
            bbox={"facecolor": "black", "alpha": 0.35, "edgecolor": "none"},
        )
        self.field_axis.text(
            0.075,
            y_text,
            "N-type",
            color="white",
            weight="bold",
            ha="center",
            bbox={"facecolor": "black", "alpha": 0.35, "edgecolor": "none"},
        )
        self.field_axis.set_title(
            f"{field} at V = {result.selected_bias:.1f} V"
        )
        self.field_axis.set_xlabel("x (µm)")
        self.field_axis.set_ylabel("y (µm)")
        # Use the full horizontal GUI area. The underlying x/y coordinates and
        # values remain unchanged; only the on-screen display is stretched.
        self.field_axis.set_aspect("auto")

        self._render_lower_plot(result)
        self.canvas.draw_idle()

    def _render_lower_plot(self, result: PNResult) -> None:
        plot = self.lower_plot_var.get()
        axis = self.iv_axis
        if plot == "Forward I–V":
            absolute_current = np.maximum(np.abs(result.currents), 1e-30)
            axis.semilogy(
                result.voltages, absolute_current, marker="o", color="#d1495b"
            )
            axis.set_title("Forward-bias I–V")
            axis.set_xlabel("Applied voltage (V)")
            axis.set_ylabel("|Current| (A/cm)")
            axis.grid(True, which="both", alpha=0.3)
            return

        indices, center_y = self._centerline_indices(result)
        x = result.x_um[indices]
        acceptors = float(self.na_var.get())
        donors = float(self.nd_var.get())
        fixed_limits = self.dataset.line_plot_limits()
        axis.axvline(0.05, color="#667085", linestyle="--", linewidth=1)
        axis.set_xlabel("x along horizontal centerline (µm)")
        axis.grid(True, alpha=0.3)

        if plot == "Carrier Concentrations (line cut)":
            electrons = np.maximum(result.electrons[indices], 1.0)
            holes = np.maximum(result.holes[indices], 1.0)
            axis.semilogy(x, electrons, label="Electrons n", color="#2f4b7c")
            axis.semilogy(x, holes, label="Holes p", color="#d45087")
            axis.text(
                0.025,
                0.95,
                "Majority: holes\nMinority: electrons",
                transform=axis.get_xaxis_transform(),
                ha="center",
                va="top",
            )
            axis.text(
                0.075,
                0.95,
                "Majority: electrons\nMinority: holes",
                transform=axis.get_xaxis_transform(),
                ha="center",
                va="top",
            )
            axis.set_ylabel("Carrier concentration (cm⁻³)")
            axis.set_ylim(*fixed_limits["carrier"])
            axis.legend(loc="lower center", ncol=2, fontsize=8)
            title = "Electron and hole concentrations"
        elif plot == "Charge Density (line cut)":
            q = 1.602176634e-19
            charge = q * (
                result.holes[indices]
                - result.electrons[indices]
                + result.net_doping[indices]
            )
            axis.plot(x, charge, color="#7a5195")
            axis.axhline(0.0, color="black", linewidth=0.8)
            axis.set_ylabel("Charge density ρ (C/cm³)")
            axis.set_ylim(*fixed_limits["charge"])
            title = "Space-charge density"
        elif plot == "Electric Field (line cut)":
            axis.plot(x, result.electric_field_x[indices], color="#ef5675")
            axis.axhline(0.0, color="black", linewidth=0.8)
            axis.set_ylabel("Electric field Ex (V/cm)")
            axis.set_ylim(*fixed_limits["field"])
            title = "Electric-field distribution"
        elif plot == "Potential (line cut)":
            axis.plot(x, result.potential[indices], color="#2f4b7c")
            axis.set_ylabel("Potential ψ (V)")
            axis.set_ylim(*fixed_limits["potential"])
            title = "Electrostatic-potential distribution"
        else:
            # Electron energy changes by -q*psi. When expressed in eV, the
            # numerical energy shift is simply -psi in volts. Align every
            # bias to Ec=0 at the n-side endpoint so bias comparisons use a
            # common energy reference.
            conduction_band = -result.potential[indices]
            conduction_band = conduction_band - conduction_band[-1]
            band_gap = 1.12
            intrinsic_level = conduction_band - band_gap / 2
            valence_band = conduction_band - band_gap
            thermal_voltage = 8.617333262e-5 * 300.0
            intrinsic_density = 1.0e10
            electron_quasi_fermi = intrinsic_level + thermal_voltage * np.log(
                np.maximum(result.electrons[indices], 1.0) / intrinsic_density
            )
            hole_quasi_fermi = intrinsic_level - thermal_voltage * np.log(
                np.maximum(result.holes[indices], 1.0) / intrinsic_density
            )
            axis.plot(x, conduction_band, label="Ec", color="#003f5c")
            axis.plot(x, intrinsic_level, label="Ei", color="#7a5195", linestyle="--")
            axis.plot(x, valence_band, label="Ev", color="#ef5675")
            axis.plot(
                x,
                electron_quasi_fermi,
                label="EFn",
                color="#111111",
                linestyle="-.",
            )
            axis.plot(
                x,
                hole_quasi_fermi,
                label="EFp",
                color="#555555",
                linestyle=":",
            )
            axis.set_ylabel("Relative energy (eV)")
            axis.legend(loc="best", ncol=5, fontsize=8)
            axis.set_ylim(*self.dataset.band_energy_limits(acceptors, donors))
            title = "Energy-band diagram"

        axis.set_title(
            f"{title} at y={center_y:.3f} µm, V={result.selected_bias:.1f} V"
        )

    @staticmethod
    def _centerline_indices(result: PNResult) -> tuple[np.ndarray, float]:
        target = 0.5 * (float(np.min(result.y_um)) + float(np.max(result.y_um)))
        distances = np.abs(result.y_um - target)
        nearest_y = float(result.y_um[int(np.argmin(distances))])
        mask = np.isclose(result.y_um, nearest_y, rtol=0.0, atol=1e-10)
        indices = np.flatnonzero(mask)
        indices = indices[np.argsort(result.x_um[indices])]
        return indices, nearest_y

    @staticmethod
    def _field_values(
        result: PNResult, field: str
    ) -> tuple[np.ndarray, str, object | None]:
        if field == "Net Doping":
            values = result.net_doping
            maximum = max(float(np.max(np.abs(values))), 1.0)
            return (
                values,
                "Net doping (cm⁻³)",
                SymLogNorm(linthresh=1e10, vmin=-maximum, vmax=maximum),
            )
        if field == "Potential":
            return result.potential, "Potential (V)", None
        if field == "Electric Field":
            values = np.maximum(result.electric_field, 1.0)
            return values, "|E| (V/cm)", LogNorm()
        if field == "Electrons":
            values = np.maximum(result.electrons, 1.0)
            return values, "Electron density (cm⁻³)", LogNorm()
        values = np.maximum(result.holes, 1.0)
        return values, "Hole density (cm⁻³)", LogNorm()


def main() -> None:
    root = tk.Tk()
    PNJunctionApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
