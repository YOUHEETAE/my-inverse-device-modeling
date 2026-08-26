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
  L: "500",
  T: "15",
  B: "1e16",
  SD: "1e20",
  LDD: "1e18",
};

/** 쓸 수 없는 입력값과, 그게 어느 칸인지. */
export interface ParameterProblem {
  fields: (keyof DeviceParameters)[];
  message: string;
}

/**
 * 이 입력값으로 예측을 보낼 수 있는지 본다.
 *
 * 서버도 같은 것을 막지만(predictor.py의 device_features) 거기까지 가면
 * 파이썬의 float() 오류가 그대로 화면에 올라온다 — "could not convert
 * string to float: ''". 어느 칸이 비었는지는 그 문장에 없다. 보내기 전에
 * 여기서 걸러, 고쳐야 할 칸의 이름을 대신 알려준다.
 *
 * 한 번에 한 종류만 말한다. 빈 칸과 음수를 함께 늘어놓으면 무엇부터
 * 고쳐야 할지가 흐려진다.
 */
export function findParameterProblem(values: DeviceParameters): ParameterProblem | null {
  const names = Object.keys(DEFAULT_PARAMETERS) as (keyof DeviceParameters)[];

  // 빈 칸을 먼저 본다 — Number("")는 NaN이 아니라 0이라, 순서를 바꾸면
  // 빈 칸이 "0보다 커야 합니다"로 잘못 불린다.
  const blank = names.filter((name) => values[name].trim() === "");
  if (blank.length > 0) {
    return { fields: blank, message: `비어 있는 파라미터가 있습니다 — ${blank.join(", ")}` };
  }

  const unreadable = names.filter((name) => !Number.isFinite(Number(values[name])));
  if (unreadable.length > 0) {
    return {
      fields: unreadable,
      message: `숫자로 읽을 수 없는 파라미터가 있습니다 — ${unreadable.join(", ")}. 1e16처럼 적어 주세요.`,
    };
  }

  const nonPositive = names.filter((name) => Number(values[name]) <= 0);
  if (nonPositive.length > 0) {
    return {
      fields: nonPositive,
      message: `0보다 큰 값이어야 합니다 — ${nonPositive.join(", ")}`,
    };
  }

  return null;
}

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
    // 바이어스 값 대신 low/high로 부른다. AI 답변도 같은 이름을 쓰므로
    // (iv_chat.py의 답변 프롬프트) 표와 설명을 오가며 옮겨 읽지 않아도 된다.
    { key: "vth_low_v", label: "Vth (low)", unit: "V", scale: 1 },
    { key: "vth_high_v", label: "Vth (high)", unit: "V", scale: 1 },
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
