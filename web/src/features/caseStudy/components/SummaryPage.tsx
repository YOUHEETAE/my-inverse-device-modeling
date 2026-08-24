import { ELECTRICAL_PARAMETERS } from "@/features/curves/types";
import type { Answer } from "./QuestionCard";
import type { LearningSession, SafeQuestion, TopicDetail } from "../types";

/** 채점 결과. Python이 세션에 남겨둔 모양 그대로 읽는다. */
interface Feedback {
  headline?: string;
  summary?: string;
  positive_feedback?: string[];
  corrections?: string[];
  model_answer?: string;
  curve_focus?: string;
  field_focus?: string;
}

interface Summary {
  headline?: string;
  understood_concepts?: string[];
  detected_misconceptions?: string[];
  needs_review?: boolean;
}

/**
 * "4. 최종 설명"의 학습 요약 탭 (panel.py의 _build_complete).
 *
 * 내용은 전부 세션에 있다 — 채점과 피드백은 제출할 때 한 번 만들어져
 * feedback_snapshot / summary_snapshot으로 저장되므로, 다시 열어도 같은
 * 글이 나오고 LLM을 다시 부르지 않는다.
 */
export function SummaryPage({ session, topic }: { session: LearningSession; topic: TopicDetail }) {
  const feedback = (session.feedback_snapshot as Feedback | undefined) ?? {};
  const summary = (session.summary_snapshot as Summary | undefined) ?? {};

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4">
      <h2 className="text-base font-bold">{summary.headline || `${topic.title} 완료`}</h2>

      {topic.core_summary.length > 0 && (
        <Section title="핵심 정리">
          <ul className="space-y-1.5">
            {topic.core_summary.map((line) => (
              <li key={line} className="text-xs leading-relaxed">
                · {line}
              </li>
            ))}
          </ul>
        </Section>
      )}

      <Section title="초기 예측 → 실제 결과">
        <p className="mb-3 text-[11px] text-on-surface-variant">{topic.comparison_caption}</p>
        <div className="space-y-2">
          {topic.prediction_questions.map((question) => (
            <ReviewCard
              key={question.question_id}
              question={question}
              answer={answerFor(session, "prediction_answers", question.question_id)}
              session={session}
            />
          ))}
        </div>
      </Section>

      <Section title="결과를 보고 제출한 관찰">
        <div className="space-y-2">
          {topic.observation_questions.map((question) => (
            <ReviewCard
              key={question.question_id}
              question={question}
              answer={answerFor(session, "observation_answers", question.question_id)}
              session={session}
            />
          ))}
        </div>
      </Section>

      {feedback.model_answer && (
        <Section title="모범 답안">
          <ModelAnswer text={feedback.model_answer} titles={topic.model_answer_sections} />
        </Section>
      )}

      <Section title="내 학습 피드백">
        {feedback.headline && <p className="mb-3 text-xs font-bold">{feedback.headline}</p>}
        <div className="grid gap-3 md:grid-cols-2">
          <FeedbackColumn
            title="잘 이해한 부분"
            lines={humanize(feedback.positive_feedback ?? summary.understood_concepts, topic)}
            empty="확인된 이해 항목이 없습니다."
          />
          <FeedbackColumn
            title="보완할 부분"
            lines={humanize(feedback.corrections ?? summary.detected_misconceptions, topic)}
            empty="추가 보완 사항 없음"
          />
        </div>

        {(actionable(feedback.curve_focus) || actionable(feedback.field_focus)) && (
          <div className="mt-3 rounded-md border border-outline-variant p-3">
            <h4 className="mb-2 text-[11px] font-bold">다시 확인할 근거</h4>
            {actionable(feedback.curve_focus) && (
              <FocusRow title="I–V Curve에서 확인" text={feedback.curve_focus!} />
            )}
            {actionable(feedback.field_focus) && (
              <FocusRow title="Field Map에서 확인" text={feedback.field_focus!} />
            )}
          </div>
        )}
      </Section>
    </div>
  );
}

/**
 * 질문 하나를 되짚는 카드: 내 답과 그 질문이 겨눈 지표의 실제 변화.
 *
 * 정답 자체는 내려오지 않는다. 맞았는지 틀렸는지는 LLM 채점이 피드백으로
 * 말해주고, 여기서는 무엇을 답했고 결과가 어땠는지를 나란히 보여준다.
 */
