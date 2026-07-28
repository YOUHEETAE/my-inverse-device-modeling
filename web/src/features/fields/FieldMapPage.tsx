import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ExplanationPanel, type ExplanationStatus } from "@/components/explanation/ExplanationPanel";
import { useDeviceStore, MAX_SHARED_DEVICES } from "../shared/deviceStore";
import { useViewStore } from "../shared/viewStore";
import { usePredictionCache } from "../shared/predictionCache";
import { parametersEqual } from "../shared/parameters";
import { ParameterInputs } from "../curves/components/ParameterInputs";
import { DeviceList } from "./components/DeviceList";
import { DisplayControls } from "./components/DisplayControls";
import { ColorbarLegend } from "./components/ColorbarLegend";
import { EnergyBandLegend } from "./components/EnergyBandLegend";
import { formatFieldLabel } from "./components/colormap";
import { FieldChart } from "./components/FieldChart";
import { FieldCompareChart } from "./components/FieldCompareChart";
import { EnergyBandChart } from "./components/EnergyBandChart";
import {
  explainFields,
  fetchFieldDisplay,
  fetchFieldDisplayCompare,
  getErrorMessage,
  predictField,
  previewFieldsPrompt,
} from "./api";
import {
  FIELD_EXPLANATION_EXCLUDED,
  type DeviceEntry,
  type FieldCompareResponse,
  type FieldConfig,
  type FieldDisplayResponse,
} from "./types";

export default function FieldMapPage() {
  const {
    devices,
    activeId,
    inputValues,
    atCapacity,
    setInputValues,
    selectDevice,
    addDevice,
    updateSelected,
    removeSelected,
    toggleVisible,
  } = useDeviceStore();

  const { fieldMeshes: meshCache, setFieldMeshes: setMeshCache } = usePredictionCache();
  const [predictError, setPredictError] = useState<string | null>(null);

  // Compute field meshes for any shared device that's new or whose parameters
  // changed since the last prediction — lets a curve created on the Curves
  // page show up here with a real mesh already prepared.
  useEffect(() => {
    const stale = devices.filter((d) => {
      const cached = meshCache[d.id];
      return !cached || !parametersEqual(cached.parameters, d.parameters);
    });
    if (stale.length === 0) return;
    let cancelled = false;
    Promise.all(
      stale.map((d) => predictField(d.parameters).then((mesh) => ({ id: d.id, parameters: d.parameters, mesh }))),
    )
      .then((updates) => {
        if (cancelled) return;
        setMeshCache((prev) => {
          const next = { ...prev };
          for (const u of updates) next[u.id] = { parameters: u.parameters, mesh: u.mesh };
          return next;
        });
        setPredictError(null);
      })
      .catch((err) => {
        if (!cancelled) setPredictError(getErrorMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [devices]); // eslint-disable-line react-hooks/exhaustive-deps

  // Label is derived from the current index, not the (permanently-incrementing)
  // id — matches the desktop app's purely positional "Curve N" numbering, so
  // deleting a device renumbers the rest instead of leaving a gap.
  const deviceEntries: DeviceEntry[] = devices.map((d, index) => ({
    id: d.id,
    label: `Curve ${index + 1}`,
    visible: d.visible,
    parameters: d.parameters,
    mesh: meshCache[d.id]?.mesh ?? null,
  }));

  const {
    fieldDisplay: display,
    setFieldDisplay: setDisplay,
    fieldScaleMode: scaleMode,
    setFieldScaleMode: setScaleMode,
    fieldRangeMode: rangeMode,
    setFieldRangeMode: setRangeMode,
  } = useViewStore();
  const [displayData, setDisplayData] = useState<FieldDisplayResponse | null>(null);
  const [compareData, setCompareData] = useState<FieldCompareResponse | null>(null);

  const [explanationStatus, setExplanationStatus] = useState<ExplanationStatus>("ready");
  const [explanationContent, setExplanationContent] = useState("");
  const [provider, setProvider] = useState<"mock" | "external_llm" | null>(null);

  const visibleDevices = deviceEntries.filter((d) => d.visible);
  // View mode is derived from how many devices are checked, not a separate
  // toggle — 2+ checked always means "compare", 1 or 0 always means "single".
  const compareMode = visibleDevices.length >= 2;
  const rangeWarnings = deviceEntries
    .filter((d) => d.mesh?.range_warning)
    .map((d) => `${d.label}: ${d.mesh!.range_warning}`);

  function toFieldConfigs(entries: DeviceEntry[]): FieldConfig[] {
    return entries.map((d) => ({ label: d.label, ...d.parameters }));
  }

  // The single view shows the checked device, not "whichever row was last
  // clicked" (activeDevice) — otherwise unchecking everything still displayed
  // the previously-active device instead of a "select a device" prompt.
  const singleViewDevice = visibleDevices.length === 1 ? visibleDevices[0] : undefined;

  useEffect(() => {
    if (compareMode || !singleViewDevice || display === "Mesh" || display === "Energy band (1D)") {
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
    if (!compareMode || display === "Mesh" || display === "Energy band (1D)" || visibleDevices.length === 0) {
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
    // devices + meshCache (not deviceEntries/visibleDevices) — those are
    // rebuilt with a fresh array/object on every render, so depending on them
    // directly would refetch on every re-render regardless of whether
    // anything actually changed. devices only gets a new reference on a real
    // add/update/remove/toggle-visible mutation, and meshCache only on a real
    // prediction landing, so this refetches exactly when it should.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [compareMode, devices, meshCache, display, scaleMode, rangeMode]);

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
          {display === "Energy band (1D)" ? (
            <EnergyBandChart
              devices={visibleDevices
                .filter((d) => d.mesh)
                .map((d) => ({
                  label: d.label,
                  mesh: d.mesh!.mesh,
                  potential: d.mesh!.node_fields["Potential"],
                  lengthNm: Number(d.parameters.L),
                  toxNm: Number(d.parameters.T),
                }))}
            />
          ) : compareMode ? (
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
              disabled={atCapacity}
            >
              <Plus className="h-3 w-3" />
              Add
            </Button>
          </div>
          <div className="rounded-md border border-outline-variant bg-surface-container">
            <DeviceList
              devices={deviceEntries}
              activeId={activeId}
              onSelect={selectDevice}
              onToggleVisible={toggleVisible}
              onUpdateSelected={updateSelected}
              onRemoveSelected={removeSelected}
            />
          </div>
          {atCapacity && (
            <p className="mt-1 text-[11px] text-accent-orange">Maximum {MAX_SHARED_DEVICES} devices — remove one to add another.</p>
          )}
        </div>

        {display === "Energy band (1D)" ? (
          visibleDevices.some((d) => d.mesh) && (
            <div className="shrink-0">
              <h4 className="mb-2 text-xs font-bold uppercase tracking-wide">Legend</h4>
              <div className="rounded-md border border-outline-variant bg-surface-container">
                <EnergyBandLegend />
              </div>
            </div>
          )
        ) : (
          legendSource && (
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
          )
        )}
      </aside>
    </div>
  );
}
