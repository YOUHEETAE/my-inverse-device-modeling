import { useEffect, useMemo, useState } from "react";
import type { Data, Layout } from "plotly.js";
import { Plot } from "@/lib/plot";
import { darkPlotConfig, darkPlotLayout } from "@/lib/plotTheme";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { fetchPNOptions, fetchPNResult, getErrorMessage } from "./api";
import { FIELD_OPTIONS, LOWER_PLOT_OPTIONS, type FieldOption, type LowerPlotOption, type PNOptions, type PNResult } from "./types";
import { buildPNHeatmapTrace, centerlineIndices, computeBandDiagram, computeChargeDensity, selectField } from "./pnJunctionMath";

const JUNCTION_X_UM = 0.05;

function formatDoping(value: number): string {
  return value.toExponential(0);
}

export function PNJunctionTool() {
  const [options, setOptions] = useState<PNOptions | null>(null);
  const [acceptors, setAcceptors] = useState("1e18");
  const [donors, setDonors] = useState("1e18");
  const [bias, setBias] = useState("0");
  const [field, setField] = useState<FieldOption>("Net Doping");
  const [lowerPlot, setLowerPlot] = useState<LowerPlotOption>("Forward I–V");
  const [result, setResult] = useState<PNResult | null>(null);
  const [status, setStatus] = useState("Ready");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Defaults (NA=ND=1e18, bias=0) match the desktop app's initial state —
    // no need to override once the real option list arrives.
    fetchPNOptions()
      .then((data) => {
        setOptions(data);
      })
      .catch((err) => setError(getErrorMessage(err)));
  }, []);

  async function load() {
    setLoading(true);
    setError(null);
    setStatus("Loading saved result…");
    try {
      const data = await fetchPNResult(Number(acceptors), Number(donors), Number(bias));
      setResult(data);
      setStatus(`Complete — ${data.x_um.length} silicon nodes, field map at ${data.selected_bias.toFixed(1)} V`);
    } catch (err) {
      setError(getErrorMessage(err));
      setStatus("Load failed");
    } finally {
      setLoading(false);
    }
  }

  const fieldData = useMemo<Data[]>(() => {
    if (!result) return [];
    const selection = selectField(result, field);
    const heatmap = buildPNHeatmapTrace(result, selection);

    const yMin = Math.min(...result.y_um);
    const yMax = Math.max(...result.y_um);
    const yText = yMin + 0.84 * (yMax - yMin);
    const labels = {
      type: "scatter",
      mode: "text",
      x: [0.025, 0.075],
      y: [yText, yText],
      text: ["P-type", "N-type"],
      textfont: { color: "white", size: 10 },
      hoverinfo: "skip",
      showlegend: false,
    } as unknown as Data;

    return [heatmap, labels];
  }, [result, field]);

  const fieldLayout = useMemo<Partial<Layout>>(() => {
    if (!result) return {};
    return {
      paper_bgcolor: "transparent",
      margin: { t: 36, b: 30, l: 45, r: 10 },
      // No scaleanchor on the y-axis: the domain is actually square (0-0.1 µm
      // both axes), but the desktop app deliberately stretches it to fill the
      // panel width via set_aspect("auto") rather than showing true 1:1
      // proportions — a plain 2D trace does this by default, unlike a mesh3d
      // scene (which was tried first and doesn't stretch to fill a
      // non-square container).
      xaxis: { ...darkPlotLayout.xaxis, title: { text: "x (µm)" } },
      yaxis: { ...darkPlotLayout.yaxis, title: { text: "y (µm)" } },
      shapes: [
        {
          type: "line",
          x0: JUNCTION_X_UM,
          x1: JUNCTION_X_UM,
          y0: 0,
          y1: 1,
          yref: "paper",
          line: { color: "white", dash: "dash", width: 1 },
        },
      ],
      title: { text: `${field} at V = ${result.selected_bias.toFixed(1)} V`, font: { size: 12 } },
      showlegend: false,
    };
  }, [result, field]);

  const { lowerData, lowerLayout } = useMemo(() => {
    if (!result) return { lowerData: [] as Data[], lowerLayout: darkPlotLayout };

    if (lowerPlot === "Forward I–V") {
      const y = result.currents.map((c) => Math.max(Math.abs(c), 1e-30));
      return {
        lowerData: [{ type: "scatter", mode: "lines+markers", x: result.voltages, y, line: { color: "#d1495b" } } as Data],
        lowerLayout: {
          ...darkPlotLayout,
          title: { text: "Forward-bias I–V", font: { size: 12 } },
          xaxis: { ...darkPlotLayout.xaxis, title: { text: "Applied voltage (V)" } },
          yaxis: { ...darkPlotLayout.yaxis, title: { text: "|Current| (A/cm)" }, type: "log" },
          margin: { t: 36, b: 40, l: 55, r: 10 },
          showlegend: false,
        } as Partial<Layout>,
      };
    }

    const { indices, centerY } = centerlineIndices(result);
    const x = indices.map((i) => result.x_um[i]);
    const junctionLine = {
      type: "line" as const,
      x0: JUNCTION_X_UM,
      x1: JUNCTION_X_UM,
      y0: 0,
      y1: 1,
      yref: "paper" as const,
      line: { color: "#a1a1aa", dash: "dash" as const, width: 1 },
    };
    const baseLayout: Partial<Layout> = {
      ...darkPlotLayout,
      xaxis: { ...darkPlotLayout.xaxis, title: { text: "x along horizontal centerline (µm)" } },
      margin: { t: 36, b: 40, l: 55, r: 10 },
      shapes: [junctionLine],
    };

    if (lowerPlot === "Carrier Concentrations (line cut)") {
      const electrons = indices.map((i) => Math.max(result.electrons[i], 1));
      const holes = indices.map((i) => Math.max(result.holes[i], 1));
      return {
        lowerData: [
          { type: "scatter", mode: "lines", x, y: electrons, name: "Electrons n", line: { color: "#2f4b7c" } } as Data,
          { type: "scatter", mode: "lines", x, y: holes, name: "Holes p", line: { color: "#d45087" } } as Data,
        ],
        lowerLayout: {
          ...baseLayout,
          title: { text: `Electron and hole concentrations at y=${centerY.toFixed(3)} µm`, font: { size: 12 } },
          yaxis: { ...darkPlotLayout.yaxis, title: { text: "Carrier concentration (cm⁻³)" }, type: "log" },
          legend: { ...darkPlotLayout.legend, orientation: "h" },
        } as Partial<Layout>,
      };
    }

    if (lowerPlot === "Charge Density (line cut)") {
      const charge = computeChargeDensity(result, indices);
      return {
        lowerData: [{ type: "scatter", mode: "lines", x, y: charge, line: { color: "#7a5195" } } as Data],
        lowerLayout: {
          ...baseLayout,
          title: { text: `Space-charge density at y=${centerY.toFixed(3)} µm`, font: { size: 12 } },
          yaxis: { ...darkPlotLayout.yaxis, title: { text: "Charge density ρ (C/cm³)" } },
          showlegend: false,
        } as Partial<Layout>,
      };
    }

    if (lowerPlot === "Electric Field (line cut)") {
      const values = indices.map((i) => result.electric_field_x[i]);
      return {
        lowerData: [{ type: "scatter", mode: "lines", x, y: values, line: { color: "#ef5675" } } as Data],
        lowerLayout: {
          ...baseLayout,
          title: { text: `Electric-field distribution at y=${centerY.toFixed(3)} µm`, font: { size: 12 } },
          yaxis: { ...darkPlotLayout.yaxis, title: { text: "Electric field Ex (V/cm)" } },
          showlegend: false,
        } as Partial<Layout>,
      };
    }

    if (lowerPlot === "Potential (line cut)") {
      const values = indices.map((i) => result.potential[i]);
      return {
        lowerData: [{ type: "scatter", mode: "lines", x, y: values, line: { color: "#2f4b7c" } } as Data],
        lowerLayout: {
          ...baseLayout,
          title: { text: `Electrostatic-potential distribution at y=${centerY.toFixed(3)} µm`, font: { size: 12 } },
          yaxis: { ...darkPlotLayout.yaxis, title: { text: "Potential ψ (V)" } },
          showlegend: false,
        } as Partial<Layout>,
      };
    }

    const band = computeBandDiagram(result, indices);
    return {
      lowerData: [
        { type: "scatter", mode: "lines", x: band.x, y: band.conductionBand, name: "Ec", line: { color: "#003f5c" } } as Data,
        { type: "scatter", mode: "lines", x: band.x, y: band.intrinsicLevel, name: "Ei", line: { color: "#7a5195", dash: "dash" } } as Data,
        { type: "scatter", mode: "lines", x: band.x, y: band.valenceBand, name: "Ev", line: { color: "#ef5675" } } as Data,
        { type: "scatter", mode: "lines", x: band.x, y: band.electronQuasiFermi, name: "EFn", line: { color: "#111111", dash: "dashdot" } } as Data,
        { type: "scatter", mode: "lines", x: band.x, y: band.holeQuasiFermi, name: "EFp", line: { color: "#555555", dash: "dot" } } as Data,
      ],
      lowerLayout: {
        ...baseLayout,
        title: { text: `Energy-band diagram at y=${centerY.toFixed(3)} µm`, font: { size: 12 } },
        yaxis: { ...darkPlotLayout.yaxis, title: { text: "Relative energy (eV)" } },
        legend: { ...darkPlotLayout.legend, orientation: "h" },
      } as Partial<Layout>,
    };
  }, [result, lowerPlot]);

  return (
    <Card className="flex h-[720px] flex-col">
      <CardContent className="flex flex-1 flex-col gap-3 overflow-hidden">
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase text-on-surface-variant">Acceptor NA (cm⁻³)</label>
            <Select value={acceptors} onValueChange={(value) => setAcceptors(value as string)}>
              <SelectTrigger size="sm" className="w-28 text-xs">
                <SelectValue>{acceptors}</SelectValue>
              </SelectTrigger>
              <SelectContent>
                {options?.dopings.map((v) => (
                  <SelectItem key={v} value={formatDoping(v)}>
                    {formatDoping(v)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase text-on-surface-variant">Donor ND (cm⁻³)</label>
            <Select value={donors} onValueChange={(value) => setDonors(value as string)}>
              <SelectTrigger size="sm" className="w-28 text-xs">
                <SelectValue>{donors}</SelectValue>
              </SelectTrigger>
              <SelectContent>
                {options?.dopings.map((v) => (
                  <SelectItem key={v} value={formatDoping(v)}>
                    {formatDoping(v)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase text-on-surface-variant">Bias (V)</label>
            <Select value={bias} onValueChange={(value) => setBias(value as string)}>
              <SelectTrigger size="sm" className="w-24 text-xs">
                <SelectValue>{bias}</SelectValue>
              </SelectTrigger>
              <SelectContent>
                {options?.biases.map((v) => (
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
            <Select value={field} onValueChange={(v) => setField(v as FieldOption)}>
              <SelectTrigger size="sm" className="w-44 text-xs">
                <SelectValue>{field}</SelectValue>
              </SelectTrigger>
              <SelectContent>
                {FIELD_OPTIONS.map((option) => (
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

        <div className="h-64 shrink-0">
          {fieldData.length > 0 ? (
            <Plot data={fieldData} layout={fieldLayout} config={darkPlotConfig} useResizeHandler style={{ width: "100%", height: "100%" }} />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              Load a saved result to display the 2D field map
            </div>
          )}
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-[10px] uppercase text-on-surface-variant">Lower graph</label>
          <Select value={lowerPlot} onValueChange={(v) => setLowerPlot(v as LowerPlotOption)}>
            <SelectTrigger size="sm" className="w-64 text-xs">
              <SelectValue>{lowerPlot}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              {LOWER_PLOT_OPTIONS.map((option) => (
                <SelectItem key={option} value={option}>
                  {option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="h-64 flex-1">
          {result ? (
            <Plot data={lowerData} layout={lowerLayout} config={darkPlotConfig} useResizeHandler style={{ width: "100%", height: "100%" }} />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">Forward-bias I–V</div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
