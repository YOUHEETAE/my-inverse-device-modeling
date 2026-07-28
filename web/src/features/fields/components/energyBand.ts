import type { MeshData } from "../types";

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

// Port of ai/shared/field_data.py's region_interpolator(): linear barycentric
// interpolation of node-level Potential, restricted to the triangles that
// belong to one mesh region (mirrors mtri.LinearTriInterpolator over a
// region-masked triangulation). Returns NaN outside the region's hull, same
// as the Python version's mtri masked-array `.filled(np.nan)`.
function buildRegionInterpolator(mesh: MeshData, potential: number[], region: number) {
  const triangles = mesh.triangles.filter((_, i) => mesh.element_region[i] === region);
  return (x: number, y: number): number => {
    for (const [a, b, c] of triangles) {
      const [ax, ay] = mesh.node_xy_nm[a];
      const [bx, by] = mesh.node_xy_nm[b];
      const [cx, cy] = mesh.node_xy_nm[c];
      if (pointInTriangle(x, y, ax, ay, bx, by, cx, cy)) {
        const [l1, l2, l3] = barycentric(x, y, ax, ay, bx, by, cx, cy);
        return l1 * potential[a] + l2 * potential[b] + l3 * potential[c];
      }
    }
    return NaN;
  };
}

function linspace(start: number, end: number, count: number): number[] {
  if (count <= 1) return [start];
  const step = (end - start) / (count - 1);
  return Array.from({ length: count }, (_, i) => start + i * step);
}

export interface EnergyBandVerticalPanel {
  depth: number[];
  ec: number[];
  ev: number[];
  name: string;
  ecColor: string;
  evColor: string;
}

export interface EnergyBandResult {
  channelCut: { x: number[]; ec: number[]; ev: number[]; yChannel: number; gateLeft: number; gateRight: number };
  verticalCut: { panels: EnergyBandVerticalPanel[]; oxideTop: number };
}

const VERTICAL_STYLES: { region: number; offset: number; gap: number; name: string; ecColor: string; evColor: string }[] = [
  { region: 0, offset: 0.0, gap: 1.12, name: "Bulk", ecColor: "#1565C0", evColor: "#C62828" },
  { region: 1, offset: 3.1, gap: 9.0, name: "Oxide", ecColor: "#00897B", evColor: "#6A1B9A" },
  { region: 2, offset: 0.0, gap: 1.12, name: "Gate", ecColor: "#42A5F5", evColor: "#EF5350" },
];

// Port of frontend/visualization/field_rendering.py's _draw_energy_band_pair():
// approximates conduction/valence band edges (Ec/Ev) from the model's
// predicted electrostatic potential, sampled along the channel (x, at fixed
// y just inside the bulk surface) and vertically through Gate/Oxide/Bulk (y,
// at the device's horizontal center).
export function computeEnergyBand(mesh: MeshData, potential: number[], lengthNm: number, toxNm: number): EnergyBandResult {
  const bulkIdx = mesh.node_region.reduce<number[]>((acc, r, i) => {
    if (r === 0) acc.push(i);
    return acc;
  }, []);
  const bulkX = bulkIdx.map((i) => mesh.node_xy_nm[i][0]);
  const xMin = Math.min(...bulkX);
  const xMax = Math.max(...bulkX);
  const positiveY = bulkIdx.map((i) => mesh.node_xy_nm[i][1]).filter((y) => y > 1e-8);
  const yChannel = positiveY.length > 0 ? Math.min(...positiveY) : 0;

  const xLine = linspace(xMin, xMax, 1000);
  const bulkInterp = buildRegionInterpolator(mesh, potential, 0);
  const rawPotential = xLine.map((x) => bulkInterp(x, yChannel));
  const firstFiniteIndex = rawPotential.findIndex((v) => Number.isFinite(v));
  const reference = firstFiniteIndex >= 0 ? -rawPotential[firstFiniteIndex] : 0;
  const ec = rawPotential.map((v) => -v - reference);
  const ev = ec.map((v) => v - 1.12);

  const width = xMax - xMin;
  const gateLeft = xMin + 350.0;
  const gateRight = gateLeft + lengthNm;
  const xCenter = xMin + width / 2;

  const panels: EnergyBandVerticalPanel[] = VERTICAL_STYLES.map(({ region, offset, gap, name, ecColor, evColor }) => {
    const regionIdx = mesh.node_region.reduce<number[]>((acc, r, i) => {
      if (r === region) acc.push(i);
      return acc;
    }, []);
    const regionY = regionIdx.map((i) => mesh.node_xy_nm[i][1]);
    const yMin = Math.min(...regionY);
    const yMax = Math.max(...regionY);
    const depth = linspace(yMin, yMax, 400);
    const interp = buildRegionInterpolator(mesh, potential, region);
    const regionPotential = depth.map((y) => interp(xCenter, y));
    const regionEc = regionPotential.map((v) => -v + offset - reference);
    const regionEv = regionEc.map((v) => v - gap);
    return { depth, ec: regionEc, ev: regionEv, name, ecColor, evColor };
  });

  return {
    channelCut: { x: xLine, ec, ev, yChannel, gateLeft, gateRight },
    verticalCut: { panels, oxideTop: -toxNm },
  };
}
