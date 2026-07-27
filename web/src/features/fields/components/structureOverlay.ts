import type { Data, Layout } from "plotly.js";
import type { MeshData } from "../types";

// Port of geometry_markers() in ai/shared/field_data.py — same region codes
// (0 = bulk, 2 = gate) and the same fixed spacer/contact-gap constants.
export interface GeometryMarkers {
  bulkLeft: number;
  bulkRight: number;
  surface: number;
  body: number;
  gateLeft: number;
  gateRight: number;
  gateTop: number;
  oxideTop: number;
  spacerLeft: number;
  spacerRight: number;
  sourceContactRight: number;
  drainContactLeft: number;
  diffusion: number;
}

function minMax(values: number[]): [number, number] {
  let min = Infinity;
  let max = -Infinity;
  for (const value of values) {
    if (value < min) min = value;
    if (value > max) max = value;
  }
  return [min, max];
}

export function geometryMarkers(mesh: MeshData, toxNm: number): GeometryMarkers {
  const bulkX: number[] = [];
  const bulkY: number[] = [];
  const gateX: number[] = [];
  const gateY: number[] = [];
  mesh.node_xy_nm.forEach(([x, y], index) => {
    const region = mesh.node_region[index];
    if (region === 0) {
      bulkX.push(x);
      bulkY.push(y);
    } else if (region === 2) {
      gateX.push(x);
      gateY.push(y);
    }
  });
  const [bulkLeft, bulkRight] = minMax(bulkX);
  const [surface, body] = minMax(bulkY);
  const [gateLeft, gateRight] = minMax(gateX);
  const [gateTop] = minMax(gateY);
  const spacerWidth = 50.0;
  const contactGap = 50.0;
  const spacerLeft = gateLeft - spacerWidth;
  const spacerRight = gateRight + spacerWidth;
  return {
    bulkLeft,
    bulkRight,
    surface,
    body,
    gateLeft,
    gateRight,
    gateTop,
    oxideTop: -toxNm,
    spacerLeft,
    spacerRight,
    sourceContactRight: spacerLeft - contactGap,
    drainContactLeft: spacerRight + contactGap,
    diffusion: Math.min(surface + 50.0, body),
  };
}

const CONTACTS: { x0: keyof GeometryMarkers; x1: keyof GeometryMarkers; y: keyof GeometryMarkers; label: string; color: string; above: boolean }[] = [
  { x0: "bulkLeft", x1: "sourceContactRight", y: "surface", label: "source contact", color: "#265d9b", above: false },
  { x0: "drainContactLeft", x1: "bulkRight", y: "surface", label: "drain contact", color: "#265d9b", above: false },
  { x0: "gateLeft", x1: "gateRight", y: "gateTop", label: "gate contact", color: "#7a4a19", above: false },
  { x0: "bulkLeft", x1: "bulkRight", y: "body", label: "body contact", color: "#2c6b2f", above: true },
];

export function buildOverlayShapes2D(marker: GeometryMarkers): { shapes: NonNullable<Layout["shapes"]>; annotations: NonNullable<Layout["annotations"]> } {
  const rect = (x0: number, x1: number, y0: number, y1: number, dash: "solid" | "dash" | "dot"): NonNullable<Layout["shapes"]>[number] => ({
    type: "rect",
    x0,
    x1,
    y0: -y0,
    y1: -y1,
    line: { color: "black", width: dash === "dot" ? 0.8 : 1.1, dash },
    fillcolor: "rgba(0,0,0,0)",
  });
  const line = (x0: number, x1: number, y0: number, y1: number, dash: "solid" | "dash" | "dot", width = 1): NonNullable<Layout["shapes"]>[number] => ({
    type: "line",
    x0,
    x1,
    y0: -y0,
    y1: -y1,
    line: { color: "black", width, dash },
  });

  const shapes: NonNullable<Layout["shapes"]> = [
    rect(marker.gateLeft, marker.gateRight, marker.gateTop, marker.oxideTop, "solid"),
    rect(marker.gateLeft, marker.gateRight, marker.oxideTop, marker.surface, "dash"),
    rect(marker.spacerLeft, marker.gateLeft, marker.gateTop, marker.surface, "dot"),
    rect(marker.gateRight, marker.spacerRight, marker.gateTop, marker.surface, "dot"),
    line(marker.bulkLeft, marker.bulkRight, marker.surface, marker.surface, "solid"),
    line(marker.bulkLeft, marker.bulkRight, marker.diffusion, marker.diffusion, "dot"),
    line(marker.gateLeft, marker.gateLeft, marker.gateTop, marker.body, "dash"),
    line(marker.gateRight, marker.gateRight, marker.gateTop, marker.body, "dash"),
    line(marker.spacerLeft, marker.spacerLeft, marker.gateTop, marker.surface, "dot", 0.8),
    line(marker.spacerRight, marker.spacerRight, marker.gateTop, marker.surface, "dot", 0.8),
    ...CONTACTS.map(({ x0, x1, y, color }) => ({
      ...line(marker[x0], marker[x1], marker[y], marker[y], "solid", 5),
      line: { color, width: 5 },
    })),
  ];

  const annotations: NonNullable<Layout["annotations"]> = CONTACTS.map(({ x0, x1, y, label, above }) => ({
    x: (marker[x0] + marker[x1]) / 2,
    y: -marker[y],
    text: label,
    showarrow: false,
    font: { size: 9, color: "black" },
    yshift: above ? 12 : -12,
    bgcolor: "rgba(255,255,255,0.75)",
  }));

  return { shapes, annotations };
}

