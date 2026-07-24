import type { Data, Layout } from "plotly.js";
import { Plot } from "@/lib/plot";
import { darkPlotConfig, darkPlotLayout } from "@/lib/plotTheme";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { CurveEntry } from "../types";

interface CurveChartProps {
  curves: CurveEntry[];
  combined: boolean;
  logScale: boolean;
}

const COLORS = ["#3b82f6", "#f87171", "#4ade80", "#facc15", "#a78bfa"];
// Matches the desktop app's plotting floor (min(EVALUATION_LOG_FLOOR_MA_PER_UM, 1e-15))
// so near-zero/negative currents don't get silently dropped by the log axis.
const LOG_FLOOR = 1e-15;

const SWEEP_LABEL: Record<"idvd" | "idvg", string> = { idvd: "Vd", idvg: "Vg" };
const FIXED_LABEL: Record<"idvd" | "idvg", string> = { idvd: "Vg", idvg: "Vd" };

function overlayTraces(curves: CurveEntry[], kind: "idvd" | "idvg", log: boolean) {
  const traces: Data[] = [];
  curves.forEach((curve, curveIndex) => {
    if (!curve.visible || !curve.result) return;
    const data = curve.result[kind];
    data.fixed_biases.forEach((bias, biasIndex) => {
      const y = log ? data.currents[biasIndex].map((value) => Math.max(Math.abs(value), LOG_FLOOR)) : data.currents[biasIndex];
      traces.push({
        x: data.grid,
        y,
        type: "scatter",
        mode: "lines",
        name: `${curve.label} · ${FIXED_LABEL[kind]}=${bias.toFixed(2)} V`,
        opacity: 1 - biasIndex * 0.15,
        line: { color: COLORS[curveIndex % COLORS.length] },
      });
    });
  });
  return traces;
}

function axisLayout(kind: "idvd" | "idvg", log: boolean, title: string): Partial<Layout> {
  return {
    ...darkPlotLayout,
    title: { text: title, font: { size: 11 } },
    xaxis: { ...darkPlotLayout.xaxis, title: { text: `${SWEEP_LABEL[kind]} (V)` } },
    yaxis: { ...darkPlotLayout.yaxis, title: { text: "Id (mA/µm)" }, type: log ? "log" : "linear" },
    autosize: true,
    margin: { t: 24, b: 35, l: 50, r: 10 },
  };
}

export function CurveChart({ curves, combined, logScale }: CurveChartProps) {
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
        {(["idvd", "idvg"] as const).map((kind) => (
          <Card key={kind} className="flex flex-col">
            <CardHeader>
              <CardTitle>{kind === "idvd" ? "IdVd Characteristics" : "IdVg Characteristics"}</CardTitle>
              <CardDescription>
                {kind === "idvd"
                  ? "Output characteristics — drain current vs. drain voltage"
                  : "Transfer characteristics — drain current vs. gate voltage"}
              </CardDescription>
            </CardHeader>
            <CardContent className="flex-1">
              <Plot
                data={overlayTraces(visible, kind, logScale)}
                layout={axisLayout(kind, logScale, `${kind.toUpperCase()} — ${logScale ? "log |Id|" : "linear"}`)}
                config={darkPlotConfig}
                useResizeHandler
                style={{ width: "100%", height: "100%" }}
              />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <Card className="flex h-full flex-col">
      <CardHeader>
        <CardTitle>Separated Bias Plots</CardTitle>
        <CardDescription>Each fixed bias shown as its own subplot</CardDescription>
      </CardHeader>
      <CardContent className="grid flex-1 grid-cols-4 gap-3 overflow-y-auto">
        {(["idvd", "idvg"] as const).flatMap((kind) => {
          const biases = visible[0]?.result?.[kind].fixed_biases ?? [];
          return biases.map((bias, biasIndex) => (
            <Plot
              key={`${kind}-${bias}`}
              data={visible
                .filter((c) => c.result)
                .map((curve, curveIndex) => {
                  const raw = curve.result![kind].currents[biasIndex];
                  return {
                    x: curve.result![kind].grid,
                    y: logScale ? raw.map((value) => Math.max(Math.abs(value), LOG_FLOOR)) : raw,
                    type: "scatter" as const,
                    mode: "lines" as const,
                    name: curve.label,
                    line: { color: COLORS[curveIndex % COLORS.length] },
                  };
                })}
              layout={{
                ...axisLayout(kind, logScale, `${kind.toUpperCase()} @ ${FIXED_LABEL[kind]}=${bias.toFixed(2)}V`),
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
