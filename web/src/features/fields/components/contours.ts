import type { MeshData } from "../types";

// Port of frontend/visualization/field_rendering.py's _contour_levels(): 11
// evenly spaced levels across the normalized value range. The Python version
// uses np.geomspace(...,10) for LogNorm specifically because matplotlib's
// LogNorm keeps raw (non-log-transformed) values — but this codebase's
// applyNorm() (colormap.ts) already pre-transforms log/symlog values to a
// linear color-axis domain before this is ever called, so a single linear
// spacing is correct for every norm type here.
export function contourLevels(cmin: number, cmax: number, count = 11): number[] {
  if (!(cmax > cmin)) return [];
  const step = (cmax - cmin) / (count - 1);
  return Array.from({ length: count }, (_, i) => cmin + i * step);
}

// Marching-triangles: for each triangle and each level, find the (at most
// one) line segment where the linearly-interpolated node value crosses that
// level. Mirrors what matplotlib's axis.tricontour() does under the hood,
// operating on the same per-node values already used to color the mesh3d
// surface (buildMeshTrace's `intensity`).
export function computeContourSegments(
  mesh: MeshData,
  nodeValues: number[],
  levels: number[],
): { x: (number | null)[]; y: (number | null)[] } {
  const x: (number | null)[] = [];
  const y: (number | null)[] = [];
  const edges: [number, number][] = [
    [0, 1],
    [1, 2],
    [2, 0],
  ];

  for (const level of levels) {
    for (const tri of mesh.triangles) {
      const crossings: [number, number][] = [];
      for (const [ei, ej] of edges) {
        const a = tri[ei];
        const b = tri[ej];
        const va = nodeValues[a];
        const vb = nodeValues[b];
        if (!Number.isFinite(va) || !Number.isFinite(vb)) continue;
        if ((va - level) * (vb - level) < 0) {
          const t = (level - va) / (vb - va);
          const [ax, ay] = mesh.node_xy_nm[a];
          const [bx, by] = mesh.node_xy_nm[b];
          crossings.push([ax + t * (bx - ax), ay + t * (by - ay)]);
        }
      }
      if (crossings.length >= 2) {
        x.push(crossings[0][0], crossings[1][0], null);
        y.push(-crossings[0][1], -crossings[1][1], null);
      }
    }
  }

  return { x, y };
}
