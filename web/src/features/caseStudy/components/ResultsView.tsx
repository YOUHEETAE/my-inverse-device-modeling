import { useEffect, useMemo, useState, type ReactNode } from "react";
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
import { EnergyBandChart } from "@/features/fields/components/EnergyBandChart";
import { EnergyBandLegend } from "@/features/fields/components/EnergyBandLegend";
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
  // 한 번이라도 연 탭은 계속 마운트해 둔다. 탭을 옮길 때마다 언마운트되면
  // Field Map은 소자마다 예측을 다시 부르고, 자유질문은 오가던 대화가
  // 사라진다. 처음부터 전부 마운트하지 않는 이유는, 열어보지도 않은 탭의
  // 예측 호출까지 미리 나가기 때문이다 (ToolPanel과 같은 규칙).
  const [visited, setVisited] = useState<Set<TabId>>(() => new Set<TabId>(["curve"]));
  // 지표 표는 그래프를 밀어내지 않고 그 위에 뜬다. 나란히 두면 셋이 폭을
  // 나눠 갖느라 그래프가 눌리고, 표를 접었다 펼 때마다 그래프 크기가 바뀌어
  // 방금 보던 모양과 달라진다. 덮어두면 그래프는 늘 같은 크기다.
  const [showMetrics, setShowMetrics] = useState(true);

  function openTab(id: TabId) {
    setTab(id);
    setVisited((prev) => (prev.has(id) ? prev : new Set(prev).add(id)));
  }

  const { runs, labelMap } = useMemo(() => describeRuns(result?.runs ?? []), [result]);

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
            onClick={() => openTab(id)}
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
        {/* 감춘 탭도 부모와 같은 크기의 상자를 그대로 유지한다. display:none으로
            숨기면 Plotly가 폭 0을 보고 다시 돌아왔을 때 찌그러진 채로 남는다. */}
        <div className="relative h-full">
          {visited.has("curve") && (
            <Panel active={tab === "curve"}>
              {result ? (
                <CurveChart curves={toCurveEntries(runs)} combined />
              ) : (
                <MissingPlots busy={busy} onRegenerate={onRegenerate} />
              )}
            </Panel>
          )}
          {visited.has("field") && (
            <Panel active={tab === "field"}>
              {result ? (
                <FieldPanel runs={runs} />
              ) : (
                <MissingPlots busy={busy} onRegenerate={onRegenerate} />
              )}
            </Panel>
          )}
          {visited.has("chat") && (
            <Panel active={tab === "chat"}>
              <CaseFollowupChat session={session} />
            </Panel>
          )}
        </div>

        {showMetrics && (
          <aside className="absolute bottom-0 right-0 top-3 z-10 w-60 overflow-y-auto rounded-md border border-outline-variant bg-surface-container-low p-2.5 shadow-lg duration-200 animate-in slide-in-from-right-4 fade-in motion-reduce:animate-none">
            <h3 className="mb-2 text-[11px] font-bold uppercase tracking-wide">
              전기적 파라미터
            </h3>
            <MetricTable session={session} labels={labelMap} />
          </aside>
        )}
      </div>
    </div>
  );
}

/**
 * 탭 하나. 감춰도 마운트와 크기를 유지한다 — 상태를 잃지 않으면서 차트가
 * 폭 0을 보는 일도 없게 하려는 것이다.
 */
function Panel({ active, children }: { active: boolean; children: ReactNode }) {
  return (
    <div
      className={cn("absolute inset-0", !active && "invisible pointer-events-none")}
      aria-hidden={!active}
    >
      {children}
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
    // 표시를 바꾸면 앞선 실패는 지나간 얘기가 된다. 남겨두면 정상으로 그려진
    // 화면 위에 "불러오지 못했습니다"가 계속 붙어 있다.
    setError(null);
    // Mesh는 구조만 그리고, Energy band는 비교 API가 아니라 각 소자의
    // Potential에서 직접 계산한다 — 둘 다 여기서 부를 것이 없다.
    if (display === "Mesh" || display === ENERGY_BAND) {
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
          display === ENERGY_BAND ? (
            // 독립 Field Map 화면과 같은 분기다. 여기에 이 갈래가 없어서
            // 비교 API를 부르다 실패했고, 그림도 나오지 않았다.
            <div className="flex h-full flex-col gap-2">
              <div className="min-h-0 flex-1">
                <EnergyBandChart
                  devices={devices.map((device) => ({
                    label: device.label,
                    mesh: meshes[device.label].mesh,
                    potential: meshes[device.label].node_fields["Potential"],
                    lengthNm: Number(device.parameters.L),
                    toxNm: Number(device.parameters.T),
                  }))}
                />
              </div>
              {/* 차트가 자기 범례를 그리지 않아(showlegend: false) 색이 무엇을
                  뜻하는지 밖에서 알려줘야 한다. */}
              <div className="shrink-0 rounded-md border border-outline-variant bg-surface-container">
                <EnergyBandLegend />
              </div>
            </div>
          ) : (
            <FieldCompareChart
              devices={devices.map((device) => ({
                label: device.label,
                mesh: meshes[device.label].mesh,
                toxNm: Number(device.parameters.T),
              }))}
              display={display}
              compareData={compareData}
            />
          )
        ) : (
          <div className="flex h-full items-center justify-center">
            <Loader2 className="h-5 w-5 animate-spin text-on-surface-variant motion-reduce:animate-none" />
          </div>
        )}
      </div>
    </div>
  );
}

