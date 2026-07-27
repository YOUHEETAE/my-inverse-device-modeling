import { useEffect, useRef } from "react";
import type { Data } from "plotly.js";
import Plotly from "plotly.js-dist-min";
import { Plot } from "@/lib/plot";
import { Card, CardContent } from "@/components/ui/card";
import type { FieldDisplay, FieldDisplayResponse, MeshData } from "../types";
import { applyNorm, formatFieldLabel, mapColormap } from "./colormap";
import { buildOverlayShapes2D, buildOverlayTraces3D, geometryMarkers } from "./structureOverlay";
import { SCENE_LAYOUT, buildMeshEdges, buildMeshTrace, elementToNode } from "./fieldChartUtils";

interface FieldChartProps {
  mesh: MeshData | null;
  toxNm: number;
  display: FieldDisplay;
  displayData: FieldDisplayResponse | null;
}

export function FieldChart({ mesh, toxNm, display, displayData }: FieldChartProps) {
  // mesh3d scenes sometimes compute their initial camera/aspect fit before the
  // container has settled to its final size, leaving the view stuck zoomed in
  // on a corner until the user drags. Forcing a resize shortly after mount (and
  // whenever the data driving a fresh trace changes) makes Plotly recompute the
  // fit against the real container size.
  const graphDivRef = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (!graphDivRef.current) return;
    const timer = setTimeout(() => {
      if (graphDivRef.current) Plotly.Plots.resize(graphDivRef.current);
    }, 50);
    return () => clearTimeout(timer);
  }, [display, displayData]);

  if (!mesh) {
    return (
      <Card className="flex h-full items-center justify-center">
        <p className="text-sm text-muted-foreground">No device selected</p>
      </Card>
    );
  }

  const marker = geometryMarkers(mesh, toxNm);

  if (display === "Mesh") {
    const { x, y } = buildMeshEdges(mesh);
    const trace: Data = {
      type: "scatter",
      mode: "lines",
      x,
      y,
      line: { color: "#3f3f46", width: 0.5 },
      hoverinfo: "skip",
    };
    const { shapes, annotations } = buildOverlayShapes2D(marker);
    return (
      <Card className="flex h-full flex-col">
        <CardContent className="flex-1">
          <Plot
            data={[trace]}
            layout={{
              paper_bgcolor: "transparent",
              plot_bgcolor: "#ffffff",
              margin: { t: 10, b: 30, l: 40, r: 10 },
              xaxis: { title: { text: "x (nm)" }, gridcolor: "#e4e4e7" },
              yaxis: { title: { text: "y (nm)" }, gridcolor: "#e4e4e7", scaleanchor: "x" },
              showlegend: false,
              shapes,
              annotations,
            }}
            config={{ displaylogo: false, responsive: true }}
            useResizeHandler
            style={{ width: "100%", height: "100%" }}
          />
        </CardContent>
      </Card>
    );
  }

  if (!displayData) {
    return (
      <Card className="flex h-full items-center justify-center">
        <p className="text-sm text-muted-foreground">Loading field data…</p>
      </Card>
    );
  }

  const nodeCount = mesh.node_xy_nm.length;
  const rawValues =
    displayData.domain === "node"
      ? displayData.values.map((v) => v ?? NaN)
      : elementToNode(displayData.values, mesh.triangles, nodeCount);

  const { values: intensity, cmin, cmax } = applyNorm(
    rawValues,
    displayData.norm_type,
    displayData.vmin,
    displayData.vmax,
    displayData.linthresh,
  );
  const { colorscale, reversescale } = mapColormap(displayData.cmap);
  // No colorbar here — it's shown once in the sidebar's ColorbarLegend instead
  // of being embedded in this plot.
  const meshTrace = buildMeshTrace(mesh, intensity, cmin, cmax, colorscale, reversescale, null);

  return (
    <Card className="flex h-full flex-col">
      <CardContent className="flex-1">
        <Plot
          data={[meshTrace, ...buildOverlayTraces3D(marker)]}
          layout={{
            paper_bgcolor: "transparent",
            margin: { t: 36, b: 10, l: 10, r: 10 },
            scene: SCENE_LAYOUT,
            title: { text: formatFieldLabel(displayData.title), font: { size: 12 } },
            showlegend: false,
          }}
          config={{ displaylogo: false, responsive: true }}
          useResizeHandler
          style={{ width: "100%", height: "100%" }}
          onInitialized={(_figure, graphDiv) => {
            graphDivRef.current = graphDiv;
          }}
          onUpdate={(_figure, graphDiv) => {
            graphDivRef.current = graphDiv;
          }}
        />
      </CardContent>
    </Card>
  );
}
