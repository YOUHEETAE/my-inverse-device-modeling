import type { Data } from "plotly.js";
import { Plot } from "@/lib/plot";
import { mapColormap } from "./colormap";

interface ColorbarLegendProps {
  label: string;
  cmap: string;
  vmin: number;
  vmax: number;
}

export function ColorbarLegend({ label, cmap, vmin, vmax }: ColorbarLegendProps) {
  const { colorscale, reversescale } = mapColormap(cmap);
  const trace: Data = {
    type: "scatter",
    x: [null],
    y: [null],
    mode: "markers",
    marker: {
      color: [vmin, vmax],
      colorscale,
      reversescale,
      cmin: vmin,
      cmax: vmax,
      showscale: true,
      colorbar: {
        title: { text: label, side: "top", font: { size: 9 } },
        len: 0.9,
        thickness: 16,
        tickfont: { size: 9 },
        exponentformat: "e",
        x: 0.5,
        xanchor: "center",
      },
    },
    hoverinfo: "skip",
  } as unknown as Data;

  return (
    <Plot
      data={[trace]}
      layout={{
        paper_bgcolor: "transparent",
        plot_bgcolor: "transparent",
        margin: { t: 10, b: 10, l: 10, r: 10 },
        xaxis: { visible: false },
        yaxis: { visible: false },
        showlegend: false,
      }}
      config={{ displaylogo: false, responsive: true, staticPlot: true }}
      useResizeHandler
      style={{ width: "100%", height: "220px" }}
    />
  );
}
