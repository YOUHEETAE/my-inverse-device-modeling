import type { Data } from "plotly.js";
import type { PNResult, FieldOption } from "./types";

function sign(px: number, py: number, ax: number, ay: number, bx: number, by: number): number {
  return (px - bx) * (ay - by) - (ax - bx) * (py - by);
}

function pointInTriangle(
  px: number,
  py: number,
  ax: number,
  ay: number,
  bx: number,
  by: number,
  cx: number,
  cy: number,
): boolean {
  const d1 = sign(px, py, ax, ay, bx, by);
  const d2 = sign(px, py, bx, by, cx, cy);
  const d3 = sign(px, py, cx, cy, ax, ay);
  const hasNeg = d1 < 0 || d2 < 0 || d3 < 0;
  const hasPos = d1 > 0 || d2 > 0 || d3 > 0;
  return !(hasNeg && hasPos);
}

function barycentric(
  px: number,
  py: number,
  ax: number,
  ay: number,
  bx: number,
  by: number,
  cx: number,
  cy: number,
): [number, number, number] {
  const denom = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy);
  const l1 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / denom;
  const l2 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / denom;
  return [l1, l2, 1 - l1 - l2];
}

function linspace(start: number, end: number, count: number): number[] {
  if (count <= 1) return [start];
  const step = (end - start) / (count - 1);
  return Array.from({ length: count }, (_, i) => start + i * step);
}

export interface GridField {
  x: number[];
  y: number[];
  z: (number | null)[][];
}

// Narrow shape interpolateToGrid()/buildHeatmapTrace() actually need — PNResult
// and (for Chapter 2) LongChannelRegion both structurally satisfy this, so a
// single grid/heatmap implementation serves both without either result type
// depending on the other.
export interface MeshRegion {
  x_um: number[];
  y_um: number[];
  triangles: [number, number, number][];
}

// Port of the desktop app's axis.tripcolor(..., shading="gouraud"): rather
// than plotting discrete point markers, interpolate the scattered
// (triangulated) mesh values onto a regular grid — same linear barycentric
// technique as region_interpolator() in ai/shared/field_data.py (ported for
// Field Map's energy-band panel in energyBand.ts) — so Plotly's native 2D
// `heatmap` trace can render a smoothly-shaded surface. mesh3d was tried
// first (matching Field Map's approach) but Plotly 3D scenes don't stretch
// to fill a wide, non-square container the way the desktop app's
// set_aspect("auto") does; a 2D trace does this naturally.
export function interpolateToGrid(mesh: MeshRegion, values: number[], gridSize = 90): GridField {
  const xMin = Math.min(...mesh.x_um);
  const xMax = Math.max(...mesh.x_um);
  const yMin = Math.min(...mesh.y_um);
  const yMax = Math.max(...mesh.y_um);
  const gridX = linspace(xMin, xMax, gridSize);
  const gridY = linspace(yMin, yMax, gridSize);

  const z: (number | null)[][] = gridY.map(() => new Array(gridSize).fill(null));
  for (let row = 0; row < gridSize; row++) {
    const py = gridY[row];
    for (let col = 0; col < gridSize; col++) {
      const px = gridX[col];
      for (const [a, b, c] of mesh.triangles) {
        const ax = mesh.x_um[a];
        const ay = mesh.y_um[a];
        const bx = mesh.x_um[b];
        const by = mesh.y_um[b];
        const cx = mesh.x_um[c];
        const cy = mesh.y_um[c];
        // Cheap bounding-box reject before the exact (and pricier)
        // point-in-triangle test — most triangles are nowhere near a given
        // grid point.
        if (px < Math.min(ax, bx, cx) || px > Math.max(ax, bx, cx)) continue;
        if (py < Math.min(ay, by, cy) || py > Math.max(ay, by, cy)) continue;
        if (pointInTriangle(px, py, ax, ay, bx, by, cx, cy)) {
          const [l1, l2, l3] = barycentric(px, py, ax, ay, bx, by, cx, cy);
          z[row][col] = l1 * values[a] + l2 * values[b] + l3 * values[c];
          break;
        }
      }
    }
  }
  return { x: gridX, y: gridY, z };
}

export function transformValue(v: number, normType: "linear" | "symlog" | "log", linthresh: number | null): number {
  if (normType === "log") return Math.log10(Math.max(Math.abs(v), 1e-300));
  if (normType === "symlog") {
    const t = linthresh ?? 1;
    return Math.sign(v) * Math.log10(1 + Math.abs(v) / t);
  }
  return v;
}

export function normBounds(
  normType: "linear" | "symlog" | "log",
  vmin: number,
  vmax: number,
  linthresh: number | null,
): { cmin: number; cmax: number } {
  if (normType === "log") {
    return { cmin: Math.log10(Math.max(vmin, 1e-300)), cmax: Math.log10(Math.max(vmax, 1e-300)) };
  }
  if (normType === "symlog") {
    const t = linthresh ?? 1;
    const bound = Math.log10(1 + vmax / t);
    return { cmin: -bound, cmax: bound };
  }
  return { cmin: vmin, cmax: vmax };
}

