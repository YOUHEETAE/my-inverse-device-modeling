import { cn } from "@/lib/utils";
import type { SafeQuestion } from "../types";

/** 한 질문에 대한 학습자의 답. Python이 받는 모양 그대로. */
export interface Answer {
  selected: string[];
  reason: string;
}

export const EMPTY_ANSWER: Answer = { selected: [], reason: "" };

interface QuestionCardProps {
  question: SafeQuestion;
  answer: Answer;
  onChange: (answer: Answer) => void;
  disabled?: boolean;
}

/**
 * 예측·관찰 질문 한 장.
 *
 * 정답은 내려오지 않는다 — 서버가 correct_options를 빼고 보낸다. 채점은
 * 제출 뒤 LLM 튜터가 하고, 그 전에 정답을 볼 수 있으면 예측 단계 자체가
 * 의미를 잃는다.
 */
export function QuestionCard({ question, answer, onChange, disabled }: QuestionCardProps) {
  const single = question.type.startsWith("single_select");

  function toggle(option: string) {
    if (disabled) return;
    const selected = single
      ? [option]
      : answer.selected.includes(option)
        ? answer.selected.filter((item) => item !== option)
        : [...answer.selected, option];
    onChange({ ...answer, selected });
  }

  return (
    <fieldset className="rounded-md border border-outline-variant bg-surface-container-low p-3">
      <legend className="px-1 font-mono text-[10px] uppercase tracking-wider text-on-surface-variant">
        질문
      </legend>
      <p className="text-xs font-bold leading-relaxed">{question.prompt}</p>

      <div className="mt-2 space-y-1">
        {question.options.map((option) => {
          const checked = answer.selected.includes(option);
          return (
            <label
              key={option}
              className={cn(
                "flex cursor-pointer items-start gap-2 rounded-sm px-2 py-1.5 text-xs leading-relaxed",
                checked ? "bg-primary/10" : "hover:bg-surface-container",
                disabled && "cursor-default opacity-70",
              )}
            >
              <input
                type={single ? "radio" : "checkbox"}
                name={question.question_id}
                checked={checked}
                disabled={disabled}
                onChange={() => toggle(option)}
                className="mt-0.5 shrink-0 accent-[var(--color-primary)]"
              />
              <span>{option}</span>
            </label>
          );
        })}
      </div>

      {/* 근거가 필요한 질문은 선택만으로 제출되지 않는다 (panel.py의
          _collect_answers) — 왜 그렇게 생각했는지가 채점 대상이라서. */}
      {question.reason_required && (
        <label className="mt-3 block">
          <span className="text-[11px] text-on-surface-variant">근거</span>
          <textarea
            value={answer.reason}
            disabled={disabled}
            onChange={(event) => onChange({ ...answer, reason: event.target.value })}
            rows={3}
            className="mt-1 w-full resize-y rounded-md border border-outline-variant bg-surface-container-lowest px-2.5 py-1.5 text-xs leading-relaxed outline-none focus:border-primary disabled:opacity-60"
            placeholder="그렇게 생각한 이유를 적어주세요."
          />
        </label>
      )}
    </fieldset>
  );
}

/**
 * 제출 가능한지. 데스크톱과 같은 규칙 — 모든 질문에 하나 이상 선택,
 * 근거가 필요한 질문에는 근거까지.
 */
export function missingAnswer(
  questions: SafeQuestion[],
  answers: Record<string, Answer>,
): string | null {
  for (const question of questions) {
    const answer = answers[question.question_id] ?? EMPTY_ANSWER;
    if (answer.selected.length === 0) {
      return "각 질문에서 하나 이상의 답을 선택해주세요.";
    }
    if (question.reason_required && !answer.reason.trim()) {
      return "근거가 필요한 질문에 설명을 입력해주세요.";
    }
  }
  return null;
}
