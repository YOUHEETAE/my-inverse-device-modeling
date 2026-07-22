import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
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
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
        <div>
          <h1 className="text-lg font-semibold">I-V Curve</h1>
          <p className="text-sm text-muted-foreground">
            Common device parameters
          </p>
          <div className="mt-2">
            <ParameterInputs values={inputValues} onChange={setInputValues} />
          </div>
        </div>
        <Separator />
        <div className="h-[420px] shrink-0">
          <CurveChart
            curves={curves}
            combined={combined}
            onToggleCombined={() => setCombined(!combined)}
          />
        </div>
        <Separator />
        <Card>
          <CardContent className="pt-4">
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
          </CardContent>
        </Card>
      </div>

      <div className="flex w-80 shrink-0 flex-col gap-4 overflow-y-auto border-l p-4">
        <Card>
          <CardContent className="pt-4">
            <p className="mb-2 text-sm font-semibold">Curves</p>
            <CurveList
              curves={curves}
              activeId={activeId}
              onSelect={selectCurve}
              onToggleVisible={toggleVisible}
              onAdd={addCurve}
              onUpdateSelected={updateSelected}
              onRemoveSelected={removeSelected}
            />
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <p className="mb-2 text-sm font-semibold">Extracted electrical parameters</p>
            <ElectricalParametersTable curves={curves} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