// Builds the full heatmap trace for a FieldSelection (see selectField()
// below): grids the scattered values, applies the same log/symlog/linear
// transform applyNorm() (features/fields/components/colormap.ts) uses —
// reimplemented here null-safely since applyNorm operates on a flat array
// with no concept of "outside the mesh". Shared by the PN junction tool and
// (for per-region field maps, e.g. Chapter 2's gate/oxide/bulk) any other
// MeshRegion-shaped result.
export function buildHeatmapTrace(mesh: MeshRegion, selection: FieldSelection, gridSize = 90): Data {
  const grid = interpolateToGrid(mesh, selection.values, gridSize);
  const z = grid.z.map((row) => row.map((v) => (v == null ? null : transformValue(v, selection.normType, selection.linthresh))));
  const { cmin, cmax } = normBounds(selection.normType, selection.vmin, selection.vmax, selection.linthresh);

  return {
    type: "heatmap",
    x: grid.x,
    y: grid.y,
    z,
    zmin: cmin,
    zmax: cmax,
    colorscale: "Viridis",
    zsmooth: "best",
    showscale: true,
    colorbar: { title: { text: selection.label }, thickness: 14, tickfont: { size: 9 } },
    hoverinfo: "skip",
  } as unknown as Data;
}

export function buildPNHeatmapTrace(result: PNResult, selection: FieldSelection, gridSize = 90): Data {
  return buildHeatmapTrace(result, selection, gridSize);
}

// Port of the desktop app's PNJunctionApp._field_values()
// (tcad/theory/chapter1_pn_junction/app.py). Returns the raw values plus the
// normalization params applyNorm() (features/fields/components/colormap.ts)
// expects.
export interface FieldSelection {
  values: number[];
  label: string;
  normType: "linear" | "symlog" | "log";
  vmin: number;
  vmax: number;
  linthresh: number | null;
}

export function selectField(result: PNResult, field: FieldOption): FieldSelection {
  if (field === "Net Doping") {
    const maxAbs = Math.max(...result.net_doping.map((v) => Math.abs(v)), 1);
    return { values: result.net_doping, label: "Net doping (cm⁻³)", normType: "symlog", vmin: -maxAbs, vmax: maxAbs, linthresh: 1e10 };
  }
  if (field === "Potential") {
    return {
      values: result.potential,
      label: "Potential (V)",
      normType: "linear",
      vmin: Math.min(...result.potential),
      vmax: Math.max(...result.potential),
      linthresh: null,
    };
  }
  if (field === "Electric Field") {
    const floored = result.electric_field.map((v) => Math.max(v, 1));
    return { values: floored, label: "|E| (V/cm)", normType: "log", vmin: Math.min(...floored), vmax: Math.max(...floored), linthresh: null };
  }
  if (field === "Electrons") {
    const floored = result.electrons.map((v) => Math.max(v, 1));
    return {
      values: floored,
      label: "Electron density (cm⁻³)",
      normType: "log",
      vmin: Math.min(...floored),
      vmax: Math.max(...floored),
      linthresh: null,
    };
  }
  const floored = result.holes.map((v) => Math.max(v, 1));
  return { values: floored, label: "Hole density (cm⁻³)", normType: "log", vmin: Math.min(...floored), vmax: Math.max(...floored), linthresh: null };
}

// Port of _centerline_indices(): the horizontal line of mesh points closest
// to the vertical midpoint, sorted left-to-right.
export function centerlineIndices(result: PNResult): { indices: number[]; centerY: number } {
  const yMin = Math.min(...result.y_um);
  const yMax = Math.max(...result.y_um);
  const target = (yMin + yMax) / 2;

  let nearestY = result.y_um[0];
  let bestDistance = Infinity;
  for (const y of result.y_um) {
    const distance = Math.abs(y - target);
    if (distance < bestDistance) {
      bestDistance = distance;
      nearestY = y;
    }
  }

  const indices = result.y_um
    .map((y, index) => ({ y, index }))
    .filter(({ y }) => Math.abs(y - nearestY) < 1e-10)
    .map(({ index }) => index)
    .sort((a, b) => result.x_um[a] - result.x_um[b]);

  return { indices, centerY: nearestY };
}

const ELEMENTARY_CHARGE = 1.602176634e-19;
const BAND_GAP_EV = 1.12;
const THERMAL_VOLTAGE_V = 8.617333262e-5 * 300.0;
const INTRINSIC_DENSITY_CM3 = 1.0e10;

export interface BandDiagram {
  x: number[];
  conductionBand: number[];
  intrinsicLevel: number[];
  valenceBand: number[];
  electronQuasiFermi: number[];
  holeQuasiFermi: number[];
}

// Port of the "Band Diagram (line cut)" branch of _render_lower_plot().
export function computeBandDiagram(result: PNResult, indices: number[]): BandDiagram {
  const x = indices.map((i) => result.x_um[i]);
  const rawConduction = indices.map((i) => -result.potential[i]);
  const reference = rawConduction[rawConduction.length - 1] ?? 0;
  const conductionBand = rawConduction.map((v) => v - reference);
  const intrinsicLevel = conductionBand.map((v) => v - BAND_GAP_EV / 2);
  const valenceBand = conductionBand.map((v) => v - BAND_GAP_EV);

  const electronQuasiFermi = indices.map((i, k) => {
    const electrons = Math.max(result.electrons[i], 1.0);
    return intrinsicLevel[k] + THERMAL_VOLTAGE_V * Math.log(electrons / INTRINSIC_DENSITY_CM3);
  });
  const holeQuasiFermi = indices.map((i, k) => {
    const holes = Math.max(result.holes[i], 1.0);
    return intrinsicLevel[k] - THERMAL_VOLTAGE_V * Math.log(holes / INTRINSIC_DENSITY_CM3);
  });

  return { x, conductionBand, intrinsicLevel, valenceBand, electronQuasiFermi, holeQuasiFermi };
}

// Port of the "Charge Density (line cut)" branch: rho = q(p - n + Nnet).
export function computeChargeDensity(result: PNResult, indices: number[]): number[] {
  return indices.map(
    (i) => ELEMENTARY_CHARGE * (result.holes[i] - result.electrons[i] + result.net_doping[i]),
  );
}
