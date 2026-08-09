import type { Data } from "plotly.js";
import { Plot } from "@/lib/plot";
import { Card, CardContent } from "@/components/ui/card";
import type { FieldDisplay, FieldDisplayResponse, MeshData } from "../types";
import { applyNorm, formatFieldLabel, mapColormap } from "./colormap";
import { computeContourSegments, contourLevels } from "./contours";
import { buildOverlayShapes2D, buildOverlayTraces3D, geometryMarkers } from "./structureOverlay";
import { buildMeshEdges, buildMeshTrace, elementToNode } from "./fieldChartUtils";
import { MeshScenePlot } from "./MeshScenePlot";

interface FieldChartProps {
  mesh: MeshData | null;
  toxNm: number;
  display: FieldDisplay;
  displayData: FieldDisplayResponse | null;
}

export function FieldChart({ mesh, toxNm, display, displayData }: FieldChartProps) {
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

  // Thin, subtle black contour lines over the scalar surface — port of
  // field_rendering.py's axis.tricontour() overlay. Drawn at a z just above
  // the flat mesh3d surface (z=0) and below the structure overlay (z=0.05).
  const { x: contourX, y: contourY } = computeContourSegments(mesh, intensity, contourLevels(cmin, cmax));
  const contourTrace: Data = {
    type: "scatter3d",
    mode: "lines",
    x: contourX,
    y: contourY,
    z: contourX.map((v) => (v == null ? null : 0.02)),
    line: { color: "black", width: 1 },
    opacity: 0.28,
    hoverinfo: "skip",
    showlegend: false,
  } as unknown as Data;

  return (
    <Card className="flex h-full flex-col">
      <CardContent className="flex-1">
        <MeshScenePlot
          title={formatFieldLabel(displayData.title)}
          mesh={mesh}
          data={[meshTrace, contourTrace, ...buildOverlayTraces3D(marker)]}
        />
      </CardContent>
    </Card>
  );
}
