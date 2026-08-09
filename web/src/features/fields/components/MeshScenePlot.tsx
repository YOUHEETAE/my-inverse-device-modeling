import { useLayoutEffect, useRef, useState } from "react";
import type { Data, Layout } from "plotly.js";
import { Plot } from "@/lib/plot";
import type { MeshData } from "../types";
import { SCENE_LAYOUT, computeMeshAspectRatio, computeMeshSceneRange } from "./fieldChartUtils";

interface MeshScenePlotProps {
  mesh: MeshData;
  data: Data[];
  title?: string;
  // Compare view (FieldCompareChart) computes one aspectratio shared across
  // all panels (see computeSharedMeshScale) so devices of different physical
  // size read at a consistent scale, and passes it in here instead of letting
  // this component maximize itself independently.
  aspectRatio?: { x: number; y: number; z: number };
}

// Shared by the single-device (FieldChart) and compare (FieldCompareChart)
// views. The Plot is not created until a container size is known — either
// measured here via ResizeObserver, or supplied by the caller as `aspectRatio`
// — because aspectratio must be correct on the scene's first render: for an
// orthographic camera, aspectratio is what determines how much of the scene
// is visible, and changing it after the fact (relayout/resize calls) does not
// reliably re-fit an already-rendered scene.
export function MeshScenePlot({ mesh, data, title, aspectRatio }: MeshScenePlotProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [containerAspect, setContainerAspect] = useState<number | null>(null);

  useLayoutEffect(() => {
    if (aspectRatio) return;
    const el = containerRef.current;
    if (!el) return;
    const measure = () => {
      const { width, height } = el.getBoundingClientRect();
      if (width > 0 && height > 0) setContainerAspect(width / height);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, [aspectRatio]);

  const { x: xRange, y: yRange } = computeMeshSceneRange(mesh);
  const resolvedAspectRatio = aspectRatio ?? (containerAspect != null ? computeMeshAspectRatio(mesh, containerAspect) : null);
  const scene = resolvedAspectRatio
    ? ({
        ...SCENE_LAYOUT,
        xaxis: { ...(SCENE_LAYOUT as { xaxis?: object }).xaxis, range: xRange },
        yaxis: { ...(SCENE_LAYOUT as { yaxis?: object }).yaxis, range: yRange },
        aspectmode: "manual",
        aspectratio: resolvedAspectRatio,
      } as unknown as Partial<Layout["scene"]>)
    : null;

  return (
    <div ref={containerRef} className="h-full w-full">
      {scene && (
        <Plot
          data={data}
          layout={{
            paper_bgcolor: "transparent",
            margin: { t: title ? 36 : 10, b: 10, l: 10, r: 10 },
            scene,
            title: title ? { text: title, font: { size: 12 } } : undefined,
            showlegend: false,
          }}
          config={{ displaylogo: false, responsive: true }}
          useResizeHandler
          style={{ width: "100%", height: "100%" }}
        />
      )}
    </div>
  );
}
