import type { Data } from "plotly.js";
import { Plot } from "@/lib/plot";
import { darkPlotConfig, darkPlotLayout } from "@/lib/plotTheme";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { CurveEntry } from "../types";

interface CurveChartProps {
  curves: CurveEntry[];
  combined: boolean;
  onToggleCombined: () => void;
}

const COLORS = ["#3b82f6", "#f87171", "#4ade80", "#facc15", "#a78bfa"];

function overlayTraces(curves: CurveEntry[], kind: "idvd" | "idvg") {
  const traces: Data[] = [];
  curves.forEach((curve, curveIndex) => {
    if (!curve.visible || !curve.result) return;
    const data = curve.result[kind];
    data.fixed_biases.forEach((bias, biasIndex) => {
      traces.push({
        x: data.grid,
        y: data.currents[biasIndex],
        type: "scatter",
        mode: "lines",
        name: `${curve.label} · Vg=${bias.toFixed(2)} V`,
        opacity: 1 - biasIndex * 0.15,
        line: { color: COLORS[curveIndex % COLORS.length] },
      });
    });
  });
  return traces;
}

export function CurveChart({ curves, combined, onToggleCombined }: CurveChartProps) {
  const visible = curves.filter((c) => c.visible && c.result);

  if (visible.length === 0) {
    return (
      <Card className="flex h-full items-center justify-center">
        <p className="text-sm text-muted-foreground">No curves selected</p>
      </Card>
    );
  }

  if (combined) {
    return (
      <div className="grid h-full grid-cols-2 gap-4">
        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle>IdVd Characteristics</CardTitle>
            <CardDescription>Output characteristics — drain current vs. drain voltage</CardDescription>
            <CardAction>
              <Button size="sm" variant="outline" className="text-xs uppercase" onClick={onToggleCombined}>
                Separate Biases
              </Button>
            </CardAction>
          </CardHeader>
          <CardContent className="flex-1">
            <Plot
              data={overlayTraces(visible, "idvd")}
              layout={{
                ...darkPlotLayout,
                autosize: true,
                margin: { t: 10, b: 10, l: 10, r: 10 },
              }}
              config={darkPlotConfig}
              useResizeHandler
              style={{ width: "100%", height: "100%" }}
            />
          </CardContent>
        </Card>
        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle>IdVg Characteristics</CardTitle>
            <CardDescription>Transfer characteristics — log-scale drain current vs. gate voltage</CardDescription>
          </CardHeader>
          <CardContent className="flex-1">
            <Plot
              data={overlayTraces(visible, "idvg")}
              layout={{
                ...darkPlotLayout,
                yaxis: { ...darkPlotLayout.yaxis, type: "log" },
                autosize: true,
                margin: { t: 10, b: 10, l: 10, r: 10 },
              }}
              config={darkPlotConfig}
              useResizeHandler
              style={{ width: "100%", height: "100%" }}
            />
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <Card className="flex h-full flex-col">
      <CardHeader>
        <CardTitle>Separated Bias Plots</CardTitle>
        <CardDescription>Each fixed bias shown as its own subplot</CardDescription>
        <CardAction>
          <Button size="sm" variant="outline" className="text-xs uppercase" onClick={onToggleCombined}>
            Combine Biases
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="grid flex-1 grid-cols-4 grid-rows-2 gap-3 overflow-y-auto">
        {(["idvd", "idvg"] as const).flatMap((kind) => {
          const biases = visible[0]?.result?.[kind].fixed_biases ?? [];
          return biases.map((bias, biasIndex) => (
            <Plot
              key={`${kind}-${bias}`}
              data={visible
                .filter((c) => c.result)
                .map((curve, curveIndex) => ({
                  x: curve.result![kind].grid,
                  y: curve.result![kind].currents[biasIndex],
                  type: "scatter" as const,
                  mode: "lines" as const,
                  name: curve.label,
                  line: { color: COLORS[curveIndex % COLORS.length] },
                }))}
              layout={{
                ...darkPlotLayout,
                title: { text: `${kind.toUpperCase()} @ ${bias.toFixed(2)}V`, font: { size: 11, color: "#71717a" } },
                autosize: true,
                margin: { t: 24, b: 10, l: 10, r: 10 },
                showlegend: false,
              }}
              config={darkPlotConfig}
              useResizeHandler
              style={{ width: "100%", height: "100%" }}
            />
          ));
        })}
      </CardContent>
    </Card>
  );
}
