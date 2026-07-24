import type { Layout } from "plotly.js";

export const darkPlotLayout: Partial<Layout> = {
  paper_bgcolor: "transparent",
  plot_bgcolor: "transparent",
  font: { color: "#3f3f46", size: 11 },
  legend: {
    bgcolor: "transparent",
    font: { size: 10 },
  },
  xaxis: {
    gridcolor: "#e4e4e7",
    zerolinecolor: "#d4d4d8",
    linecolor: "#a1a1aa",
    tickfont: { size: 10 },
  },
  yaxis: {
    gridcolor: "#e4e4e7",
    zerolinecolor: "#d4d4d8",
    linecolor: "#a1a1aa",
    tickfont: { size: 10 },
  },
};

export const darkPlotConfig = { displaylogo: false, responsive: true };
