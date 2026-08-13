export interface DeviceParameters {
  L: string;
  T: string;
  B: string;
  SD: string;
  LDD: string;
}

export interface CurveData {
  kind: "idvd" | "idvg";
  grid: number[];
  fixed_biases: number[];
  currents: number[][];
}

export interface CurveResponse {
  idvd: CurveData;
  idvg: CurveData;
  electrical_parameters: Record<string, number>;
  range_warning: string;
}

export interface CurveEntry {
  id: number;
  label: string;
  visible: boolean;
  parameters: DeviceParameters;
  result: CurveResponse | null;
}

export interface CurveConfig extends DeviceParameters {
  label: string;
}

export interface PromptResponse {
  prompt: string;
}

export interface ExplainResponse {
  descriptions: string[];
  comparisons: string[];
  tradeoffs: string[];
  cautions: string[];
  provider: string;
  model: string;
  cached: boolean;
}

export const PARAMETER_OPTIONS: Record<keyof DeviceParameters, string[]> = {
  L: ["100", "120", "150", "170", "200", "250", "300", "400", "500", "700", "1000", "1300", "1600"],
  T: ["5", "7", "10", "12", "15", "20", "27", "35", "50"],
  B: ["5e15", "1e16", "5e16"],
  SD: ["1e19", "5e19", "1e20", "5e20"],
  LDD: ["1e17", "5e17", "1e18", "5e18"],
};

export const DEFAULT_PARAMETERS: DeviceParameters = {
  L: "200",
  T: "20",
  B: "1e16",
  SD: "1e20",
  LDD: "1e18",
};

export const ELECTRICAL_PARAMETERS: {
  key: string;
  label: string;
  unit: string;
  // Multiplier applied before display — matches the Tkinter reference
  // (frontend/app.py's ELECTRICAL_PARAMETERS tuple), which shows DIBL in
  // mV/V by scaling the API's raw V/V value by 1000 at display time rather
  // than converting it in the shared extraction backend. Every other row is
  // already in its display unit, hence 1.
  scale: number;
}[] = [
    { key: "vth_low_v", label: "Vth (Vd=0.05 V)", unit: "V", scale: 1 },
    { key: "vth_high_v", label: "Vth (Vd=1.5 V)", unit: "V", scale: 1 },
    { key: "ion_ma_per_um", label: "Ion", unit: "mA/µm", scale: 1 },
    { key: "ioff_ma_per_um", label: "Ioff", unit: "mA/µm", scale: 1 },
    { key: "ion_ioff_ratio", label: "Ion/Ioff", unit: "", scale: 1 },
    { key: "ss_mv_per_dec", label: "SS", unit: "mV/dec", scale: 1 },
    { key: "dibl_gm_v_per_v", label: "DIBL", unit: "mV/V", scale: 1000 },
    { key: "gm_max_ms_per_um", label: "gm max", unit: "mS/µm", scale: 1 },
    { key: "gds_ms_per_um", label: "gds", unit: "mS/µm", scale: 1 },
    { key: "ron_kohm_um", label: "Ron", unit: "kΩ·µm", scale: 1 },
    { key: "lambda_per_v", label: "λ (CLM)", unit: "1/V", scale: 1 },
  ];