// 다른 표시들과 달리 서버의 비교 API를 쓰지 않고 Potential에서 계산한다.
// FieldDisplay로 좁혀 두면 목록에 없는 이름을 적었을 때 컴파일에서 걸린다.
const ENERGY_BAND: FieldDisplay = "Energy band (1D)";

const CONDITION_UNITS: Record<string, string> = {
  L: "nm",
  T: "nm",
  B: "cm⁻³",
  SD: "cm⁻³",
  LDD: "cm⁻³",
};

// 케이스가 두 조건에 붙여둔 기본 이름. 무엇이 다른지 알려주지 않으므로
// 값으로 대체한다. 6~8번 Case처럼 "Short·Thick", "Control" 같은 이름을
// 따로 지어둔 경우는 뜻이 담겨 있어서 남긴다.
const GENERIC_LABELS = new Set(["Baseline", "Comparison"]);

// 범례 한 줄에 값을 몇 개까지 넣을지. 후보군을 고르는 Case는 다섯 조건이
// 한꺼번에 달라서 전부 적으면 범례가 읽을 수 없게 길어진다. 그런 Case는
// 원래 이름("Drive", "Balanced")이 이미 뜻을 담고 있고 숫자는 조건표에 있다.
const MAX_LABELLED_CONDITIONS = 2;

/**
 * 조건을 이름으로 바꾼다. "Baseline / Comparison"만 보면 무엇이 얼마나
 * 달라졌는지 알 수 없어서, 실제로 값이 갈리는 조건을 그대로 이름에 쓴다.
 *
 * 무엇이 갈리는지는 케이스 설정이 아니라 화면에 함께 놓인 실행들에서 찾는다.
 * changed_parameters는 baseline과 comparison 사이만 가리켜서, 소자를 넷
 * 비교하는 Case에서는 나머지 축을 놓친다 — Channel Length와 Oxide Thickness를
 * 함께 보는 Case가 전부 "10 nm"와 "20 nm" 두 이름으로 겹쳐버린다.
 */
function describeRuns(runs: ConditionRun[]): {
  runs: ConditionRun[];
  labelMap: Record<string, string>;
} {
  if (runs.length === 0) return { runs, labelMap: {} };

  const varying = Object.keys(runs[0].conditions).filter(
    (key) => new Set(runs.map((run) => run.conditions[key])).size > 1,
  );

  // 이름이 이미 뜻을 담고 있고 조건이 너무 많이 갈리면 값을 적지 않는다.
  const named = !GENERIC_LABELS.has(runs[0].label);
  const shown = named && varying.length > MAX_LABELLED_CONDITIONS ? [] : varying;

  const labelMap: Record<string, string> = {};
  const renamed = runs.map((run) => {
    const values = shown
      .map((key) => formatCondition(key, run.conditions[key]))
      .join(" · ");
    const label = !values
      ? run.label
      : GENERIC_LABELS.has(run.label)
        ? values
        : `${values} · ${run.label}`;
    labelMap[run.label] = label;
    return { ...run, label };
  });

  return { runs: renamed, labelMap };
}

function formatCondition(name: string, value: number): string {
  const unit = CONDITION_UNITS[name];
  // 도핑은 1e16처럼 지수로 읽는 값이고, 길이는 그냥 정수다.
  const text = Math.abs(value) >= 1e4 ? value.toExponential().replace("e+", "e") : String(value);
  return unit ? `${text} ${unit}` : text;
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
