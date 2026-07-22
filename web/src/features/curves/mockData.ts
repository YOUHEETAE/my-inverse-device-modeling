import type { CurveData, CurveResponse, DeviceParameters } from "./types";

// Deterministic placeholder generator so the UI has something realistic to
// render before real API wiring is connected. Not physically accurate.
export function mockCurveResponse(params: DeviceParameters): CurveResponse {
  const L = Number(params.L);
  const scale = 200 / L;

  const idvdGrid = Array.from({ length: 31 }, (_, i) => (i / 30) * 3);
  const idvdBiases = [1, 1.5, 2, 2.5, 3];
  const idvd: CurveData = {
    kind: "idvd",
    grid: idvdGrid,
    fixed_biases: idvdBiases,
    currents: idvdBiases.map((vg) =>
      idvdGrid.map((vd) => scale * 0.4 * (vg - 0.4) * Math.tanh(vd * 1.5)),
    ),
  };

  const idvgGrid = Array.from({ length: 31 }, (_, i) => (i / 30) * 3);
  const idvgBiases = [0.05, 1.5];
  const idvg: CurveData = {
    kind: "idvg",
    grid: idvgGrid,
    fixed_biases: idvgBiases,
    currents: idvgBiases.map((vd) =>
      idvgGrid.map((vg) => scale * 0.05 * Math.max(0, vg - 0.4) ** 2 * (vd > 1 ? 3 : 1) + 1e-6),
    ),
  };

  return {
    idvd,
    idvg,
    electrical_parameters: {
      vth_low_v: 0.42,
      vth_high_v: 0.38,
      ion_ma_per_um: scale * 0.6,
      ioff_ma_per_um: 1.2e-4,
      ion_ioff_ratio: (scale * 0.6) / 1.2e-4,
      ss_mv_per_dec: 78,
      dibl_gm_v_per_v: 45,
      gm_max_ms_per_um: scale * 0.35,
      gds_ms_per_um: scale * 0.02,
      ron_kohm_um: 1 / (scale * 0.02),
      lambda_per_v: 0.03,
    },
    range_warning: "",
  };
}
