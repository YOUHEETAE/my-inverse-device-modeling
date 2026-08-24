import { useEffect, useState } from "react";
import {
  Loader2,
  PanelRightClose,
  PanelRightOpen,
  RotateCcw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { CurveChart } from "@/features/curves/components/CurveChart";
import { FieldCompareChart } from "@/features/fields/components/FieldCompareChart";
import { DisplayControls } from "@/features/fields/components/DisplayControls";
import { fetchFieldDisplayCompare, predictField } from "@/features/fields/api";
import {
  FIELD_DISPLAYS,
  type FieldCompareResponse,
  type FieldDisplay,
  type FieldResponse,
} from "@/features/fields/types";
import type { CurveEntry, DeviceParameters } from "@/features/curves/types";
import { MetricTable } from "./MetricTable";
import { CaseFollowupChat } from "./CaseFollowupChat";
import type { ConditionRun, ExperimentResult, LearningSession } from "../types";

const TABS = [
  { id: "curve", label: "I–V Curve" },
  { id: "field", label: "Field Map" },
  { id: "chat", label: "AI 자유 질문" },
] as const;

type TabId = (typeof TABS)[number]["id"];

interface ResultsViewProps {
  session: LearningSession;
  result: ExperimentResult | null;
  busy: boolean;
  onRegenerate: () => void;
}

/**
 * 결과 관찰의 왼쪽 (panel.py의 _build_results): 그래프 탭들과 지표 표.
 *
 * 표는 세션에서 복원되지만 그래프는 아니다 — 곡선을 세션에 저장하지 않기
 * 때문에, 저장된 세션을 다시 열면 다시 만들어야 한다. 데스크톱도 같은
 * 자리에 "그래프 다시 생성" 버튼을 둔다.
 */
export function ResultsView({
  session,
  result,
  busy,
  onRegenerate,
}: ResultsViewProps) {
  const [tab, setTab] = useState<TabId>("curve");
  // 지표 표는 그래프를 밀어내지 않고 그 위에 뜬다. 나란히 두면 셋이 폭을
  // 나눠 갖느라 그래프가 눌리고, 표를 접었다 펼 때마다 그래프 크기가 바뀌어
  // 방금 보던 모양과 달라진다. 덮어두면 그래프는 늘 같은 크기다.
  const [showMetrics, setShowMetrics] = useState(true);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div
        role="tablist"
        className="flex shrink-0 gap-1 border-b border-outline-variant"
      >
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            role="tab"
            type="button"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={cn(
              "-mb-px border-b-2 px-3 py-1.5 text-xs font-bold transition-colors motion-reduce:transition-none",
              tab === id
                ? "border-primary text-primary"
                : "border-transparent text-on-surface-variant hover:text-on-surface",
            )}
          >
            {label}
          </button>
        ))}
        <Button
          variant="ghost"
          size="sm"
          className="ml-auto h-7 gap-1 px-2 text-[10px] text-on-surface-variant"
          onClick={() => setShowMetrics((value) => !value)}
          aria-pressed={showMetrics}
        >
          {showMetrics ? (
            <PanelRightClose className="h-3.5 w-3.5" />
          ) : (
            <PanelRightOpen className="h-3.5 w-3.5" />
          )}
          파라미터
        </Button>
      </div>

      {/* relative: 지표 표가 이 영역 안에서만 뜬다 — 옆 질문 칸까지 덮으면
          답을 적으면서 값을 보려던 게 반대로 막힌다. */}
      <div className="relative min-h-0 flex-1 pt-3">
        {tab === "chat" ? (
          <CaseFollowupChat session={session} />
        ) : !result ? (
          <MissingPlots busy={busy} onRegenerate={onRegenerate} />
        ) : tab === "curve" ? (
          <CurveChart curves={toCurveEntries(result.runs)} combined />
        ) : (
          <FieldPanel runs={result.runs} />
        )}

        {showMetrics && (
          <aside className="absolute bottom-0 right-0 top-3 z-10 w-60 overflow-y-auto rounded-md border border-outline-variant bg-surface-container-low p-2.5 shadow-lg duration-200 animate-in slide-in-from-right-4 fade-in motion-reduce:animate-none">
            <h3 className="mb-2 text-[11px] font-bold uppercase tracking-wide">
              전기적 파라미터
            </h3>
            <MetricTable session={session} />
          </aside>
        )}
      </div>
    </div>
  );
}

