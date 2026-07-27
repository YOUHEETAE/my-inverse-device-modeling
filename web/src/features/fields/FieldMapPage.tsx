import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ExplanationPanel, type ExplanationStatus } from "@/components/explanation/ExplanationPanel";
import { ParameterInputs } from "../curves/components/ParameterInputs";
import { DeviceList } from "./components/DeviceList";
import { DisplayControls } from "./components/DisplayControls";
import { ColorbarLegend } from "./components/ColorbarLegend";
import { formatFieldLabel } from "./components/colormap";
import { FieldChart } from "./components/FieldChart";
import { FieldCompareChart } from "./components/FieldCompareChart";
import {
  explainFields,
  fetchFieldDisplay,
  fetchFieldDisplayCompare,
  getErrorMessage,
  predictField,
  previewFieldsPrompt,
} from "./api";
import {
  DEFAULT_PARAMETERS,
  FIELD_EXPLANATION_EXCLUDED,
  type DeviceEntry,
  type DeviceParameters,
  type FieldCompareResponse,
  type FieldConfig,
  type FieldDisplay,
  type FieldDisplayResponse,
  type RangeMode,
  type ScaleMode,
} from "./types";

let nextId = 2;
const MAX_DEVICES = 4;

export default function FieldMapPage() {
  const [inputValues, setInputValues] = useState<DeviceParameters>(DEFAULT_PARAMETERS);
  const [devices, setDevices] = useState<DeviceEntry[]>([]);
  const [predictError, setPredictError] = useState<string | null>(null);

  useEffect(() => {
    predictField(DEFAULT_PARAMETERS)
      .then((mesh) => {
        setDevices([{ id: 1, label: "Device 1", visible: true, parameters: DEFAULT_PARAMETERS, mesh }]);
      })
      .catch((err) => setPredictError(getErrorMessage(err)));
  }, []);

  const [activeId, setActiveId] = useState(1);
  const [display, setDisplay] = useState<FieldDisplay>("Mesh");
  const [scaleMode, setScaleMode] = useState<ScaleMode>("Auto");
  const [rangeMode, setRangeMode] = useState<RangeMode>("Robust 1-99%");
  const [displayData, setDisplayData] = useState<FieldDisplayResponse | null>(null);
  const [compareData, setCompareData] = useState<FieldCompareResponse | null>(null);

  const [explanationStatus, setExplanationStatus] = useState<ExplanationStatus>("ready");
  const [explanationContent, setExplanationContent] = useState("");
  const [provider, setProvider] = useState<"mock" | "external_llm" | null>(null);

  const visibleDevices = devices.filter((d) => d.visible);
  // View mode is derived from how many devices are checked, not a separate
  // toggle — 2+ checked always means "compare", 1 or 0 always means "single".
  const compareMode = visibleDevices.length >= 2;
  const rangeWarnings = devices
    .filter((d) => d.mesh?.range_warning)
    .map((d) => `${d.label}: ${d.mesh!.range_warning}`);

  function parametersEqual(a: DeviceParameters, b: DeviceParameters): boolean {
    return a.L === b.L && a.T === b.T && a.B === b.B && a.SD === b.SD && a.LDD === b.LDD;
  }

  function toFieldConfigs(entries: DeviceEntry[]): FieldConfig[] {
    return entries.map((d) => ({ label: d.label, ...d.parameters }));
  }

  // The single view shows the checked device, not "whichever row was last
  // clicked" (activeDevice) — otherwise unchecking everything still displayed
  // the previously-active device instead of a "select a device" prompt.
  const singleViewDevice = visibleDevices.length === 1 ? visibleDevices[0] : undefined;

  useEffect(() => {
    if (compareMode || !singleViewDevice || display === "Mesh") {
      setDisplayData(null);
      return;
    }
    let cancelled = false;
    fetchFieldDisplay(singleViewDevice.parameters, display, scaleMode, rangeMode)
      .then((data) => {
        if (!cancelled) setDisplayData(data);
      })
      .catch((err) => {
        if (!cancelled) setPredictError(getErrorMessage(err));
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [compareMode, singleViewDevice?.id, singleViewDevice?.mesh, display, scaleMode, rangeMode]);

  useEffect(() => {
    if (!compareMode || display === "Mesh" || visibleDevices.length === 0) {
      setCompareData(null);
      return;
    }
    let cancelled = false;
    fetchFieldDisplayCompare(toFieldConfigs(visibleDevices), display, scaleMode, rangeMode)
      .then((data) => {
        if (!cancelled) setCompareData(data);
      })
      .catch((err) => {
        if (!cancelled) setPredictError(getErrorMessage(err));
      });
    return () => {
      cancelled = true;
    };
    // devices (not visibleDevices) so any add/update/remove/toggle-visible
    // mutation (all of which replace the array reference) triggers a refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [compareMode, devices, display, scaleMode, rangeMode]);

  function selectDevice(id: number) {
    setActiveId(id);
    const device = devices.find((d) => d.id === id);
    if (device) setInputValues(device.parameters);
  }

  async function addDevice() {
    if (devices.length >= MAX_DEVICES) return;
    const id = nextId++;
    try {
      const mesh = await predictField(inputValues);
      const entry: DeviceEntry = { id, label: `Device ${id}`, visible: true, parameters: inputValues, mesh };
      setDevices([...devices, entry]);
      setActiveId(id);
      setPredictError(null);
    } catch (err) {
      setPredictError(getErrorMessage(err));
    }
  }

  async function updateSelected() {
    try {
      const mesh = await predictField(inputValues);
      setDevices(devices.map((d) => (d.id === activeId ? { ...d, parameters: inputValues, mesh } : d)));
      setPredictError(null);
    } catch (err) {
      setPredictError(getErrorMessage(err));
    }
  }

  function removeSelected() {
    const remaining = devices.filter((d) => !d.visible);
    setDevices(remaining);
    if (remaining.length > 0 && !remaining.some((d) => d.id === activeId)) {
      selectDevice(remaining[remaining.length - 1].id);
    }
  }

  function toggleVisible(id: number) {
    setDevices(devices.map((d) => (d.id === id ? { ...d, visible: !d.visible } : d)));
  }

  const legendSource = compareMode ? compareData : displayData;

  const hasIdenticalDevices =
    visibleDevices.length === 2 && parametersEqual(visibleDevices[0].parameters, visibleDevices[1].parameters);

  const explanationDisabled =
    visibleDevices.length === 0 ||
    visibleDevices.length > 2 ||
    hasIdenticalDevices ||
    FIELD_EXPLANATION_EXCLUDED.has(display);
  const explanationDisabledReason =
    visibleDevices.length === 0
      ? "Check at least one device to analyze."
      : visibleDevices.length > 2
        ? "LLM explanation supports at most 2 devices — uncheck some to analyze."
        : hasIdenticalDevices
          ? "Selected devices have identical parameters — nothing to compare."
          : `${display} is not supported by LLM explanation.`;

  async function analyze() {
    if (explanationDisabled) return;
    setExplanationStatus("analyzing");
    try {
      const result = await explainFields(toFieldConfigs(visibleDevices), display, scaleMode, rangeMode);
      setExplanationContent(
        [...result.descriptions, ...result.comparisons, ...result.tradeoffs, ...result.cautions].join("\n"),
      );
      setProvider(result.provider as "mock" | "external_llm");
      setExplanationStatus("complete");
    } catch {
      setExplanationStatus("failed");
    }
  }

  return (
    <div className="flex h-full">
      <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-3">
        <div>
          <div className="flex items-start justify-between">
            <div>
              <h2 className="mb-0.5 text-base font-bold uppercase tracking-wide">Structure / Field Map</h2>
              <p className="text-xs text-on-surface-variant">
                Predicted 2D field distributions over the generated device mesh.
              </p>
            </div>
            <div className="flex gap-2">
              <DisplayControls
                display={display}
                onDisplayChange={setDisplay}
                scaleMode={scaleMode}
                onScaleModeChange={setScaleMode}
                rangeMode={rangeMode}
                onRangeModeChange={setRangeMode}
              />
            </div>
          </div>
          <div className="mt-2">
            <ParameterInputs values={inputValues} onChange={setInputValues} />
          </div>
          {predictError && <p className="mt-1 text-[11px] text-destructive">{predictError}</p>}
          {rangeWarnings.length > 0 && (
            <p className="mt-1 text-[11px] text-accent-orange">{rangeWarnings.join(" | ")}</p>
          )}
        </div>
        <div className="h-[420px] shrink-0">
          {compareMode ? (
            <FieldCompareChart
              devices={visibleDevices
                .filter((d) => d.mesh)
                .map((d) => ({ label: d.label, mesh: d.mesh!.mesh, toxNm: Number(d.parameters.T) }))}
              display={display}
              compareData={compareData}
            />
          ) : (
            <FieldChart
              mesh={singleViewDevice?.mesh?.mesh ?? null}
              toxNm={Number(singleViewDevice?.parameters.T ?? 0)}
              display={display}
              displayData={displayData}
            />
          )}
        </div>
        <div className="rounded-md border border-outline-variant bg-surface-container-low p-3">
          <ExplanationPanel
            status={explanationStatus}
            content={explanationContent}
            provider={provider}
            onAnalyze={analyze}
            disabled={explanationDisabled}
            disabledReason={explanationDisabledReason}
            fetchPromptText={() =>
              !explanationDisabled
                ? previewFieldsPrompt(toFieldConfigs(visibleDevices), display, scaleMode, rangeMode).then((r) => r.prompt)
                : Promise.resolve("")
            }
          />
        </div>
      </div>

      <aside className="flex w-72 shrink-0 flex-col gap-4 overflow-y-auto border-l border-outline-variant bg-sidebar p-3">
        <div className="shrink-0">
          <div className="mb-2 flex items-center justify-between">
            <h4 className="text-xs font-bold uppercase tracking-wide">Devices</h4>
            <Button
              size="sm"
              variant="outline"
              className="h-6 gap-1 rounded-sm border-outline-variant bg-surface-container-highest px-2 text-[10px] uppercase"
              onClick={addDevice}
              disabled={devices.length >= MAX_DEVICES}
            >
              <Plus className="h-3 w-3" />
              Add
            </Button>
          </div>
          <div className="rounded-md border border-outline-variant bg-surface-container">
            <DeviceList
              devices={devices}
              activeId={activeId}
              onSelect={selectDevice}
              onToggleVisible={toggleVisible}
              onUpdateSelected={updateSelected}
              onRemoveSelected={removeSelected}
            />
          </div>
          {devices.length >= MAX_DEVICES && (
            <p className="mt-1 text-[11px] text-accent-orange">Maximum {MAX_DEVICES} devices — remove one to add another.</p>
          )}
        </div>

        {legendSource && (
          <div className="shrink-0">
            <h4 className="mb-2 text-xs font-bold uppercase tracking-wide">Legend</h4>
            <div className="rounded-md border border-outline-variant bg-surface-container p-2">
              <ColorbarLegend
                label={formatFieldLabel(`${legendSource.label} [${legendSource.mode_label}]`)}
                cmap={legendSource.cmap}
                vmin={legendSource.vmin}
                vmax={legendSource.vmax}
              />
            </div>
          </div>
        )}
      </aside>
    </div>
  );
}
