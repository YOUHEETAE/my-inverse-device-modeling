import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ExplanationPanel, type ExplanationStatus } from "@/components/explanation/ExplanationPanel";
import { CurveChart } from "./components/CurveChart";
import { CurveList } from "./components/CurveList";
import { ElectricalParametersTable } from "./components/ElectricalParametersTable";
import { ParameterInputs } from "./components/ParameterInputs";
import { DEFAULT_PARAMETERS, type CurveConfig, type CurveEntry, type DeviceParameters } from "./types";
import { explainCurve, getErrorMessage, predictCurve, previewCurvePrompt } from "./api";

let nextId = 2;

export default function CurvesPage() {
  const [inputValues, setInputValues] = useState<DeviceParameters>(DEFAULT_PARAMETERS);
  const [curves, setCurves] = useState<CurveEntry[]>([]);
  const [predictError, setPredictError] = useState<string | null>(null);
  useEffect(() => {
    predictCurve(DEFAULT_PARAMETERS)
      .then((result) => {
        setCurves([{ id: 1, label: "Curve 1", visible: true, parameters: DEFAULT_PARAMETERS, result }]);
      })
      .catch((err) => setPredictError(getErrorMessage(err)));
  }, [])
  const [activeId, setActiveId] = useState(1);
  const [combined, setCombined] = useState(true);
  const [logScale, setLogScale] = useState(false);
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

  function selectCurve(id: number) {
    setActiveId(id);
    const curve = curves.find((c) => c.id === id);
    if (curve) setInputValues(curve.parameters);
  }

  async function addCurve() {
    const id = nextId++;
    try {
      const result = await predictCurve(inputValues);
      const entry: CurveEntry = {
        id,
        label: `Curve ${id}`,
        visible: true,
        parameters: inputValues,
        result,
      };
      setCurves([...curves, entry]);
      setActiveId(id);
      setPredictError(null);
    } catch (err) {
      setPredictError(getErrorMessage(err));
    }
  }

  async function updateSelected() {
    try {
      const result = await predictCurve(inputValues);
      setCurves(
        curves.map((c) =>
          c.id === activeId
            ? { ...c, parameters: inputValues, result }
            : c,
        ),
      );
      setPredictError(null);
    } catch (err) {
      setPredictError(getErrorMessage(err));
    }
  }

  function removeSelected() {
    const remaining = curves.filter((c) => !c.visible);
    setCurves(remaining);
    if (remaining.length > 0 && !remaining.some((c) => c.id === activeId)) {
      selectCurve(remaining[remaining.length - 1].id);
    }
  }

  function toggleVisible(id: number) {
    setCurves(curves.map((c) => (c.id === id ? { ...c, visible: !c.visible } : c)));
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
              onClick={addCurve}
            >
              <Plus className="h-3 w-3" />
              Add
            </Button>
          </div>
          <div className="rounded-md border border-outline-variant bg-surface-container">
            <CurveList
              curves={curves}
              activeId={activeId}
              onSelect={selectCurve}
              onToggleVisible={toggleVisible}
              onUpdateSelected={updateSelected}
              onRemoveSelected={removeSelected}
            />
          </div>
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
