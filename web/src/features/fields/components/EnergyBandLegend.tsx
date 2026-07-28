const CHANNEL_ITEMS = [
  { label: "Ec", color: "#0D47A1" },
  { label: "Ev", color: "#B71C1C" },
];

const VERTICAL_ITEMS = [
  { label: "Bulk Ec", color: "#1565C0" },
  { label: "Bulk Ev", color: "#C62828" },
  { label: "Oxide Ec", color: "#00897B" },
  { label: "Oxide Ev", color: "#6A1B9A" },
  { label: "Gate Ec", color: "#42A5F5" },
  { label: "Gate Ev", color: "#EF5350" },
];

function Swatch({ label, color }: { label: string; color: string }) {
  return (
    <div className="flex items-center gap-1.5 text-[10px] text-on-surface-variant">
      <span className="h-0.5 w-4 shrink-0" style={{ backgroundColor: color }} />
      {label}
    </div>
  );
}

// Every device's energy-band panels use the same fixed colors (see
// energyBand.ts's VERTICAL_STYLES / EnergyBandChart's channel trace colors),
// so the legend is shown once here instead of repeating it on every panel —
// with 3-4 devices the per-panel legend wrapped and overlapped the axis
// titles beneath it.
export function EnergyBandLegend() {
  return (
    <div className="flex flex-col gap-2 p-2">
      <div>
        <p className="mb-1 text-[10px] font-bold uppercase tracking-wide text-on-surface-variant">Source–Gate–Drain</p>
        <div className="flex flex-wrap gap-x-3 gap-y-1">
          {CHANNEL_ITEMS.map((item) => (
            <Swatch key={item.label} {...item} />
          ))}
        </div>
      </div>
      <div>
        <p className="mb-1 text-[10px] font-bold uppercase tracking-wide text-on-surface-variant">Gate–Oxide–Bulk</p>
        <div className="flex flex-wrap gap-x-3 gap-y-1">
          {VERTICAL_ITEMS.map((item) => (
            <Swatch key={item.label} {...item} />
          ))}
        </div>
      </div>
    </div>
  );
}
