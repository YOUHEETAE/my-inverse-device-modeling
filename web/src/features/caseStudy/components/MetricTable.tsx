import { ELECTRICAL_PARAMETERS } from "@/features/curves/types";
import type { LearningSession } from "../types";

/**
 * 조건별 전기적 파라미터 비교 (panel.py의 _build_parameter_table).
 *
 * 곡선과 달리 이 값은 세션에 남는다 — analysis_snapshot에 들어 있어서
 * 저장된 세션을 다시 열어도 표는 그대로 보인다. 지표 목록은 I-V 화면이
 * 쓰는 것과 같은 것을 재사용한다(키·단위·배율이 동일).
 */
export function MetricTable({ session }: { session: LearningSession }) {
  const display = displayParameters(session);
  if (!display) {
    return <p className="text-[11px] text-on-surface-variant">분석 결과를 복원할 수 없습니다.</p>;
  }

  const { baseline, comparison } = display;

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[11px]">
        <thead>
          <tr className="border-b border-outline-variant text-on-surface-variant">
            <th className="py-1 pr-2 text-left font-medium">Metric</th>
            <th className="py-1 px-1 text-right font-medium">{baseline.label}</th>
            <th className="py-1 px-1 text-right font-medium">{comparison.label}</th>
            <th className="py-1 pl-1 text-center font-medium">변화</th>
          </tr>
        </thead>
        <tbody className="tabular-nums">
          {ELECTRICAL_PARAMETERS.map(({ key, label, unit, scale }) => {
            const before = scaled(baseline.values[key], scale);
            const after = scaled(comparison.values[key], scale);
            return (
              <tr key={key} className="border-b border-outline-variant/50 last:border-0">
                <td className="py-1 pr-2">
                  {label}
                  {unit && <span className="text-on-surface-variant"> ({unit})</span>}
                </td>
                <td className="py-1 px-1 text-right text-on-surface-variant">{format(before)}</td>
                <td className="py-1 px-1 text-right">{format(after)}</td>
                <td className="py-1 pl-1 text-center">{direction(before, after)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

interface DisplayGroup {
  label: string;
  values: Record<string, number>;
}

function displayParameters(
  session: LearningSession,
): { baseline: DisplayGroup; comparison: DisplayGroup } | null {
  const snapshot = session.analysis_snapshot as { experiment?: Record<string, unknown> } | undefined;
  const display = snapshot?.experiment?.display_electrical_parameters as
    | { baseline?: DisplayGroup; comparison?: DisplayGroup }
    | undefined;
  if (!display?.baseline || !display?.comparison) return null;
  return { baseline: display.baseline, comparison: display.comparison };
}

function scaled(value: number | undefined, factor: number): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value * factor : null;
}

/** 값을 못 뽑은 지표는 빈칸이 아니라 확인 불가로 둔다. */
function format(value: number | null): string {
  if (value === null) return "—";
  if (value !== 0 && (Math.abs(value) >= 1e4 || Math.abs(value) < 1e-3)) {
    return value.toExponential(2).replace("e+", "e");
  }
  return value.toFixed(4).replace(/\.?0+$/, "");
}

function direction(before: number | null, after: number | null): string {
  if (before === null || after === null) return "—";
  if (after > before) return "↑";
  if (after < before) return "↓";
  return "→";
}
