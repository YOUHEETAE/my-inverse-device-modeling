import type { DeviceParameters } from "../curves/types";

export type { DeviceParameters } from "../curves/types";
export { PARAMETER_OPTIONS, DEFAULT_PARAMETERS } from "../curves/types";

export const FIELD_DISPLAYS = [
  "Mesh",
  "Abs net doping",
  "Net doping",
  "Potential",
  "Electric field",
  "Electron density",
  "Hole density",
  "Electron current density",
  "Hole current density",
  "Total current density",
  "SRH recombination",
] as const;

export type FieldDisplay = (typeof FIELD_DISPLAYS)[number];

// Mirrors the desktop app's FIELD_EXPLANATION_EXCLUDED (frontend/visualization/
// explanation_panel.py) — these displays don't carry enough distinct signal for
// the LLM explanation payload (backend/explanation/field_analyzer.py rejects them
// with a ValueError), so block them client-side instead of round-tripping a 400.
export const FIELD_EXPLANATION_EXCLUDED: ReadonlySet<FieldDisplay> = new Set(["Mesh", "Abs net doping", "Net doping"]);

export const SCALE_MODES = ["Auto", "Linear", "Log magnitude", "SymLog"] as const;
export type ScaleMode = (typeof SCALE_MODES)[number];

export const RANGE_MODES = ["Robust 1-99%", "Full range"] as const;
export type RangeMode = (typeof RANGE_MODES)[number];

export interface MeshData {
  node_xy_nm: [number, number][];
  node_region: number[];
  triangles: [number, number, number][];
  element_centroid_xy_nm: [number, number][];
  element_region: number[];
}

export interface FieldResponse {
  mesh: MeshData;
  net_doping: number[];
  node_fields: Record<string, number[]>;
  element_fields: Record<string, number[]>;
  range_warning: string;
}

export interface FieldDisplayResponse {
  domain: "node" | "element";
  values: (number | null)[];
  title: string;
  label: string;
  norm_type: "linear" | "two_slope" | "log" | "symlog";
  vmin: number;
  vmax: number;
  linthresh: number | null;
  mode_label: string;
  cmap: string;
}

export interface DeviceEntry {
  id: number;
  label: string;
  visible: boolean;
  parameters: DeviceParameters;
  mesh: FieldResponse | null;
}

export interface FieldConfig extends DeviceParameters {
  label: string;
}

export interface FieldCompareItem {
  label: string;
  mesh: MeshData;
  values: (number | null)[];
}

export interface FieldCompareResponse {
  domain: "node" | "element";
  title: string;
  label: string;
  norm_type: "linear" | "two_slope" | "log" | "symlog";
  vmin: number;
  vmax: number;
  linthresh: number | null;
  mode_label: string;
  cmap: string;
  items: FieldCompareItem[];
}
