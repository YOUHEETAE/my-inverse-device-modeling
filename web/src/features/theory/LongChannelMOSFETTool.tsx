import { useEffect, useMemo, useState } from "react";
import type { Data, Layout } from "plotly.js";
import { Plot } from "@/lib/plot";
import { darkPlotConfig, darkPlotLayout } from "@/lib/plotTheme";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { fetchLongChannelOptions, fetchLongChannelResult, getErrorMessage } from "./api";
import { LONG_CHANNEL_FIELD_OPTIONS, type LongChannelFieldOption, type LongChannelOptions, type LongChannelResult } from "./types";
import { buildIdVdTraces, buildIdVgTrace, buildLongChannelFieldTraces, nearestValue } from "./longChannelMath";

function regionCentroid(xUm: number[], yUm: number[]): [number, number] {
  const sum = (values: number[]) => values.reduce((a, b) => a + b, 0);
  return [sum(xUm) / xUm.length, sum(yUm) / yUm.length];
}

export function LongChannelMOSFETTool() {
  const [options, setOptions] = useState<LongChannelOptions | null>(null);
  const [gateVoltage, setGateVoltage] = useState("1");
  const [drainVoltage, setDrainVoltage] = useState("1");
  const [field, setField] = useState<LongChannelFieldOption>("Electrons");
  const [result, setResult] = useState<LongChannelResult | null>(null);
  const [status, setStatus] = useState("Ready");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchLongChannelOptions()
      .then((data) => setOptions(data))
      .catch((err) => setError(getErrorMessage(err)));
  }, []);

  async function load() {
    setLoading(true);
    setError(null);
    setStatus("Loading saved result…");
    try {
      const data = await fetchLongChannelResult(Number(gateVoltage), Number(drainVoltage));
      setResult(data);
      setStatus(`Complete — showing VG=${data.selected_gate_voltage.toFixed(2)} V, VD=${data.selected_drain_voltage.toFixed(2)} V`);
    } catch (err) {
      setError(getErrorMessage(err));
      setStatus("Load failed");
    } finally {
      setLoading(false);
    }
  }

  const fieldData = useMemo<Data[]>(() => {
    if (!result) return [];
    const { traces } = buildLongChannelFieldTraces(result.regions, field);

    const gate = result.regions.gate;
    const oxide = result.regions.oxide;
    const bulk = result.regions.bulk;
    const [gateX, gateY] = regionCentroid(gate.x_um, gate.y_um);
    const [oxideX, oxideY] = regionCentroid(oxide.x_um, oxide.y_um);
    const bulkXMin = Math.min(...bulk.x_um);
    const bulkXMax = Math.max(...bulk.x_um);
    const bulkYMin = Math.min(...bulk.y_um);
    const bulkYMax = Math.max(...bulk.y_um);
    const labels = {
      type: "scatter",
      mode: "text",
      x: [gateX, oxideX, bulkXMin + 0.12 * (bulkXMax - bulkXMin), bulkXMax - 0.12 * (bulkXMax - bulkXMin), (bulkXMin + bulkXMax) / 2],
      y: [gateY, oxideY, bulkYMin + 0.08 * (bulkYMax - bulkYMin), bulkYMin + 0.08 * (bulkYMax - bulkYMin), bulkYMin + 0.7 * (bulkYMax - bulkYMin)],
      text: ["Gate", "Oxide", "Source n+", "Drain n+", "p-type body"],
      textfont: { color: "white", size: 9 },
      hoverinfo: "skip",
      showlegend: false,
    } as unknown as Data;

    return [...traces, labels];
  }, [result, field]);

  const fieldLayout = useMemo<Partial<Layout>>(() => {
    if (!result) return {};
    const { shapes, label } = buildLongChannelFieldTraces(result.regions, field);
    const allY = [...result.regions.gate.y_um, ...result.regions.oxide.y_um, ...result.regions.bulk.y_um];
    const yMin = Math.min(...allY);
    const yMax = Math.max(...allY);
    return {
      paper_bgcolor: "transparent",
      margin: { t: 36, b: 30, l: 45, r: 10 },
      xaxis: { ...darkPlotLayout.xaxis, title: { text: "Lateral position x (µm)" } },
      // Gate/oxide sit at small (near-zero or negative) y, the bulk extends
      // to larger y — reversing the range puts the gate on top, matching the
      // desktop app's axis.set_ylim(0.35, -0.21).
      yaxis: { ...darkPlotLayout.yaxis, title: { text: "Depth y (µm)" }, range: [yMax, yMin] },
      shapes,
      title: { text: `${label} · VG=${result.selected_gate_voltage.toFixed(2)} V, VD=${result.selected_drain_voltage.toFixed(2)} V`, font: { size: 12 } },
      showlegend: false,
    };
  }, [result, field]);

  const idvgData = useMemo<Data[]>(() => (result ? [buildIdVgTrace(result)] : []), [result]);
  const idvgLayout = useMemo<Partial<Layout>>(() => {
    if (!result) return {};
    const nearestVg = nearestValue(result.gate_voltages, result.selected_gate_voltage);
    return {
      ...darkPlotLayout,
      title: { text: `Transfer characteristic ID–VG (VD=${result.idvg_drain_voltage.toFixed(2)} V)`, font: { size: 12 } },
      xaxis: { ...darkPlotLayout.xaxis, title: { text: "Gate voltage VG (V)" } },
      yaxis: { ...darkPlotLayout.yaxis, title: { text: "|Drain current| (A/cm)" }, type: "log" },
      margin: { t: 36, b: 40, l: 55, r: 10 },
      showlegend: false,
      shapes: [{ type: "line", x0: nearestVg, x1: nearestVg, y0: 0, y1: 1, yref: "paper", line: { color: "#a1a1aa", dash: "dash", width: 1 } }],
    } as Partial<Layout>;
  }, [result]);

  const idvdData = useMemo<Data[]>(() => (result ? buildIdVdTraces(result) : []), [result]);
  const idvdLayout = useMemo<Partial<Layout>>(() => {
    if (!result) return {};
    const nearestVd = nearestValue(result.idvd_drain_voltages, result.selected_drain_voltage);
    return {
      ...darkPlotLayout,
      title: { text: "Output characteristics ID–VD", font: { size: 12 } },
      xaxis: { ...darkPlotLayout.xaxis, title: { text: "Drain voltage VD (V)" } },
      yaxis: { ...darkPlotLayout.yaxis, title: { text: "|Drain current| (A/cm)" } },
      // Extra bottom margin + an explicit legend y below the default auto
      // position: with orientation "h" and no y set, Plotly places the
      // legend right where the x-axis title sits, so they render on top of
      // each other.
      margin: { t: 36, b: 78, l: 55, r: 10 },
      legend: { ...darkPlotLayout.legend, orientation: "h", x: 0.5, xanchor: "center", y: -0.32, yanchor: "top" },
      shapes: [{ type: "line", x0: nearestVd, x1: nearestVd, y0: 0, y1: 1, yref: "paper", line: { color: "#a1a1aa", dash: "dash", width: 1 } }],
    } as Partial<Layout>;
  }, [result]);

  return (
    <Card className="flex h-[820px] flex-col">
      <CardContent className="flex flex-1 flex-col gap-3 overflow-hidden">
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase text-on-surface-variant">Gate voltage VG (V)</label>
            <Select value={gateVoltage} onValueChange={(value) => setGateVoltage(value as string)}>
              <SelectTrigger size="sm" className="w-24 text-xs">
                <SelectValue>{gateVoltage}</SelectValue>
              </SelectTrigger>
              <SelectContent>
                {options?.gate_voltages.map((v) => (
                  <SelectItem key={v} value={String(v)}>
                    {String(v)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase text-on-surface-variant">Drain voltage VD (V)</label>
            <Select value={drainVoltage} onValueChange={(value) => setDrainVoltage(value as string)}>
              <SelectTrigger size="sm" className="w-24 text-xs">
                <SelectValue>{drainVoltage}</SelectValue>
              </SelectTrigger>
              <SelectContent>
                {options?.drain_voltages.map((v) => (
                  <SelectItem key={v} value={String(v)}>
                    {String(v)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button size="sm" onClick={load} disabled={loading || !options} className="text-xs">
            Load Saved Result
          </Button>

          <div className="ml-auto flex flex-col gap-1">
            <label className="text-[10px] uppercase text-on-surface-variant">Displayed field</label>
            <Select value={field} onValueChange={(v) => setField(v as LongChannelFieldOption)}>
              <SelectTrigger size="sm" className="w-44 text-xs">
                <SelectValue>{field}</SelectValue>
              </SelectTrigger>
              <SelectContent>
                {LONG_CHANNEL_FIELD_OPTIONS.map((option) => (
                  <SelectItem key={option} value={option}>
                    {option}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {error && <p className="text-[11px] text-destructive">{error}</p>}
        <p className="text-[11px] text-on-surface-variant">{status}</p>

        <div className="h-72 shrink-0">
          {fieldData.length > 0 ? (
            <Plot data={fieldData} layout={fieldLayout} config={darkPlotConfig} useResizeHandler style={{ width: "100%", height: "100%" }} />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              Load a saved result to display the 2D field map
            </div>
          )}
        </div>

        <div className="grid min-h-0 flex-1 grid-cols-2 gap-3">
          <div className="min-h-0">
            {idvgData.length > 0 && (
              <Plot data={idvgData} layout={idvgLayout} config={darkPlotConfig} useResizeHandler style={{ width: "100%", height: "100%" }} />
            )}
          </div>
          <div className="min-h-0">
            {idvdData.length > 0 && (
              <Plot data={idvdData} layout={idvdLayout} config={darkPlotConfig} useResizeHandler style={{ width: "100%", height: "100%" }} />
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
