import type { Data, Layout } from "plotly.js";
import { Plot } from "@/lib/plot";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { MeshData } from "../types";
import { computeEnergyBand } from "./energyBand";

interface EnergyBandDevice {
  label: string;
  mesh: MeshData;
  potential: number[];
  lengthNm: number;
  toxNm: number;
}

interface EnergyBandChartProps {
  devices: EnergyBandDevice[];
}

const VLINE = (x: number): NonNullable<Layout["shapes"]>[number] => ({
  type: "line",
  x0: x,
  x1: x,
  y0: 0,
  y1: 1,
  yref: "paper",
  line: { color: "#888888", width: 1, dash: "dash" },
});

const PANEL_MARGIN = { t: 28, b: 34, l: 44, r: 10 };

export function EnergyBandChart({ devices }: EnergyBandChartProps) {
  if (devices.length === 0) {
    return (
      <Card className="flex h-full items-center justify-center">
        <p className="text-sm text-muted-foreground">No device selected</p>
      </Card>
    );
  }

  return (
    <div className="grid h-full gap-3" style={{ gridTemplateColumns: `repeat(${devices.length}, 1fr)` }}>
      {devices.map((device) => {
        const band = computeEnergyBand(device.mesh, device.potential, device.lengthNm, device.toxNm);

        const channelTraces: Data[] = [
          { type: "scatter", mode: "lines", x: band.channelCut.x, y: band.channelCut.ec, name: "Ec", line: { color: "#0D47A1" } },
          { type: "scatter", mode: "lines", x: band.channelCut.x, y: band.channelCut.ev, name: "Ev", line: { color: "#B71C1C" } },
        ];

        const verticalTraces: Data[] = band.verticalCut.panels.flatMap((panel) => [
          { type: "scatter", mode: "lines", x: panel.depth, y: panel.ec, name: `${panel.name} Ec`, line: { color: panel.ecColor } },
          { type: "scatter", mode: "lines", x: panel.depth, y: panel.ev, name: `${panel.name} Ev`, line: { color: panel.evColor } },
        ]);

        return (
          <Card key={`${device.label}-${devices.length}`} className="flex flex-col">
            <CardHeader>
              <CardTitle>{device.label}</CardTitle>
            </CardHeader>
            <CardContent className="grid flex-1 grid-rows-2 gap-2">
              <Plot
                data={channelTraces}
                layout={{
                  margin: PANEL_MARGIN,
                  title: { text: `Source - Gate - Drain (y=${band.channelCut.yChannel.toFixed(3)} nm)`, font: { size: 11 } },
                  xaxis: { title: { text: "x (nm)" } },
                  yaxis: { title: { text: "Relative energy (eV)" } },
                  shapes: [VLINE(band.channelCut.gateLeft), VLINE(band.channelCut.gateRight)],
                  showlegend: false,
                }}
                config={{ displaylogo: false, responsive: true }}
                useResizeHandler
                style={{ width: "100%", height: "100%" }}
              />
              <Plot
                data={verticalTraces}
                layout={{
                  margin: PANEL_MARGIN,
                  title: { text: "Gate - Oxide - Bulk", font: { size: 11 } },
                  xaxis: { title: { text: "y (nm)" } },
                  yaxis: { title: { text: "Relative energy (eV)" } },
                  shapes: [VLINE(band.verticalCut.oxideTop), VLINE(0)],
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
