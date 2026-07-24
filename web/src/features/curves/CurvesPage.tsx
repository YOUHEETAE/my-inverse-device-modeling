import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ExplanationPanel, type ExplanationStatus } from "@/components/explanation/ExplanationPanel";
import { CurveChart } from "./components/CurveChart";
import { CurveList } from "./components/CurveList";
import { ElectricalParametersTable } from "./components/ElectricalParametersTable";
import { ParameterInputs } from "./components/ParameterInputs";
import { mockCurveResponse } from "./mockData";
import { DEFAULT_PARAMETERS, type CurveEntry, type DeviceParameters } from "./types";

let nextId = 2;

export default function CurvesPage() {
  const [inputValues, setInputValues] = useState<DeviceParameters>(DEFAULT_PARAMETERS);
  const [curves, setCurves] = useState<CurveEntry[]>([
    {
      id: 1,
      label: "Curve 1",
      visible: true,
      parameters: DEFAULT_PARAMETERS,
      result: mockCurveResponse(DEFAULT_PARAMETERS),
    },
  ]);
  const [activeId, setActiveId] = useState(1);
  const [combined, setCombined] = useState(true);
  const [explanationStatus, setExplanationStatus] = useState<ExplanationStatus>("ready");
  const [explanationContent, setExplanationContent] = useState("");
  const [provider, setProvider] = useState<"mock" | "external_llm">("mock");

  const activeCurve = curves.find((c) => c.id === activeId);

  function selectCurve(id: number) {
    setActiveId(id);
    const curve = curves.find((c) => c.id === id);
    if (curve) setInputValues(curve.parameters);
  }

  function addCurve() {
    const id = nextId++;
    const entry: CurveEntry = {
      id,
      label: `Curve ${curves.length + 1}`,
      visible: true,
      parameters: inputValues,
      result: mockCurveResponse(inputValues),
    };
    setCurves([...curves, entry]);
    setActiveId(id);
  }

  function updateSelected() {
    setCurves(
      curves.map((c) =>
        c.id === activeId
          ? { ...c, parameters: inputValues, result: mockCurveResponse(inputValues) }
          : c,
      ),
    );
  }

  function removeSelected() {
    if (curves.length === 1) return;
    const remaining = curves.filter((c) => c.id !== activeId);
    setCurves(remaining);
    selectCurve(remaining[remaining.length - 1].id);
  }

  function toggleVisible(id: number) {
    setCurves(curves.map((c) => (c.id === id ? { ...c, visible: !c.visible } : c)));
  }

  function analyze() {
    setExplanationStatus("analyzing");
    // Placeholder for the real /explain/curves call — wiring TBD.
    setTimeout(() => {
      setExplanationContent(
        "결과 설명\n- Curve 1의 Id–Vd 및 Id–Vg 예측 결과와 추출된 전기 파라미터를 기준으로 특성을 분석했습니다.\n\n주의사항\n- 이 결과는 학습 모델의 prediction이므로 실제 측정 또는 TCAD 검증을 대체하지 않습니다.",
      );
      setExplanationStatus("complete");
    }, 600);
  }

  return (
    <div className="flex h-full">
      <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-3">
        <div>
          <h2 className="mb-0.5 text-base font-bold uppercase tracking-wide">Device Workbench</h2>
          <p className="text-xs text-on-surface-variant">
            Common device parameters used for physical semiconductor simulation extraction.
          </p>
          <div className="mt-2">
            <ParameterInputs values={inputValues} onChange={setInputValues} />
          </div>
        </div>
        <div className="h-[320px] shrink-0">
          <CurveChart
            curves={curves}
            combined={combined}
            onToggleCombined={() => setCombined(!combined)}
          />
        </div>
        <div className="rounded-md border border-outline-variant bg-surface-container-low p-3">
          <ExplanationPanel
            status={explanationStatus}
            content={explanationContent}
            provider={provider}
            onProviderChange={setProvider}
            onAnalyze={analyze}
            promptText={
              activeCurve
                ? `=== SYSTEM PROMPT ===\n...\n\n=== USER PROMPT ===\nCurve config: ${JSON.stringify(activeCurve.parameters)}`
                : ""
            }
          />
        </div>
      </div>

      <aside className="flex w-72 shrink-0 flex-col gap-4 overflow-y-auto border-l border-outline-variant bg-sidebar p-3">
        <div>
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

        <div>
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