function MissingPlots({
  busy,
  onRegenerate,
}: {
  busy: boolean;
  onRegenerate: () => void;
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3">
      <p className="text-xs text-on-surface-variant">
        저장된 분석 결과가 있습니다. 그래프를 다시 생성하면 볼 수 있습니다.
      </p>
      <Button
        variant="outline"
        size="sm"
        className="gap-1.5 text-xs"
        disabled={busy}
        onClick={onRegenerate}
      >
        {busy ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none" />
        ) : (
          <RotateCcw className="h-3.5 w-3.5" />
        )}
        그래프 다시 생성
      </Button>
    </div>
  );
}

/**
 * Field Map은 실험 결과에 실려 오지 않는다. 조건이 곧 소자 파라미터라
 * 기존 Field Map 화면이 쓰는 API를 그대로 부르면 같은 결과가 나오고,
 * 덕분에 응답에서 3 MB를 덜어냈다.
 */
function FieldPanel({ runs }: { runs: ConditionRun[] }) {
  const [display, setDisplay] = useState<FieldDisplay>(FIELD_DISPLAYS[0]);
  const [meshes, setMeshes] = useState<Record<string, FieldResponse>>({});
  const [compareData, setCompareData] = useState<FieldCompareResponse | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  const devices = runs.map((run) => ({
    label: run.label,
    parameters: toParameters(run.conditions),
  }));
  const signature = JSON.stringify(devices);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    Promise.all(devices.map((device) => predictField(device.parameters)))
      .then((results) => {
        if (cancelled) return;
        setMeshes(
          Object.fromEntries(
            results.map((value, index) => [devices[index].label, value]),
          ),
        );
      })
      .catch(() => !cancelled && setError("Field Map을 불러오지 못했습니다."));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature]);

  useEffect(() => {
    if (display === "Mesh") {
      setCompareData(null);
      return;
    }
    let cancelled = false;
    fetchFieldDisplayCompare(
      devices.map((device) => ({ label: device.label, ...device.parameters })),
      display,
      "Auto",
      "Robust 1-99%",
    )
      .then((data) => !cancelled && setCompareData(data))
      .catch(() => !cancelled && setError("Field Map을 불러오지 못했습니다."));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature, display]);

  const ready = devices.every((device) => meshes[device.label]);

  return (
    <div className="flex h-full flex-col gap-2">
      <DisplayControls
        display={display}
        onDisplayChange={setDisplay}
        scaleMode="Auto"
        onScaleModeChange={() => {}}
        rangeMode="Robust 1-99%"
        onRangeModeChange={() => {}}
      />
      {error && <p className="text-[11px] text-destructive">{error}</p>}
      <div className="min-h-0 flex-1">
        {ready ? (
          <FieldCompareChart
            devices={devices.map((device) => ({
              label: device.label,
              mesh: meshes[device.label].mesh,
              toxNm: Number(device.parameters.T),
            }))}
            display={display}
            compareData={compareData}
          />
        ) : (
          <div className="flex h-full items-center justify-center">
            <Loader2 className="h-5 w-5 animate-spin text-on-surface-variant motion-reduce:animate-none" />
          </div>
        )}
      </div>
    </div>
  );
}

/** 기존 I-V 차트가 받는 모양으로 맞춘다 — 로그 축 전환과 색 배정이 그대로 온다. */
function toCurveEntries(runs: ConditionRun[]): CurveEntry[] {
  return runs.map((run, index) => ({
    id: index,
    label: run.label,
    visible: true,
    parameters: toParameters(run.conditions),
    result: {
      idvd: run.idvd as CurveEntry["result"] extends null ? never : never,
      idvg: run.idvg,
      electrical_parameters: {},
      range_warning: "",
    } as NonNullable<CurveEntry["result"]>,
  }));
}

/** 케이스 조건은 숫자, 소자 파라미터 API는 문자열을 받는다. */
function toParameters(conditions: Record<string, number>): DeviceParameters {
  return {
    L: String(conditions.L),
    T: String(conditions.T),
    B: String(conditions.B),
    SD: String(conditions.SD),
    LDD: String(conditions.LDD),
  };
}
