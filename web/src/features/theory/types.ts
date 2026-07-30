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