export function buildOverlayTraces3D(marker: GeometryMarkers): Data[] {
  const z = 0.05;
  const rectTrace = (x0: number, x1: number, y0: number, y1: number, dash: "solid" | "dash" | "dot"): Data =>
    ({
      type: "scatter3d",
      mode: "lines",
      x: [x0, x1, x1, x0, x0],
      y: [-y0, -y0, -y1, -y1, -y0],
      z: [z, z, z, z, z],
      line: { color: "black", width: dash === "dot" ? 2 : 3, dash },
      hoverinfo: "skip",
      showlegend: false,
    }) as unknown as Data;
  const lineTrace = (x0: number, x1: number, y0: number, y1: number, dash: "solid" | "dash" | "dot", width = 3): Data =>
    ({
      type: "scatter3d",
      mode: "lines",
      x: [x0, x1],
      y: [-y0, -y1],
      z: [z, z],
      line: { color: "black", width, dash },
      hoverinfo: "skip",
      showlegend: false,
    }) as unknown as Data;

  const traces: Data[] = [
    rectTrace(marker.gateLeft, marker.gateRight, marker.gateTop, marker.oxideTop, "solid"),
    rectTrace(marker.gateLeft, marker.gateRight, marker.oxideTop, marker.surface, "dash"),
    rectTrace(marker.spacerLeft, marker.gateLeft, marker.gateTop, marker.surface, "dot"),
    rectTrace(marker.gateRight, marker.spacerRight, marker.gateTop, marker.surface, "dot"),
    lineTrace(marker.bulkLeft, marker.bulkRight, marker.surface, marker.surface, "solid"),
    lineTrace(marker.bulkLeft, marker.bulkRight, marker.diffusion, marker.diffusion, "dot"),
    lineTrace(marker.gateLeft, marker.gateLeft, marker.gateTop, marker.body, "dash"),
    lineTrace(marker.gateRight, marker.gateRight, marker.gateTop, marker.body, "dash"),
    lineTrace(marker.spacerLeft, marker.spacerLeft, marker.gateTop, marker.surface, "dot", 2),
    lineTrace(marker.spacerRight, marker.spacerRight, marker.gateTop, marker.surface, "dot", 2),
  ];

  CONTACTS.forEach(({ x0, x1, y, label, color }) => {
    traces.push({
      type: "scatter3d",
      mode: "lines",
      x: [marker[x0], marker[x1]],
      y: [-marker[y], -marker[y]],
      z: [z, z],
      line: { color, width: 8 },
      hoverinfo: "skip",
      showlegend: false,
    } as unknown as Data);
    traces.push({
      type: "scatter3d",
      mode: "text",
      x: [(marker[x0] + marker[x1]) / 2],
      y: [-marker[y]],
      z: [z + 0.03],
      text: [label],
      textfont: { size: 9, color: "black" },
      hoverinfo: "skip",
      showlegend: false,
    } as unknown as Data);
  });

  return traces;
}