function ReviewCard({
  question,
  answer,
  session,
}: {
  question: SafeQuestion;
  answer: Answer | undefined;
  session: LearningSession;
}) {
  const metrics = question.review_metrics
    .map((key) => metricRow(session, key))
    .filter((row): row is MetricRow => row !== null);

  return (
    <div className="rounded-md border border-outline-variant bg-surface-container p-3">
      <h4 className="text-[11px] font-bold text-on-surface-variant">
        {question.review_title || question.prompt}
      </h4>
      <p className="mt-1 text-xs leading-relaxed">{question.prompt}</p>

      <p className="mt-2 text-xs">
        <span className="text-on-surface-variant">내 답변 · </span>
        <span className="text-primary">{answer?.selected.join(", ") || "—"}</span>
      </p>
      {answer?.reason && (
        <p className="mt-1 whitespace-pre-wrap text-[11px] leading-relaxed text-on-surface-variant">
          {answer.reason}
        </p>
      )}

      {metrics.length > 0 && (
        <table className="mt-2 w-full border-collapse text-[11px] tabular-nums">
          <tbody>
            {metrics.map((row) => (
              <tr key={row.label} className="border-t border-outline-variant/50">
                <td className="py-1 pr-2 text-on-surface-variant">{row.label}</td>
                <td className="py-1 px-1 text-right text-on-surface-variant">{row.before}</td>
                <td className="py-1 px-1 text-center">→</td>
                <td className="py-1 pl-1 text-right font-bold">{row.after}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

/**
 * 모범 답안은 한 덩어리 글로 오고, 섹션 제목이 줄 머리에 들어 있다.
 * 제목 목록은 케이스 설정이 준다.
 */
function ModelAnswer({ text, titles }: { text: string; titles: Record<string, string> }) {
  const sections: { title: string | null; body: string[] }[] = [{ title: null, body: [] }];
  for (const line of text.split("\n")) {
    // 제목은 [대괄호]만 있는 줄로 온다 (panel.py의
    // split_model_answer_sections). 줄 머리 일치로 찾으면 대괄호 때문에
    // 하나도 걸리지 않아 글이 통째로 붙고 원문 제목이 그대로 노출된다.
    const heading = /^\[([^\]]+)\]\s*$/.exec(line.trim());
    if (heading) {
      const raw = heading[1].trim();
      // 화면용 이름으로 바꿔 단다 — "현재 Case의 I–V 근거" -> "I–V Curve에서
      // 확인된 근거". 목록에 없으면 원문을 그대로 쓴다.
      sections.push({ title: titles[raw] ?? raw, body: [] });
    } else if (line.trim()) {
      sections[sections.length - 1].body.push(line.trim());
    }
  }

  return (
    <div className="space-y-3">
      {sections
        .filter((section) => section.body.length > 0)
        .map((section, index) => (
          <div key={section.title ?? index}>
            {section.title && <h4 className="mb-1 text-[11px] font-bold">{section.title}</h4>}
            <p className="whitespace-pre-wrap text-xs leading-relaxed text-on-surface-variant">
              {section.body.join("\n")}
            </p>
          </div>
        ))}
    </div>
  );
}

function FeedbackColumn({ title, lines, empty }: { title: string; lines: string[]; empty: string }) {
  return (
    <div className="rounded-md border border-outline-variant p-3">
      <h4 className="mb-2 text-[11px] font-bold">{title}</h4>
      <ul className="space-y-1">
        {(lines.length > 0 ? lines : [empty]).map((line) => (
          <li key={line} className="text-[11px] leading-relaxed text-on-surface-variant">
            · {line}
          </li>
        ))}
      </ul>
    </div>
  );
}

function FocusRow({ title, text }: { title: string; text: string }) {
  return (
    <div className="flex gap-2 py-1">
      <span className="w-32 shrink-0 text-[11px] font-bold">{title}</span>
      <span className="text-[11px] leading-relaxed text-on-surface-variant">{text}</span>
    </div>
  );
}

interface MetricRow {
  label: string;
  before: string;
  after: string;
}

/** 질문이 겨눈 지표의 실제 변화. 값은 analysis_snapshot에 남아 있다. */
function metricRow(session: LearningSession, metricKey: string): MetricRow | null {
  const snapshot = session.analysis_snapshot as { experiment?: Record<string, unknown> } | undefined;
  const display = snapshot?.experiment?.display_electrical_parameters as
    | { baseline?: { values: Record<string, number> }; comparison?: { values: Record<string, number> } }
    | undefined;
  if (!display?.baseline || !display?.comparison) return null;

  // 질문은 "ion" 같은 짧은 이름을 쓰고, 값은 "ion_ma_per_um" 키로 저장된다.
  const spec = ELECTRICAL_PARAMETERS.find((item) => item.key.startsWith(metricKey));
  if (!spec) return null;

  const before = display.baseline.values[spec.key];
  const after = display.comparison.values[spec.key];
  if (typeof before !== "number" || typeof after !== "number") return null;

  return {
    label: `${spec.label}${spec.unit ? ` (${spec.unit})` : ""}`,
    before: format(before * spec.scale),
    after: format(after * spec.scale),
  };
}

function format(value: number): string {
  if (value !== 0 && (Math.abs(value) >= 1e4 || Math.abs(value) < 1e-3)) {
    return value.toExponential(2).replace("e+", "e");
  }
  return value.toFixed(4).replace(/\.?0+$/, "");
}

function answerFor(session: LearningSession, field: string, questionId: string): Answer | undefined {
  const records = (session[field] as { question_id: string; raw_answer: Answer }[] | undefined) ?? [];
  // 같은 질문을 다시 답했으면 마지막 답이 유효하다.
  return records.filter((record) => record.question_id === questionId).at(-1)?.raw_answer;
}

/**
 * 개념 id가 그대로 나오면 학습자가 읽을 수 없다.
 *
 * 채점 결과는 "ion_can_increase 개념을 확인했습니다."처럼 id를 문장 안에
 * 끼워 보내므로, 줄 전체를 키로 찾으면 안 되고 문장 안에서 바꿔줘야 한다
 * (panel.py의 _humanize_feedback_line).
 *
 * 긴 id부터 바꾼다 — 짧은 id가 긴 id의 앞부분과 겹치면 먼저 잘려 나간다.
 */
function humanize(lines: string[] | undefined, topic: TopicDetail): string[] {
  const entries = Object.entries(topic.concept_labels).sort(([a], [b]) => b.length - a.length);
  return (lines ?? [])
    .map((line) => entries.reduce((text, [id, label]) => text.split(id).join(label), String(line)))
    .filter((line) => line.trim().length > 0);
}

/** 비어 있거나 "없음"이 섞이면 칸을 만들지 않는다 (panel.py의 _focus_is_actionable). */
function actionable(value: string | undefined): boolean {
  const text = String(value ?? "").trim();
  return text.length > 0 && !text.includes("없음");
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-md border border-outline-variant bg-surface-container-low p-4">
      <h3 className="mb-2 text-xs font-bold uppercase tracking-wide">{title}</h3>
      {children}
    </section>
  );
}
