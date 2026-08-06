export interface PNOptions {
  dopings: number[];
  biases: number[];
}

export interface PNResult {
  x_um: number[];
  y_um: number[];
  triangles: [number, number, number][];
  net_doping: number[];
  potential: number[];
  electrons: number[];
  holes: number[];
  electric_field: number[];
  electric_field_x: number[];
  voltages: number[];
  currents: number[];
  selected_bias: number;
}

export const FIELD_OPTIONS = ["Net Doping", "Potential", "Electric Field", "Electrons", "Holes"] as const;
export type FieldOption = (typeof FIELD_OPTIONS)[number];

export const LOWER_PLOT_OPTIONS = [
  "Forward I–V",
  "Carrier Concentrations (line cut)",
  "Charge Density (line cut)",
  "Electric Field (line cut)",
  "Potential (line cut)",
  "Band Diagram (line cut)",
] as const;
export type LowerPlotOption = (typeof LOWER_PLOT_OPTIONS)[number];

export interface LongChannelOptions {
  gate_voltages: number[];
  drain_voltages: number[];
}

export interface LongChannelRegion {
  x_um: number[];
  y_um: number[];
  triangles: [number, number, number][];
  potential: number[];
  net_doping: number[] | null;
  electrons: number[] | null;
  holes: number[] | null;
}

export interface LongChannelResult {
  regions: Record<string, LongChannelRegion>;
  gate_voltages: number[];
  drain_currents: number[];
  idvg_drain_voltage: number;
  idvd_gate_voltages: number[];
  idvd_drain_voltages: number[];
  idvd_currents: number[][];
  selected_gate_voltage: number;
  selected_drain_voltage: number;
}

export const LONG_CHANNEL_FIELD_OPTIONS = ["Net Doping", "Potential", "Electrons", "Holes"] as const;
export type LongChannelFieldOption = (typeof LONG_CHANNEL_FIELD_OPTIONS)[number];
