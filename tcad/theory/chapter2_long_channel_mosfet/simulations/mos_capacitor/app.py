from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from data_loader import MOSCapDataset
from result_types import MOSCapResult


class MOSCapacitorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.result: MOSCapResult | None = None
        self.dataset = MOSCapDataset()
        root.title("Chapter 2 — MOS Capacitor")
        width = min(1500, max(1100, int(root.winfo_screenwidth() * 0.9)))
        height = min(900, max(700, int(root.winfo_screenheight() * 0.86)))
        root.geometry(f"{width}x{height}")

        header = ttk.Frame(root, padding=(12, 10))
        header.pack(fill=tk.X)
        ttk.Label(
            header,
            text="MOS Capacitor: Gate Control of the Silicon Surface",
            font=("TkDefaultFont", 16, "bold"),
        ).pack(side=tk.LEFT)

        body = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        controls = ttk.Frame(body, padding=10, width=300)
        plots = ttk.Frame(body, padding=4)
        body.add(controls, weight=0)
        body.add(plots, weight=1)

        self.na_var = tk.StringVar(value="1e17")
        self.tox_var = tk.StringVar(value="10")
        self.vg_var = tk.StringVar(value="0")
        self.status_var = tk.StringVar(value="Ready")
        self.regime_var = tk.StringVar(value="Regime: —")

        settings = ttk.LabelFrame(controls, text="MOS capacitor settings", padding=10)
        settings.pack(fill=tk.X)
        self._combo(
            settings,
            "Acceptor NA (cm⁻³)",
            self.na_var,
            tuple(f"{value:.0e}" for value in self.dataset.acceptor_dopings),
            0,
        )
        self._combo(
            settings,
            "Oxide thickness (nm)",
            self.tox_var,
            tuple(f"{value:g}" for value in self.dataset.oxide_thicknesses_nm),
            1,
        )
        self._combo(
            settings,
            "Gate voltage VG (V)",
            self.vg_var,
            tuple(f"{value:g}" for value in self.dataset.gate_voltages),
            2,
        )
        self.run_button = ttk.Button(
            settings, text="Load Saved Result", command=self.run
        )
        self.run_button.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        settings.columnconfigure(1, weight=1)

        state = ttk.LabelFrame(controls, text="Surface state", padding=10)
        state.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(
            state,
            textvariable=self.regime_var,
            font=("TkDefaultFont", 12, "bold"),
        ).pack(anchor="w")
        self.surface_var = tk.StringVar(value="")
        ttk.Label(
            state,
            textvariable=self.surface_var,
            justify=tk.LEFT,
            wraplength=260,
        ).pack(anchor="w", pady=(6, 0))

        guide = ttk.LabelFrame(controls, text="How to read", padding=10)
        guide.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        ttk.Label(
            guide,
            text=(
                "Negative VG attracts holes: accumulation.\n\n"
                "VG = 0 is the ideal flat-band reference.\n\n"
                "Small positive VG repels holes: depletion.\n\n"
                "Larger positive VG raises the surface electron density: inversion.\n\n"
                "The inversion layer becomes the MOSFET channel in the next section."
            ),
            justify=tk.LEFT,
            wraplength=260,
        ).pack(anchor="nw")
        ttk.Label(
            controls,
            textvariable=self.status_var,
            foreground="#375a7f",
            wraplength=270,
        ).pack(fill=tk.X, pady=(10, 0))

        self.figure = Figure(figsize=(10, 7), dpi=100, constrained_layout=True)
        self.canvas = FigureCanvasTkAgg(self.figure, master=plots)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        toolbar = ttk.Frame(plots)
        toolbar.pack(fill=tk.X)
        NavigationToolbar2Tk(self.canvas, toolbar)
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
            width=11,
        ).grid(row=row, column=1, sticky="ew", pady=4)

    def _empty_plot(self) -> None:
        axis = self.figure.add_subplot(111)
        axis.text(
            0.5,
            0.5,
            "Choose NA, oxide thickness, and VG, then load the saved result.",
            transform=axis.transAxes,
            ha="center",
            va="center",
        )
        axis.set_axis_off()
        self.canvas.draw_idle()

    def run(self) -> None:
        try:
            acceptors = float(self.na_var.get())
            tox = float(self.tox_var.get())
            gate_voltage = float(self.vg_var.get())
        except ValueError:
            messagebox.showerror("Invalid input", "Select valid numeric values.")
            return

        self.run_button.configure(state=tk.DISABLED)
        self.status_var.set("Loading precomputed result…")
        self.root.update_idletasks()
        try:
            self.result = self.dataset.load(acceptors, tox, gate_voltage)
        except Exception as exc:
            self.status_var.set("Load failed")
            messagebox.showerror("Saved result unavailable", str(exc))
        else:
            self.status_var.set("Simulation complete")
            self.regime_var.set(f"Regime: {self.result.regime}")
            self.surface_var.set(
                f"n(surface) = {self.result.electrons[0]:.3e} cm⁻³\n"
                f"p(surface) = {self.result.holes[0]:.3e} cm⁻³\n"
                f"Qg = {self.result.gate_charge_c_per_cm2:.3e} C/cm²"
            )
            self.render()
        finally:
            self.run_button.configure(state=tk.NORMAL)

    def render(self) -> None:
        if self.result is None:
            return
        result = self.result
        self.figure.clear()
        axes = self.figure.subplots(2, 2)

        axis = axes[0, 0]
        oxide_depth = result.oxide_x_nm - result.oxide_thickness_nm
        axis.plot(oxide_depth, result.oxide_potential, label="Oxide", color="#d97706")
        axis.plot(
            result.silicon_depth_nm,
            result.silicon_potential,
            label="Silicon",
            color="#2563eb",
        )
        axis.axvline(0, color="#333333", linestyle=":")
        axis.set_title("Potential across Oxide / Silicon")
        axis.set_xlabel("Position from Si surface (nm)")
        axis.set_ylabel("Potential (V)")
        axis.legend()
        axis.grid(True, alpha=0.25)

        axis = axes[0, 1]
        axis.semilogy(
            result.silicon_depth_nm,
            np.maximum(result.electrons, 1.0),
            label="Electrons n",
            color="#2563eb",
        )
        axis.semilogy(
            result.silicon_depth_nm,
            np.maximum(result.holes, 1.0),
            label="Holes p",
            color="#db2777",
        )
        axis.axhline(
            result.acceptor_doping,
            color="#7f1d1d",
            linestyle="--",
            label="NA",
        )
        axis.set_xlim(0, min(300, float(np.max(result.silicon_depth_nm))))
        axis.set_title(f"Carrier Distribution — {result.regime}")
        axis.set_xlabel("Depth into Silicon (nm)")
        axis.set_ylabel("Concentration (cm⁻³)")
        axis.legend()
        axis.grid(True, which="both", alpha=0.25)

        axis = axes[1, 0]
        axis.plot(
            result.silicon_depth_nm,
            result.charge_density,
            color="#7c3aed",
        )
        axis.axhline(0, color="#333333", linewidth=0.8)
        axis.set_xlim(0, min(300, float(np.max(result.silicon_depth_nm))))
        axis.set_title("Space Charge Density")
        axis.set_xlabel("Depth into Silicon (nm)")
        axis.set_ylabel("ρ (C/cm³)")
        axis.grid(True, alpha=0.25)

        axis = axes[1, 1]
        conduction = -result.silicon_potential
        conduction -= conduction[-1]
        intrinsic = conduction - 0.56
        valence = conduction - 1.12
        fermi_samples = intrinsic + 0.025852 * np.log(
            np.maximum(result.electrons, 1.0) / 1e10
        )
        fermi = np.full_like(conduction, float(np.median(fermi_samples)))
        axis.plot(result.silicon_depth_nm, conduction, label="Ec", color="#2563eb")
        axis.plot(
            result.silicon_depth_nm,
            intrinsic,
            "--",
            label="Ei",
            color="#7c3aed",
        )
        axis.plot(result.silicon_depth_nm, valence, label="Ev", color="#db2777")
        axis.plot(
            result.silicon_depth_nm,
            fermi,
            "-.",
            label="EF",
            color="#111111",
        )
        axis.set_xlim(0, min(300, float(np.max(result.silicon_depth_nm))))
        axis.set_title("Silicon Energy Band")
        axis.set_xlabel("Depth into Silicon (nm)")
        axis.set_ylabel("Relative energy (eV)")
        axis.legend(ncol=4, fontsize=8)
        axis.grid(True, alpha=0.25)

        self.figure.suptitle(
            f"p-type MOS Capacitor: NA={result.acceptor_doping:.0e} cm⁻³, "
            f"tox={result.oxide_thickness_nm:g} nm, VG={result.gate_voltage:g} V",
            fontsize=12,
            fontweight="bold",
        )
        self.canvas.draw_idle()


def main() -> None:
    root = tk.Tk()
    MOSCapacitorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
