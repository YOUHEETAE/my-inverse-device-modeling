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
export const SCENE_LAYOUT = {
  xaxis: { visible: false },
  yaxis: { visible: false },
  zaxis: { visible: false, range: [-1, 1] },
  aspectmode: "data",
  camera: { eye: { x: 0, y: 0, z: 1.6 }, up: { x: 0, y: 1, z: 0 }, projection: { type: "orthographic" } },
  dragmode: "pan",
} as unknown as Partial<Layout["scene"]>;

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
