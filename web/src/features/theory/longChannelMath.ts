import type { Data, Layout } from "plotly.js";

type Shape = NonNullable<Layout["shapes"]>[number];
import { buildHeatmapTrace, type FieldSelection } from "./pnJunctionMath";
import type { LongChannelFieldOption, LongChannelRegion, LongChannelResult } from "./types";

// Port of the desktop app's LongChannelMOSFETApp._field_scale()
// (tcad/theory/chapter2_long_channel_mosfet/simulations/long_channel_mosfet/app.py):
// the color scale (norm + vmin/vmax) is computed once across every region's
// values for the selected field, not per region, so gate/oxide/bulk share one
// consistent color mapping. The oxide region has no net_doping/electrons/holes
// (it's an insulator) — those fields render oxide as a flat fill instead of a
// gradient there, same as the desktop app's ListedColormap(["#d9dde3"]) case.
export interface LongChannelFieldSelection {
  label: string;
  regionSelections: Record<string, FieldSelection | null>;
}

function regionValues(region: LongChannelRegion, field: LongChannelFieldOption): number[] | null {
  if (field === "Potential") return region.potential;
  if (field === "Net Doping") return region.net_doping;
  if (field === "Electrons") return region.electrons ? region.electrons.map((v) => Math.max(v, 1)) : null;
  return region.holes ? region.holes.map((v) => Math.max(v, 1)) : null;
}

export function selectLongChannelField(
  regions: Record<string, LongChannelRegion>,
  field: LongChannelFieldOption,
): LongChannelFieldSelection {
  const perRegionValues: Record<string, number[] | null> = {};
  for (const [name, region] of Object.entries(regions)) {
    perRegionValues[name] = regionValues(region, field);
  }
  const combined = Object.values(perRegionValues).filter((v): v is number[] => v != null).flat();

  if (field === "Net Doping") {
    const maxAbs = Math.max(...combined.map((v) => Math.abs(v)), 1);
    const regionSelections: Record<string, FieldSelection | null> = {};
    for (const [name, values] of Object.entries(perRegionValues)) {
      regionSelections[name] = values
        ? { values, label: "Net doping (cm⁻³)", normType: "symlog", vmin: -maxAbs, vmax: maxAbs, linthresh: 1e12 }
        : null;
    }
    return { label: "Net doping (cm⁻³)", regionSelections };
  }
  if (field === "Potential") {
    const vmin = Math.min(...combined);
    const vmax = Math.max(...combined);
    const regionSelections: Record<string, FieldSelection | null> = {};
    for (const [name, values] of Object.entries(perRegionValues)) {
      regionSelections[name] = values ? { values, label: "Potential (V)", normType: "linear", vmin, vmax, linthresh: null } : null;
    }
    return { label: "Potential (V)", regionSelections };
  }
  const label = field === "Electrons" ? "Electron density (cm⁻³)" : "Hole density (cm⁻³)";
  const vmax = Math.max(...combined, 10);
  const regionSelections: Record<string, FieldSelection | null> = {};
  for (const [name, values] of Object.entries(perRegionValues)) {
    regionSelections[name] = values ? { values, label, normType: "log", vmin: 1, vmax, linthresh: null } : null;
  }
  return { label, regionSelections };
}

// Builds one heatmap trace per region that has data for the selected field,
// plus a flat gray rectangle shape for regions that don't (mirrors the
// desktop app's flat oxide fill for Net Doping/Electrons/Holes).
export function buildLongChannelFieldTraces(
  regions: Record<string, LongChannelRegion>,
  field: LongChannelFieldOption,
  gridSize = 70,
): { traces: Data[]; shapes: Shape[]; label: string } {
  const selection = selectLongChannelField(regions, field);
  const traces: Data[] = [];
  const shapes: Shape[] = [];
  for (const [name, regionSelection] of Object.entries(selection.regionSelections)) {
    const region = regions[name];
    if (regionSelection) {
      traces.push(buildHeatmapTrace(region, regionSelection, gridSize));
    } else {
      shapes.push({
        type: "rect",
        x0: Math.min(...region.x_um),
        x1: Math.max(...region.x_um),
        y0: Math.min(...region.y_um),
        y1: Math.max(...region.y_um),
        fillcolor: "#d9dde3",
        line: { width: 0 },
        layer: "below",
      });
    }
  }
  return { traces, shapes, label: selection.label };
}

// Port of _selected_snapshot()'s nearest-point matching, and the ID-VG /
// ID-VD marker + dashed-guideline placement in _draw_idvg()/_draw_idvd().
export function nearestValue(values: number[], requested: number): number {
  let best = values[0];
  let bestDistance = Infinity;
  for (const value of values) {
    const distance = Math.abs(value - requested);
    if (distance < bestDistance) {
      bestDistance = distance;
      best = value;
    }
  }
  return best;
}

export function buildIdVgTrace(result: LongChannelResult): Data {
  const currents = result.drain_currents.map((v) => Math.max(Math.abs(v), 1e-30));
  return {
    type: "scatter",
    mode: "lines+markers",
    x: result.gate_voltages,
    y: currents,
    line: { color: "#c44e52", width: 2 },
    marker: { size: 4 },
    name: "ID–VG",
    hoverinfo: "x+y",
  } as Data;
}

export function buildIdVdTraces(result: LongChannelResult): Data[] {
  const colors = ["#3568c0", "#16a085", "#e08b2c", "#c44e52", "#8e44ad"];
  const nearestGate = nearestValue(result.idvd_gate_voltages, result.selected_gate_voltage);
  return result.idvd_gate_voltages.map((gateVoltage, index) => {
    const highlighted = Math.abs(gateVoltage - nearestGate) < 1e-9;
    return {
      type: "scatter",
      mode: highlighted ? "lines+markers" : "lines",
      x: result.idvd_drain_voltages,
      y: result.idvd_currents[index].map((v) => Math.abs(v)),
      line: { color: colors[index % colors.length], width: highlighted ? 2.6 : 1.4 },
      marker: { size: 3.5 },
      opacity: highlighted ? 1 : 0.72,
      name: `VG=${gateVoltage} V`,
      hoverinfo: "x+y+name",
    } as Data;
  });
}
