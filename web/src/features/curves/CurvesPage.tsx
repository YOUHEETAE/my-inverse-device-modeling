import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ExplanationPanel, type ExplanationStatus } from "@/components/explanation/ExplanationPanel";
import { useDeviceStore, MAX_SHARED_DEVICES } from "../shared/deviceStore";
import { useViewStore } from "../shared/viewStore";
import { usePredictionCache } from "../shared/predictionCache";
import { parametersEqual } from "../shared/parameters";
import { CurveChart } from "./components/CurveChart";
import { CurveList } from "./components/CurveList";
import { ElectricalParametersTable } from "./components/ElectricalParametersTable";
import { ParameterInputs } from "./components/ParameterInputs";
import type { CurveConfig, CurveEntry } from "./types";
import { explainCurve, getErrorMessage, predictCurve, previewCurvePrompt } from "./api";

export default function CurvesPage() {
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

  const { curveResults: resultsCache, setCurveResults: setResultsCache } = usePredictionCache();
  const [predictError, setPredictError] = useState<string | null>(null);

  // Predict curves for any shared device that's new or whose parameters
  // changed since the last prediction — lets a device created on the Field
  // Map page (or updated there) show up here with a real curve.
  useEffect(() => {
    const stale = devices.filter((d) => {
      const cached = resultsCache[d.id];
      return !cached || !parametersEqual(cached.parameters, d.parameters);
    });
    if (stale.length === 0) return;
    let cancelled = false;
    Promise.all(
      stale.map((d) => predictCurve(d.parameters).then((result) => ({ id: d.id, parameters: d.parameters, result }))),
    )
      .then((updates) => {
        if (cancelled) return;
        setResultsCache((prev) => {
          const next = { ...prev };
          for (const u of updates) next[u.id] = { parameters: u.parameters, result: u.result };
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
  // deleting a curve renumbers the rest instead of leaving a gap.
  const curves: CurveEntry[] = devices.map((d, index) => ({
    id: d.id,
    label: `Curve ${index + 1}`,
    visible: d.visible,
    parameters: d.parameters,
    result: resultsCache[d.id]?.result ?? null,
  }));

  const {
    curveCombined: combined,
    setCurveCombined: setCombined,
    curveLogScale: logScale,
    setCurveLogScale: setLogScale,
  } = useViewStore();
  const [explanationStatus, setExplanationStatus] = useState<ExplanationStatus>("ready");
  const [explanationContent, setExplanationContent] = useState("");
  const [provider, setProvider] = useState<"mock" | "external_llm" | null>(null);

  const visibleCurves = curves.filter((c) => c.visible);
  const rangeWarnings = curves
    .filter((c) => c.result?.range_warning)
    .map((c) => `${c.label}: ${c.result!.range_warning}`);

  function toCurveConfigs(entries: CurveEntry[]): CurveConfig[] {
    return entries.map((c) => ({ label: c.label, ...c.parameters }));
  }

  async function analyze() {
    if (visibleCurves.length === 0) return;
    setExplanationStatus("analyzing");
    try {
      const result = await explainCurve(toCurveConfigs(visibleCurves));
      setExplanationContent(
        [...result.descriptions, ...result.comparisons, ...result.tradeoffs, ...result.cautions].join("\n"),
      );
      setProvider(result.provider as "mock" | "external_llm");
      setExplanationStatus("complete")
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
              <h2 className="mb-0.5 text-base font-bold uppercase tracking-wide">Device Workbench</h2>
              <p className="text-xs text-on-surface-variant">
                Common device parameters used for physical semiconductor simulation extraction.
              </p>
            </div>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" className="text-xs uppercase" onClick={() => setLogScale(!logScale)}>
                {logScale ? "Linear Scale" : "Log Scale"}
              </Button>
              <Button size="sm" variant="outline" className="text-xs uppercase" onClick={() => setCombined(!combined)}>
                {combined ? "Separate Biases" : "Combine Biases"}
              </Button>
            </div>
          </div>
          <div className="mt-2">
            <ParameterInputs values={inputValues} onChange={setInputValues} />
          </div>
          {predictError && (
            <p className="mt-1 text-[11px] text-destructive">{predictError}</p>
          )}
          {rangeWarnings.length > 0 && (
            <p className="mt-1 text-[11px] text-accent-orange">{rangeWarnings.join(" | ")}</p>
          )}
        </div>
        <div className="h-[320px] shrink-0">
          <CurveChart curves={curves} combined={combined} logScale={logScale} />
        </div>
        <div className="rounded-md border border-outline-variant bg-surface-container-low p-3">
          <ExplanationPanel
            status={explanationStatus}
            content={explanationContent}
            provider={provider}
            onAnalyze={analyze}
            disabled={visibleCurves.length === 0}
            disabledReason="Check at least one curve to analyze."
            fetchPromptText={() =>
              visibleCurves.length > 0
                ? previewCurvePrompt(toCurveConfigs(visibleCurves)).then((r) => r.prompt)
                : Promise.resolve("")
            }
          />
        </div>
      </div>

      <aside className="flex w-72 shrink-0 flex-col gap-4 overflow-y-auto border-l border-outline-variant bg-sidebar p-3">
        <div className="shrink-0">
          <div className="mb-2 flex items-center justify-between">
            <h4 className="text-xs font-bold uppercase tracking-wide">Curves</h4>
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
            <CurveList
              curves={curves}
              activeId={activeId}
              onSelect={selectDevice}
              onToggleVisible={toggleVisible}
              onUpdateSelected={updateSelected}
              onRemoveSelected={removeSelected}
            />
          </div>
          {atCapacity && (
            <p className="mt-1 text-[11px] text-accent-orange">Maximum {MAX_SHARED_DEVICES} curves — remove one to add another.</p>
          )}
        </div>

        <div className="shrink-0">
          <h4 className="text-xs font-bold uppercase tracking-wide">Extracted Parameters</h4>
          <p className="mb-2 text-[11px] text-on-surface-variant">
            Calculated physical metrics from {curves.find((c) => c.id === activeId)?.label ?? "the active curve"}
          </p>
          <ElectricalParametersTable curves={curves} />
        </div>
      </aside>
    </div>
  );
}
