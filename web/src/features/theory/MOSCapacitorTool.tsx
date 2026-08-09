import { useEffect, useMemo, useState } from "react";
import type { Data, Layout } from "plotly.js";
import { Plot } from "@/lib/plot";
import { darkPlotConfig, darkPlotLayout } from "@/lib/plotTheme";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { fetchMOSCapOptions, fetchMOSCapResult, getErrorMessage } from "./api";
import type { MOSCapOptions, MOSCapResult } from "./types";
import { buildBandDiagramTraces, buildCarrierTraces, buildChargeDensityTrace, buildPotentialTraces, depthLimit } from "./mosCapacitorMath";

function formatDoping(value: number): string {
  return value.toExponential(0).replace("+", "");
}

export function MOSCapacitorTool() {
  const [options, setOptions] = useState<MOSCapOptions | null>(null);
  const [acceptorDoping, setAcceptorDoping] = useState("1e17");
  const [oxideThickness, setOxideThickness] = useState("10");
  const [gateVoltage, setGateVoltage] = useState("1");
  const [result, setResult] = useState<MOSCapResult | null>(null);
  const [status, setStatus] = useState("Ready");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchMOSCapOptions()
      .then((data) => setOptions(data))
      .catch((err) => setError(getErrorMessage(err)));
  }, []);

  async function load() {
    setLoading(true);
    setError(null);
    setStatus("Loading saved result…");
    try {
      const data = await fetchMOSCapResult(Number(acceptorDoping), Number(oxideThickness), Number(gateVoltage));
      setResult(data);
      setStatus(`Complete — ${data.regime} at NA=${formatDoping(data.acceptor_doping)}, tox=${data.oxide_thickness_nm}nm, VG=${data.gate_voltage.toFixed(2)} V`);
    } catch (err) {
      setError(getErrorMessage(err));
      setStatus("Load failed");
    } finally {
      setLoading(false);
    }
  }

  const potentialData = useMemo<Data[]>(() => (result ? buildPotentialTraces(result) : []), [result]);
  const potentialLayout = useMemo<Partial<Layout>>(
    () => ({
      ...darkPlotLayout,
      title: { text: "Potential across Oxide / Silicon", font: { size: 12 } },
      xaxis: { ...darkPlotLayout.xaxis, title: { text: "Position from Si surface (nm)" } },
      yaxis: { ...darkPlotLayout.yaxis, title: { text: "Potential (V)" } },
      margin: { t: 36, b: 40, l: 55, r: 10 },
      shapes: [{ type: "line", x0: 0, x1: 0, y0: 0, y1: 1, yref: "paper", line: { color: "#333333", dash: "dot", width: 1 } }],
    }),
    [],
  );

  const carrierData = useMemo<Data[]>(() => (result ? buildCarrierTraces(result) : []), [result]);
  const carrierLayout = useMemo<Partial<Layout>>(() => {
    if (!result) return {};
    return {
      ...darkPlotLayout,
      title: { text: `Carrier Distribution — ${result.regime}`, font: { size: 12 } },
      xaxis: { ...darkPlotLayout.xaxis, title: { text: "Depth into Silicon (nm)" }, range: [0, depthLimit(result)] },
      yaxis: { ...darkPlotLayout.yaxis, title: { text: "Concentration (cm⁻³)" }, type: "log" },
      margin: { t: 36, b: 40, l: 60, r: 10 },
    };
  }, [result]);

  const chargeData = useMemo<Data[]>(() => (result ? buildChargeDensityTrace(result) : []), [result]);
  const chargeLayout = useMemo<Partial<Layout>>(() => {
    if (!result) return {};
    return {
      ...darkPlotLayout,
      title: { text: "Space Charge Density", font: { size: 12 } },
      xaxis: { ...darkPlotLayout.xaxis, title: { text: "Depth into Silicon (nm)" }, range: [0, depthLimit(result)] },
      yaxis: { ...darkPlotLayout.yaxis, title: { text: "ρ (C/cm³)" } },
      margin: { t: 36, b: 40, l: 60, r: 10 },
      showlegend: false,
      shapes: [{ type: "line", x0: 0, x1: 1, xref: "paper", y0: 0, y1: 0, line: { color: "#333333", width: 1 } }],
    };
  }, [result]);

  const bandData = useMemo<Data[]>(() => (result ? buildBandDiagramTraces(result) : []), [result]);
  const bandLayout = useMemo<Partial<Layout>>(() => {
    if (!result) return {};
    return {
      ...darkPlotLayout,
      title: { text: "Silicon Energy Band", font: { size: 12 } },
      xaxis: { ...darkPlotLayout.xaxis, title: { text: "Depth into Silicon (nm)" }, range: [0, depthLimit(result)] },
      yaxis: { ...darkPlotLayout.yaxis, title: { text: "Relative energy (eV)" } },
      margin: { t: 36, b: 60, l: 55, r: 10 },
      legend: { ...darkPlotLayout.legend, orientation: "h", x: 0.5, xanchor: "center", y: -0.28, yanchor: "top" },
    };
  }, [result]);

  return (
    <Card className="flex h-[820px] flex-col">
      <CardContent className="flex flex-1 flex-col gap-3 overflow-hidden">
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase text-on-surface-variant">Acceptor NA (cm⁻³)</label>
            <Select value={acceptorDoping} onValueChange={(value) => setAcceptorDoping(value as string)}>
              <SelectTrigger size="sm" className="w-24 text-xs">
                <SelectValue>{formatDoping(Number(acceptorDoping))}</SelectValue>
              </SelectTrigger>
              <SelectContent>
                {options?.acceptor_dopings.map((v) => (
                  <SelectItem key={v} value={String(v)}>
                    {formatDoping(v)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase text-on-surface-variant">Oxide thickness tox (nm)</label>
            <Select value={oxideThickness} onValueChange={(value) => setOxideThickness(value as string)}>
              <SelectTrigger size="sm" className="w-24 text-xs">
                <SelectValue>{oxideThickness}</SelectValue>
              </SelectTrigger>
              <SelectContent>
                {options?.oxide_thicknesses_nm.map((v) => (
                  <SelectItem key={v} value={String(v)}>
                    {String(v)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
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
          <Button size="sm" onClick={load} disabled={loading || !options} className="text-xs">
            Load Saved Result
          </Button>

          {result && (
            <div className="ml-auto flex items-center gap-2">
              <Badge variant="secondary">{result.regime}</Badge>
              <span className="font-mono text-[11px] text-on-surface-variant">
                Qg={result.gate_charge_c_per_cm2.toExponential(2)} C/cm²
              </span>
            </div>
          )}
        </div>

        {error && <p className="text-[11px] text-destructive">{error}</p>}
        <p className="text-[11px] text-on-surface-variant">{status}</p>

        <div className="grid min-h-0 flex-1 grid-cols-2 grid-rows-2 gap-3">
          <div className="min-h-0">
            {potentialData.length > 0 && (
              <Plot data={potentialData} layout={potentialLayout} config={darkPlotConfig} useResizeHandler style={{ width: "100%", height: "100%" }} />
            )}
          </div>
          <div className="min-h-0">
            {carrierData.length > 0 && (
              <Plot data={carrierData} layout={carrierLayout} config={darkPlotConfig} useResizeHandler style={{ width: "100%", height: "100%" }} />
            )}
          </div>
          <div className="min-h-0">
            {chargeData.length > 0 && (
              <Plot data={chargeData} layout={chargeLayout} config={darkPlotConfig} useResizeHandler style={{ width: "100%", height: "100%" }} />
            )}
          </div>
          <div className="min-h-0">
            {bandData.length > 0 && (
              <Plot data={bandData} layout={bandLayout} config={darkPlotConfig} useResizeHandler style={{ width: "100%", height: "100%" }} />
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
