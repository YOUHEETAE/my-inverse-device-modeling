import { useLayoutEffect, useRef, useState } from "react";
import type { Data } from "plotly.js";
import { Plot } from "@/lib/plot";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { FieldCompareResponse, FieldDisplay, MeshData } from "../types";
import { applyNorm, formatFieldLabel, mapColormap } from "./colormap";
import { computeContourSegments, contourLevels } from "./contours";
import { buildOverlayShapes2D, buildOverlayTraces3D, geometryMarkers } from "./structureOverlay";
import { buildMeshEdges, buildMeshTrace, computeSharedMeshScale, computeMeshAspectRatioForScale, elementToNode } from "./fieldChartUtils";
import { MeshScenePlot } from "./MeshScenePlot";

// gap-3 in Tailwind's default scale (0.75rem at the standard 16px root).
const GRID_GAP_PX = 12;

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
  const gridRef = useRef<HTMLDivElement | null>(null);
  const [cellAspect, setCellAspect] = useState<number | null>(null);
  const panelCount = compareData?.items.length ?? devices.length;

  useLayoutEffect(() => {
    const el = gridRef.current;
    if (!el || panelCount === 0) return;
    const measure = () => {
      const { width, height } = el.getBoundingClientRect();
      if (width > 0 && height > 0) {
        const cellWidth = (width - GRID_GAP_PX * (panelCount - 1)) / panelCount;
        setCellAspect(cellWidth / height);
      }
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, [panelCount]);

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
            // instance doesn't reliably refit its axes to the new width.
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

  // One scale shared across every panel (see computeSharedMeshScale), derived
  // from whichever compared device has the largest extent, so a physically
  // bigger device actually reads as bigger on screen instead of every panel
  // independently maximizing itself to the same on-screen footprint.
  const sharedScale =
    cellAspect != null ? computeSharedMeshScale(compareData.items.map((item) => item.mesh), cellAspect) : null;

  // Each device gets its own independent Plot (same single-scene fitting code
  // path as the single-device view, which is reliable) instead of one figure
  // with multiple domain-positioned scenes — the shared-figure approach drifted
  // out of alignment with its own panel titles once panels got narrow (3-4
  // devices). No colorbar here — it's shown once in the sidebar's
  // ColorbarLegend instead of taking width from a device panel.
  return (
    <div
      ref={gridRef}
      className="grid h-full gap-3"
      style={{ gridTemplateColumns: `repeat(${compareData.items.length}, 1fr)` }}
    >
      {sharedScale == null
        ? null
        : compareData.items.map((item, index) => {
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
            const { x: contourX, y: contourY } = computeContourSegments(
              item.mesh,
              intensity,
              contourLevels(cmin, cmax),
            );
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
              // See the Mesh branch above for why devices.length is part of the key.
              <Card key={`${item.label}-${compareData.items.length}`} className="flex flex-col">
                <CardContent className="flex-1">
                  <MeshScenePlot
                    title={`${item.label} · ${formatFieldLabel(compareData.title)}`}
                    mesh={item.mesh}
                    data={[meshTrace, contourTrace, ...buildOverlayTraces3D(marker)]}
                    aspectRatio={computeMeshAspectRatioForScale(item.mesh, sharedScale)}
                  />
                </CardContent>
              </Card>
            );
          })}
    </div>
  );
}
