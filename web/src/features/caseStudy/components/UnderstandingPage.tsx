import { Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { TopicDetail } from "../types";

interface UnderstandingPageProps {
  topic: TopicDetail;
  /** 아직 예측을 시작하지 않았을 때만 시작 버튼을 준다. */
  canBegin: boolean;
  busy: boolean;
  onBegin: () => void;
}

/**
 * "1. Case 이해" (panel.py의 _build_introduction).
 *
 * 배경·핵심 질문·학습 목표·확인할 근거는 케이스마다 손으로 쓴 안내문이고
 * (backend/learning/case_presentation.py), 오른쪽 조건표는 케이스 설정에서
 * 나온다.
 */
export function UnderstandingPage({ topic, canBegin, busy, onBegin }: UnderstandingPageProps) {
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="flex flex-col gap-3">
        <Section title="Case 배경">
          <p className="text-xs leading-relaxed text-on-surface-variant">{topic.guide.context}</p>
        </Section>

        <Section title="이번 Case의 핵심 질문">
          <p className="text-xs font-bold leading-relaxed text-primary">{topic.guide.question}</p>
        </Section>

        <Section title="학습 목표">
          <ul className="space-y-1.5">
            {topic.learning_objectives.map((objective) => (
              <li key={objective} className="text-xs leading-relaxed">
                · {objective}
              </li>
            ))}
          </ul>
        </Section>

        <Section title="결과에서 확인할 근거">
          <ul className="space-y-1.5">
            {topic.guide.evidence.map((item) => (
              <li key={item} className="text-xs leading-relaxed">
                · {item}
              </li>
            ))}
          </ul>
          <p className="mt-3 text-[11px] leading-relaxed text-on-surface-variant">
            해석할 때 주의: {topic.guide.caution}
          </p>
        </Section>
      </div>

      <div className="flex flex-col gap-3">
        <ConditionsTable topic={topic} />
        {canBegin && (
          <Button className="w-full gap-1.5 text-xs" disabled={busy} onClick={onBegin}>
            <Play className="h-3.5 w-3.5" />
            사전 예측 시작
          </Button>
        )}
        {topic.theory_reference && (
          <p className="text-[11px] leading-relaxed text-on-surface-variant">
            관련 이론 · {topic.theory_reference}
          </p>
        )}
      </div>
    </div>
  );
}

/**
 * 이번 Case의 실험 조건.
 *
 * 케이스마다 줄 수가 다르다 — 단일 파라미터 비교는 baseline/comparison 두
 * 줄이지만, 2x2나 후보군 비교는 reference 조건이 앞에 붙는다
 * (panel.py의 topic_condition_rows).
 */
function ConditionsTable({ topic }: { topic: TopicDetail }) {
  const columns = topic.display_parameters.length
    ? topic.display_parameters
    : Object.keys(topic.baseline_conditions);

  const rows = [
    ...topic.reference_conditions.map((item) => ({ label: item.label, conditions: item.conditions })),
    { label: topic.baseline_label, conditions: topic.baseline_conditions },
    { label: topic.comparison_label, conditions: topic.comparison_conditions },
  ];

  const changed = new Set(topic.changed_parameters);

  return (
    <Section title="이번 Case의 실험 조건">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[11px]">
          <thead>
            <tr className="border-b border-outline-variant text-on-surface-variant">
              <th className="py-1 pr-2 text-left font-medium">Condition</th>
              {columns.map((name) => (
                <th
                  key={name}
                  className={`py-1 px-1 text-right font-medium ${changed.has(name) ? "text-primary" : ""}`}
                >
                  {name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="tabular-nums">
            {rows.map((row) => (
              <tr key={row.label} className="border-b border-outline-variant/50 last:border-0">
                <td className="py-1 pr-2">{row.label}</td>
                {columns.map((name) => (
                  <td
                    key={name}
                    className={`py-1 px-1 text-right ${changed.has(name) ? "font-bold text-primary" : "text-on-surface-variant"}`}
                  >
                    {format(row.conditions[name])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-[11px] font-bold text-primary">
        변경 변수 · {topic.changed_parameters.map((name) => topic.parameter_labels[name] ?? name).join(" × ")}
      </p>
      <p className="mt-1 text-[11px] leading-relaxed text-on-surface-variant">
        고정 변수 ·{" "}
        {columns.filter((name) => !changed.has(name)).map((name) => topic.parameter_labels[name] ?? name).join(", ") ||
          "없음 (후보별 설계값 비교)"}
      </p>
    </Section>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-md border border-outline-variant bg-surface-container-low p-4">
      <h3 className="mb-2 text-xs font-bold uppercase tracking-wide">{title}</h3>
      {children}
    </section>
  );
}

/** 데스크톱과 같은 표기 — 큰 값은 지수로 (panel.py의 _format_compact_condition_value). */
function format(value: number | undefined): string {
  if (value === undefined) return "—";
  if (value !== 0 && Math.abs(value) >= 1e4) return value.toExponential(2).replace("e+", "e");
  return String(value);
}
