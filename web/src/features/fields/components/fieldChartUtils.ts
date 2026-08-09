import type { Data, Layout } from "plotly.js";
import type { MeshData } from "../types";

// Element-domain values (one per triangle) get averaged onto the triangle's three
// corner nodes so they can drive mesh3d's per-vertex `intensity` the same way
// node-domain values do. Mirrors the desktop app's _element_to_node() in
// frontend/visualization/field_rendering.py.
export function elementToNode(values: (number | null)[], triangles: [number, number, number][], nodeCount: number): number[] {
  const sums = new Array(nodeCount).fill(0);
  const counts = new Array(nodeCount).fill(0);
  triangles.forEach((tri, index) => {
    const value = values[index];
    if (value == null) return;
    tri.forEach((nodeIndex) => {
      sums[nodeIndex] += value;
      counts[nodeIndex] += 1;
    });
  });
  return sums.map((sum, index) => (counts[index] > 0 ? sum / counts[index] : NaN));
}

export function buildMeshEdges(mesh: MeshData) {
  const x: (number | null)[] = [];
  const y: (number | null)[] = [];
  mesh.triangles.forEach(([a, b, c]) => {
    for (const nodeIndex of [a, b, c, a]) {
      x.push(mesh.node_xy_nm[nodeIndex][0]);
      y.push(-mesh.node_xy_nm[nodeIndex][1]);
    }
    x.push(null);
    y.push(null);
  });
  return { x, y };
}

// `camera.projection` (orthographic top-down lock) is supported by plotly.js at
// runtime but missing from its TS types, hence the cast.
//
// aspectmode is deliberately NOT set here. Do not set it to "data": these
// meshes have x/y in nm (extents in the hundreds to low thousands) but a
// near-zero-thickness z (mesh z=0, overlay lines at z=0.02-0.05), and "data"
// mode sets each axis's ratio to extent[i] / cbrt(Ex*Ey*Ez) — folding the
// ~0.05 z-extent into that geometric mean blows the x/y ratios up into the
// tens (e.g. 36 and 21.6 for a 1400x840nm device). Plotly's orthographic
// camera always renders a fixed view-volume height of 2, so an aspectratio
// in the tens leaves only a small sliver of the device visible — this is
// what "way too zoomed in" turned out to be, not a camera/zoom setting.
// camera.eye's *distance* has no effect on what's visible under orthographic
// projection (only its direction does) — mouse-wheel zoom instead scales
// aspectratio directly. aspectmode:"manual" plus a computed aspectratio
// (see computeMeshAspectRatio / computeSharedMeshScale below, applied
// per-instance by MeshScenePlot) is the correct fix.
export const SCENE_LAYOUT = {
  xaxis: { visible: false },
  yaxis: { visible: false },
  zaxis: { visible: false, range: [-1, 1] },
  camera: { eye: { x: 0, y: 0, z: 1.6 }, up: { x: 0, y: 1, z: 0 }, projection: { type: "orthographic" } },
  dragmode: "pan",
} as unknown as Partial<Layout["scene"]>;

// Explicit x/y range computed from the mesh itself, rather than leaving the
// scene to Plotly's own autorange — autorange re-derives from trace data on
// every relayout and can transiently disagree with the manual aspectratio
// MeshScenePlot sets, so pinning it once up front keeps the two in sync.
export function computeMeshSceneRange(mesh: MeshData, paddingFraction = 0.05): { x: [number, number]; y: [number, number] } {
  const xs = mesh.node_xy_nm.map(([x]) => x);
  const ys = mesh.node_xy_nm.map(([, y]) => -y);
  const rangeWithPadding = (values: number[]): [number, number] => {
    const min = Math.min(...values);
    const max = Math.max(...values);
    const pad = (max - min) * paddingFraction || 1;
    return [min - pad, max + pad];
  };
  return { x: rangeWithPadding(xs), y: rangeWithPadding(ys) };
}

function meshExtent(mesh: MeshData): { x: number; y: number } {
  const xs = mesh.node_xy_nm.map(([x]) => x);
  const ys = mesh.node_xy_nm.map(([, y]) => y);
  return {
    x: Math.max(...xs) - Math.min(...xs) || 1,
    y: Math.max(...ys) - Math.min(...ys) || 1,
  };
}

// aspectmode:"manual" needs an aspectratio computed the same way Plotly's own
// "data" mode would — extent-proportional — but normalized against the
// device's own x/y extent instead of folding the near-zero z extent into a
// shared geometric mean (see the aspectmode:"data" note on SCENE_LAYOUT
// above). The orthographic camera's view volume is a fixed height of 2 and
// width 2*containerAspect, so this scales whichever axis is more constrained
// by that volume down to marginFactor of it, and lets the other axis fall out
// proportionally.
function scaleForExtent(xExtent: number, yExtent: number, containerAspect: number, marginFactor: number): number {
  const scaleX = (2 * containerAspect * marginFactor) / xExtent;
  const scaleY = (2 * marginFactor) / yExtent;
  return Math.min(scaleX, scaleY);
}

export function computeMeshAspectRatio(
  mesh: MeshData,
  containerAspect: number,
  marginFactor = 0.9,
): { x: number; y: number; z: number } {
  const { x: xExtent, y: yExtent } = meshExtent(mesh);
  const scale = scaleForExtent(xExtent, yExtent, containerAspect, marginFactor);
  return { x: xExtent * scale, y: yExtent * scale, z: 0.02 };
}

// Compare view variant: rather than each panel maximizing itself independently
// (which gives two differently-sized devices the same on-screen footprint,
// hiding their real relative size), this derives one nm-per-unit scale from
// whichever compared device has the largest extent, so every panel uses the
// same scale and a physically bigger device reads as visually bigger too.
export function computeSharedMeshScale(meshes: MeshData[], containerAspect: number, marginFactor = 0.9): number {
  const extents = meshes.map(meshExtent);
  const maxXExtent = Math.max(...extents.map((e) => e.x));
  const maxYExtent = Math.max(...extents.map((e) => e.y));
  return scaleForExtent(maxXExtent, maxYExtent, containerAspect, marginFactor);
}

export function computeMeshAspectRatioForScale(mesh: MeshData, scale: number): { x: number; y: number; z: number } {
  const { x: xExtent, y: yExtent } = meshExtent(mesh);
  return { x: xExtent * scale, y: yExtent * scale, z: 0.02 };
}

export function buildMeshTrace(
  mesh: MeshData,
  intensity: number[],
  cmin: number,
  cmax: number,
  colorscale: string | [number, string][],
  reversescale: boolean,
  colorbarTitle: string | null,
): Data {
  return {
    type: "mesh3d",
    x: mesh.node_xy_nm.map(([x]) => x),
    y: mesh.node_xy_nm.map(([, y]) => -y),
    z: mesh.node_xy_nm.map(() => 0),
    i: mesh.triangles.map(([a]) => a),
    j: mesh.triangles.map(([, b]) => b),
    k: mesh.triangles.map(([, , c]) => c),
    intensity,
    cmin,
    cmax,
    colorscale,
    reversescale,
    showscale: colorbarTitle != null,
    colorbar: colorbarTitle != null ? { title: { text: colorbarTitle }, len: 0.8 } : undefined,
    flatshading: false,
    lighting: { ambient: 1, diffuse: 0, specular: 0 },
    // plotly.js's TS types require i/j/k as TypedArray, but the runtime accepts
    // plain number[] fine (as does the rest of this codebase's Plot usage).
  } as unknown as Data;
}
