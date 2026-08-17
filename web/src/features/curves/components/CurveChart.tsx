import { useState } from "react";
import type { Data, Layout } from "plotly.js";
import { Plot } from "@/lib/plot";
import { darkPlotConfig, darkPlotLayout } from "@/lib/plotTheme";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
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
        // The highest fixed bias is the device's main curve; lower biases
        // for the same device (same color) are dashed instead, so two
        // devices' overlapping bias families stay distinguishable at a
        // glance instead of relying on opacity alone.
        line: {
          color: COLORS[curveIndex % COLORS.length],
          dash: biasIndex === data.fixed_biases.length - 1 ? "solid" : "dash",
        },
      } as Data);
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

// Each graph gets its own toggle instead of one global switch flipping every
// graph at once — e.g. IdVd can stay linear while IdVg is checked in log.
function LogScaleToggle({ log, onToggle, className }: { log: boolean; onToggle: () => void; className?: string }) {
  return (
    <Button size="sm" variant="outline" className={cn("h-6 shrink-0 px-2 text-[10px] uppercase", className)} onClick={onToggle}>
      {log ? "Linear" : "Log"}
    </Button>
  );
}

export function CurveChart({ curves, combined }: CurveChartProps) {
  const visible = curves.filter((c) => c.visible && c.result);
  const [logByKey, setLogByKey] = useState<Record<string, boolean>>({});
  const isLog = (key: string) => logByKey[key] ?? false;
  const toggleLog = (key: string) => setLogByKey((prev) => ({ ...prev, [key]: !prev[key] }));

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
        {(["idvd", "idvg"] as const).map((kind) => {
          const log = isLog(kind);
          return (
            <Card key={kind} className="flex flex-col">
              <CardHeader className="flex flex-row items-start justify-between gap-2">
                <div>
                  <CardTitle>{kind === "idvd" ? "IdVd Characteristics" : "IdVg Characteristics"}</CardTitle>
                  <CardDescription>
                    {kind === "idvd"
                      ? "Output characteristics — drain current vs. drain voltage"
                      : "Transfer characteristics — drain current vs. gate voltage"}
                  </CardDescription>
                </div>
                <LogScaleToggle log={log} onToggle={() => toggleLog(kind)} />
              </CardHeader>
              <CardContent className="flex-1">
                <Plot
                  data={overlayTraces(visible, kind, log)}
                  layout={axisLayout(kind, log, `${kind.toUpperCase()} — ${log ? "log |Id|" : "linear"}`)}
                  config={darkPlotConfig}
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

  return (
    <Card className="flex h-full flex-col">
      <CardHeader>
        <CardTitle>Separated Bias Plots</CardTitle>
        <CardDescription>Each fixed bias shown as its own subplot</CardDescription>
      </CardHeader>
      <CardContent className="grid flex-1 grid-cols-4 gap-3 overflow-y-auto">
        {(["idvd", "idvg"] as const).flatMap((kind) => {
          const biases = visible[0]?.result?.[kind].fixed_biases ?? [];
          return biases.map((bias, biasIndex) => {
            const key = `${kind}-${bias.toFixed(2)}`;
            const log = isLog(key);
            return (
              <div key={key} className="relative flex flex-col">
                <LogScaleToggle log={log} onToggle={() => toggleLog(key)} className="absolute right-1 top-1 z-10" />
                <Plot
                  data={visible
                    .filter((c) => c.result)
                    .map((curve, curveIndex) => {
                      const raw = curve.result![kind].currents[biasIndex];
                      return {
                        x: curve.result![kind].grid,
                        y: log ? raw.map((value) => Math.max(Math.abs(value), LOG_FLOOR)) : raw,
                        type: "scatter" as const,
                        mode: "lines" as const,
                        name: curve.label,
                        line: { color: COLORS[curveIndex % COLORS.length] },
                      };
                    })}
                  layout={{
                    ...axisLayout(kind, log, `${kind.toUpperCase()} @ ${FIXED_LABEL[kind]}=${bias.toFixed(2)}V`),
                    showlegend: false,
                  }}
                  config={darkPlotConfig}
                  useResizeHandler
                  style={{ width: "100%", height: "100%" }}
                />
              </div>
            );
          });
        })}
      </CardContent>
    </Card>
  );
}
