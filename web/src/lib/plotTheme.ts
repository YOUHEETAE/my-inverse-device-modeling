import type { Layout } from "plotly.js";

// Plotly defaults to a white paper/plot background regardless of page theme,
// so it renders as a bright box on a dark UI unless overridden explicitly.
export const darkPlotLayout: Partial<Layout> = {
  paper_bgcolor: "transparent",
  plot_bgcolor: "transparent",
  font: { color: "#a1a1aa", size: 11 },
  xaxis: { gridcolor: "#27272a", zerolinecolor: "#3f3f46", linecolor: "#3f3f46" },
  yaxis: { gridcolor: "#27272a", zerolinecolor: "#3f3f46", linecolor: "#3f3f46" },
};

export const darkPlotConfig = { displaylogo: false, responsive: true };
