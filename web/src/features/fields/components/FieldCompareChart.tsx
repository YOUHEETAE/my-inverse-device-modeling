import type { Data } from "plotly.js";
import { Plot } from "@/lib/plot";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { FieldCompareResponse, FieldDisplay, MeshData } from "../types";
import { applyNorm, formatFieldLabel, mapColormap } from "./colormap";
import { buildOverlayShapes2D, buildOverlayTraces3D, geometryMarkers } from "./structureOverlay";
import { SCENE_LAYOUT, buildMeshEdges, buildMeshTrace, elementToNode } from "./fieldChartUtils";

interface CompareDevice {
  label: string;
  mesh: MeshData;
  toxNm: number;
}

interface FieldCompareChartProps {
  devices: CompareDevice[];
  display: FieldDisplay;
  compareData: FieldCompareResponse | null;
}

export function FieldCompareChart({ devices, display, compareData }: FieldCompareChartProps) {
  if (devices.length === 0) {
    return (
      <Card className="flex h-full items-center justify-center">
        <p className="text-sm text-muted-foreground">No devices selected</p>
      </Card>
    );
  }

  if (display === "Mesh") {
    return (
      <div className="grid h-full gap-3" style={{ gridTemplateColumns: `repeat(${devices.length}, 1fr)` }}>
        {devices.map((device) => {
          const marker = geometryMarkers(device.mesh, device.toxNm);
          const { shapes, annotations } = buildOverlayShapes2D(marker);
          const { x, y } = buildMeshEdges(device.mesh);
          const trace: Data = {
            type: "scatter",
            mode: "lines",
            x,
            y,
            line: { color: "#3f3f46", width: 0.5 },
            hoverinfo: "skip",
          };
          return (
            // Key includes devices.length: when panel count changes, every
            // panel's width changes too, and a reused (not remounted) Plotly
            // instance doesn't reliably refit its camera/aspect to the new
            // width — remounting all panels on count change keeps this in
            // sync with the same "works after a full remount" behavior seen
            // when this used to be a manual view toggle.
            <Card key={`${device.label}-${devices.length}`} className="flex flex-col">
              <CardHeader>
                <CardTitle>{device.label}</CardTitle>
              </CardHeader>
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
        })}
      </div>
    );
  }

  if (!compareData) {
    return (
      <Card className="flex h-full items-center justify-center">
        <p className="text-sm text-muted-foreground">Loading field data…</p>
      </Card>
    );
  }

  const { colorscale, reversescale } = mapColormap(compareData.cmap);

  // Each device gets its own independent Plot (same single-scene fitting code
  // path as the single-device view, which is reliable) instead of one figure
  // with multiple domain-positioned scenes — the shared-figure approach drifted
  // out of alignment with its own panel titles once panels got narrow (3-4
  // devices). No colorbar here — it's shown once in the sidebar's
  // ColorbarLegend instead of taking width from a device panel.
  return (
    <div className="grid h-full gap-3" style={{ gridTemplateColumns: `repeat(${compareData.items.length}, 1fr)` }}>
      {compareData.items.map((item, index) => {
        const marker = geometryMarkers(item.mesh, devices[index]?.toxNm ?? 0);
        const nodeCount = item.mesh.node_xy_nm.length;
        const rawValues =
          compareData.domain === "node"
            ? item.values.map((v) => v ?? NaN)
            : elementToNode(item.values, item.mesh.triangles, nodeCount);
        const { values: intensity, cmin, cmax } = applyNorm(
          rawValues,
          compareData.norm_type,
          compareData.vmin,
          compareData.vmax,
          compareData.linthresh,
        );
        const meshTrace = buildMeshTrace(item.mesh, intensity, cmin, cmax, colorscale, reversescale, null);
        return (
          // See the Mesh branch above for why devices.length is part of the key.
          <Card key={`${item.label}-${compareData.items.length}`} className="flex flex-col">
            <CardContent className="flex-1">
              <Plot
                data={[meshTrace, ...buildOverlayTraces3D(marker)]}
                layout={{
                  paper_bgcolor: "transparent",
                  margin: { t: 36, b: 10, l: 10, r: 10 },
                  scene: SCENE_LAYOUT,
                  title: { text: `${item.label} · ${formatFieldLabel(compareData.title)}`, font: { size: 12 } },
                  showlegend: false,
                }}
                config={{ displaylogo: false, responsive: true }}
                useResizeHandler
                style={{ width: "100%", height: "100%" }}
              />
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
