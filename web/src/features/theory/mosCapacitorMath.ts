import type { Data } from "plotly.js";
import type { MOSCapResult } from "./types";

// Mirrors tcad/theory/chapter2_long_channel_mosfet/simulations/mos_capacitor/app.py's
// plotting math exactly, so the web tool reproduces the same four panels as
// the Tkinter reference.

export function buildPotentialTraces(result: MOSCapResult): Data[] {
  const oxideDepth = result.oxide_x_nm.map((x) => x - result.oxide_thickness_nm);
  return [
    { type: "scatter", mode: "lines", x: oxideDepth, y: result.oxide_potential, name: "Oxide", line: { color: "#d97706" } },
    { type: "scatter", mode: "lines", x: result.silicon_depth_nm, y: result.silicon_potential, name: "Silicon", line: { color: "#2563eb" } },
  ];
}

export function buildCarrierTraces(result: MOSCapResult): Data[] {
  const electrons = result.electrons.map((v) => Math.max(v, 1));
  const holes = result.holes.map((v) => Math.max(v, 1));
  return [
    { type: "scatter", mode: "lines", x: result.silicon_depth_nm, y: electrons, name: "Electrons n", line: { color: "#2563eb" } },
    { type: "scatter", mode: "lines", x: result.silicon_depth_nm, y: holes, name: "Holes p", line: { color: "#db2777" } },
    {
      type: "scatter",
      mode: "lines",
      x: [0, depthLimit(result)],
      y: [result.acceptor_doping, result.acceptor_doping],
      name: "NA",
      line: { color: "#7f1d1d", dash: "dash" },
    },
  ];
}

export function buildChargeDensityTrace(result: MOSCapResult): Data[] {
  return [
    {
      type: "scatter",
      mode: "lines",
      x: result.silicon_depth_nm,
      y: result.charge_density,
      line: { color: "#7c3aed" },
      showlegend: false,
    },
  ];
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}

// Silicon room-temperature thermal voltage kT/q (eV), half/full bandgap
// (eV), and intrinsic carrier concentration (cm^-3) — same constants the
// Tkinter reference hardcodes for this same plot.
const KT_OVER_Q_EV = 0.025852;
const HALF_BANDGAP_EV = 0.56;
const BANDGAP_EV = 1.12;
const NI_CM3 = 1e10;

export function buildBandDiagramTraces(result: MOSCapResult): Data[] {
  const rawConduction = result.silicon_potential.map((psi) => -psi);
  const shift = rawConduction[rawConduction.length - 1];
  const conduction = rawConduction.map((v) => v - shift);
  const intrinsic = conduction.map((v) => v - HALF_BANDGAP_EV);
  const valence = conduction.map((v) => v - BANDGAP_EV);
  const fermiSamples = intrinsic.map(
    (ei, i) => ei + KT_OVER_Q_EV * Math.log(Math.max(result.electrons[i], 1) / NI_CM3),
  );
  const fermiLevel = median(fermiSamples);
  const fermi = conduction.map(() => fermiLevel);

  return [
    { type: "scatter", mode: "lines", x: result.silicon_depth_nm, y: conduction, name: "Ec", line: { color: "#2563eb" } },
    { type: "scatter", mode: "lines", x: result.silicon_depth_nm, y: intrinsic, name: "Ei", line: { color: "#7c3aed", dash: "dash" } },
    { type: "scatter", mode: "lines", x: result.silicon_depth_nm, y: valence, name: "Ev", line: { color: "#db2777" } },
    { type: "scatter", mode: "lines", x: result.silicon_depth_nm, y: fermi, name: "EF", line: { color: "#111111", dash: "dashdot" } },
  ];
}

// Reference app clips the silicon-side x-axis to the near-surface region
// (depth <= 300nm) since that's where all the interesting band bending
// happens — the mesh extends much further into the field-free bulk.
export function depthLimit(result: MOSCapResult): number {
  return Math.min(300, Math.max(...result.silicon_depth_nm));
}
