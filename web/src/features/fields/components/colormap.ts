// Maps the desktop app's matplotlib colormap names (from ai/shared/field_data.py's
// scalar_display) to Plotly-compatible equivalents. Plotly has no native "coolwarm"
// or "PiYG", so those get a close built-in substitute / a hand-built colorscale.
export function mapColormap(cmap: string): { colorscale: string | [number, string][]; reversescale: boolean } {
  switch (cmap) {
    case "plasma":
      return { colorscale: "Plasma", reversescale: false };
    case "inferno":
      return { colorscale: "Inferno", reversescale: false };
    case "magma":
      return { colorscale: "Magma", reversescale: false };
    case "Blues":
      return { colorscale: "Blues", reversescale: false };
    case "Reds":
      return { colorscale: "Reds", reversescale: false };
    case "RdBu_r":
      return { colorscale: "RdBu", reversescale: true };
    case "coolwarm":
      return { colorscale: "RdBu", reversescale: true };
    case "PiYG":
      return {
        colorscale: [
          [0, "#8e0152"],
          [0.25, "#de77ae"],
          [0.5, "#f7f7f7"],
          [0.75, "#7fbc41"],
          [1, "#276419"],
        ],
        reversescale: false,
      };
    default:
      return { colorscale: "Viridis", reversescale: false };
  }
}

const SUPERSCRIPT_DIGITS: Record<string, string> = {
  "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
  "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "-": "⁻",
};

// Backend labels (ai/shared/field_data.py) carry matplotlib LaTeX math text
// (e.g. "cm$^{-3}$") meant for matplotlib's renderer. Plotly doesn't interpret
// that syntax, so it shows up as literal "$^{-3}$" text — long enough that it
// wraps and distorts the colorbar's layout. Convert the `$^{n}$` exponents to
// compact unicode superscripts instead.
export function formatFieldLabel(text: string): string {
  return text.replace(/\$\^\{?(-?\d+)\}?\$/g, (_match, exponent: string) =>
    [...(exponent as string)].map((ch) => SUPERSCRIPT_DIGITS[ch] ?? ch).join(""),
  );
}

const LOG_EPSILON = 1e-300;

// Converts raw field values + the backend's chosen normalization into values/cmin/cmax
// that Plotly's linear color mapping can use directly (Plotly has no native log/symlog
// color axis, so log and symlog are pre-transformed here to a linear scale).
export function applyNorm(
  values: number[],
  normType: "linear" | "two_slope" | "log" | "symlog",
  vmin: number,
  vmax: number,
  linthresh: number | null,
): { values: number[]; cmin: number; cmax: number } {
  if (normType === "log") {
    const transform = (v: number) => Math.log10(Math.max(Math.abs(v), LOG_EPSILON));
    return { values: values.map(transform), cmin: Math.log10(Math.max(vmin, LOG_EPSILON)), cmax: Math.log10(Math.max(vmax, LOG_EPSILON)) };
  }
  if (normType === "symlog") {
    const t = linthresh ?? 1;
    const transform = (v: number) => Math.sign(v) * Math.log10(1 + Math.abs(v) / t);
    const bound = Math.log10(1 + vmax / t);
    return { values: values.map(transform), cmin: -bound, cmax: bound };
  }
  return { values, cmin: vmin, cmax: vmax };
}
