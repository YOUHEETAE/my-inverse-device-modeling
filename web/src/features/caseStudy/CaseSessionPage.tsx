import { ArrowLeft, Loader2, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { QuestionCard, missingAnswer, EMPTY_ANSWER, type Answer } from "./components/QuestionCard";
import { ResultsView } from "./components/ResultsView";
import { UnderstandingPage } from "./components/UnderstandingPage";
import { isUnlocked, stepOf, useCaseSession } from "./useCaseSession";
import { LEARNING_PAGES, type LearningPage } from "./types";
import { useState } from "react";

interface CaseSessionPageProps {
  sessionId: string;
  caseNumber: number;
  onBack: () => void;
}

/**
 * 케이스 한 판. 데스크톱 앱과 같은 4단계다 (panel.py의 render).
 *
 * 어느 화면을 그릴지는 세션의 단계가 정한다 — 답변을 제출했는지, 실험이
 * 끝났는지, 채점이 끝났는지. 프론트가 따로 진행 상태를 들고 있지 않아서
 * 새로고침해도 같은 자리로 돌아온다.
 */
export default function CaseSessionPage({ sessionId, caseNumber, onBack }: CaseSessionPageProps) {
  const state = useCaseSession(sessionId);
  const { session, topic, page, busy, error } = state;

  if (!session || !topic) {
    return (
      <div className="flex h-full items-center justify-center">
        {error ? (
          <p className="text-xs text-destructive">{error}</p>
        ) : (
          <Loader2 className="h-5 w-5 animate-spin text-on-surface-variant motion-reduce:animate-none" />
        )}
      </div>
    );
  }

  const step = String(session.current_step);

  return (
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 items-center gap-3 border-b border-outline-variant px-4 py-2">
        <Button variant="ghost" size="sm" className="h-7 gap-1 px-2 text-xs" onClick={onBack}>
          <ArrowLeft className="h-3.5 w-3.5" />
          Case 목록
        </Button>
        <span className="font-mono text-[10px] uppercase tracking-wider text-on-surface-variant">
          Case {String(caseNumber).padStart(2, "0")}
        </span>
        <h1 className="min-w-0 truncate text-xs font-bold">{topic.title}</h1>
        <div className="ml-auto flex items-center gap-2">
          {busy && (
            <Loader2 className="h-3.5 w-3.5 animate-spin text-on-surface-variant motion-reduce:animate-none" />
          )}
          <Button
            variant="ghost"
            size="sm"
            className="h-7 gap-1 px-2 text-[10px] uppercase text-on-surface-variant"
            disabled={busy}
            onClick={state.reset}
          >
            <RotateCcw className="h-3 w-3" />
            처음부터
          </Button>
        </div>
      </div>

      <StepNav session={session} current={page} onSelect={state.setPage} disabled={busy} />

      {error && (
        <p className="shrink-0 border-b border-outline-variant bg-destructive/10 px-4 py-1.5 text-[11px] text-destructive">
          {error}
        </p>
      )}

      <div
        className={cn(
          "min-h-0 flex-1 p-4",
          // 관찰 화면은 안에서 각자 스크롤한다. 바깥이 스크롤하면 그래프가
          // 세로로 눌려서 읽을 수 없게 된다.
          page === "observation" && step !== "ERROR" ? "overflow-hidden" : "overflow-y-auto",
        )}
      >
        {step === "ERROR" ? (
          <RecoveryNotice onRetry={state.recover} busy={busy} />
        ) : (
          <PageBody state={state} page={page} />
        )}
      </div>
    </div>
  );
}

/**
 * 4단계 진행 표시. 잠긴 단계는 누를 수 없고 막대도 회색이다 — 답변이나
 * 결과가 남아 있으면 지나온 단계로는 돌아가 볼 수 있다.
 */
function StepNav({
  session,
  current,
  onSelect,
  disabled,
}: {
  session: Parameters<typeof isUnlocked>[0];
  current: LearningPage;
  onSelect: (page: LearningPage) => void;
  disabled: boolean;
}) {
  return (
    <nav className="flex shrink-0 border-b border-outline-variant">
      {LEARNING_PAGES.map(({ id, label }) => {
        const unlocked = isUnlocked(session, id);
        return (
          <button
            key={id}
            type="button"
            disabled={!unlocked || disabled}
            aria-current={current === id ? "step" : undefined}
            onClick={() => onSelect(id)}
            className={cn(
              "flex-1 border-b-2 px-3 py-2 text-xs transition-colors motion-reduce:transition-none",
              current === id
                ? "border-primary font-bold text-primary"
                : unlocked
                  ? "border-transparent text-on-surface-variant hover:text-on-surface"
                  : "cursor-not-allowed border-transparent text-on-surface-variant/40",
            )}
          >
            {label}
            {!unlocked && " · 잠김"}
          </button>
        );
      })}
    </nav>
  );
}

function PageBody({
  state,
  page,
}: {
  state: ReturnType<typeof useCaseSession>;
  page: LearningPage;
}) {
  const { session, topic } = state;
  if (!session || !topic) return null;
  const step = stepOf(session);

  if (page === "understanding") {
    return (
      <UnderstandingPage
        topic={topic}
        canBegin={["INTRODUCTION", "BASELINE_SETUP"].includes(step)}
        busy={state.busy}
        onBegin={state.begin}
      />
    );
  }

  if (page === "prediction") {
    if (step === "PREDICTION_QUESTION") {
      return (
        <AnswerForm
          heading="결과를 실행하기 전에 예상해보세요."
          questions={topic.prediction_questions}
          submitLabel="예측 제출 후 모델 실행"
          busy={state.busy}
          onSubmit={state.submitPrediction}
        />
      );
    }
    // 예측은 저장됐는데 실험이 아직인 상태. 실패한 뒤라면 답변을 다시 적을
    // 필요 없이 실행만 다시 하면 된다.
    if (step === "PREDICTION_SUBMITTED" || step === "SIMULATION_RUNNING") {
      return <Pending label="모델을 실행하는 중입니다." busy={state.busy} onRetry={state.retryExperiment} />;
    }
    return <SubmittedAnswers session={session} field="prediction_answers" questions={topic.prediction_questions} />;
  }

  if (page === "observation") {
    // 결과를 보면서 답해야 하는 단계라 그래프와 질문이 나란히 놓인다.
    // 답을 낸 뒤에도 그래프는 남는다 — 피드백을 읽으며 다시 보게 된다.
    return (
      <div className="flex h-full min-h-0 gap-3">
        <div className="min-w-0 flex-1">
          <ResultsView
            session={session}
            result={state.result}
            busy={state.busy}
            onRegenerate={state.regenerate}
          />
        </div>
        {/* w-80: 질문은 세로로 길어서 폭보다 높이가 중요하다. 남는 폭은
            그래프로 넘긴다. */}
        <div className="w-80 shrink-0 overflow-y-auto pr-1">
          {step === "OBSERVATION_QUESTION" ? (
            <AnswerForm
              heading="그래프와 Field Map을 관찰한 뒤 답하세요."
              questions={topic.observation_questions}
              submitLabel="관찰 답변 제출"
              busy={state.busy}
              onSubmit={state.submitObservation}
            />
          ) : step === "OBSERVATION_SUBMITTED" ? (
            <Pending
              label="답변을 채점하고 피드백을 만드는 중입니다."
              busy={state.busy}
              onRetry={state.retryEvaluation}
            />
          ) : (
            <SubmittedAnswers
              session={session}
              field="observation_answers"
              questions={topic.observation_questions}
            />
          )}
        </div>
      </div>
    );
  }

  return <FeedbackPlaceholder />;
}

function AnswerForm({
  heading,
  questions,
  submitLabel,
  busy,
  onSubmit,
}: {
  heading: string;
  questions: import("./types").SafeQuestion[];
  submitLabel: string;
  busy: boolean;
  onSubmit: (answers: Record<string, Answer>) => void;
}) {
  const [answers, setAnswers] = useState<Record<string, Answer>>({});
  const [warning, setWarning] = useState<string | null>(null);

  function submit() {
    const problem = missingAnswer(questions, answers);
    setWarning(problem);
    if (!problem) onSubmit(answers);
  }

  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-sm font-bold">{heading}</h2>
      {questions.map((question) => (
        <QuestionCard
          key={question.question_id}
          question={question}
          answer={answers[question.question_id] ?? EMPTY_ANSWER}
          disabled={busy}
          onChange={(answer) =>
            setAnswers((previous) => ({ ...previous, [question.question_id]: answer }))
          }
        />
      ))}
      {warning && <p className="text-[11px] text-destructive">{warning}</p>}
      <Button className="self-end text-xs" disabled={busy} onClick={submit}>
        {submitLabel}
      </Button>
    </div>
  );
}

/** 제출한 답변을 다시 볼 때 (panel.py의 _build_answer_review). */
function SubmittedAnswers({
  session,
  field,
  questions,
}: {
  session: import("./types").LearningSession;
  field: string;
  questions: import("./types").SafeQuestion[];
}) {
  const records = (session[field] as { question_id: string; raw_answer: Answer }[] | undefined) ?? [];
  // 같은 질문을 다시 답했으면 마지막 답이 유효하다.
  const latest = new Map<string, Answer>();
  for (const record of records) latest.set(record.question_id, record.raw_answer);

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-3">
      <h2 className="text-sm font-bold">내가 제출한 답변</h2>
      {questions.map((question) => {
        const answer = latest.get(question.question_id);
        return (
          <section
            key={question.question_id}
            className="rounded-md border border-outline-variant bg-surface-container-low p-3"
          >
            <p className="text-xs font-bold leading-relaxed">{question.prompt}</p>
            <p className="mt-2 text-xs text-primary">{answer?.selected.join(", ") || "—"}</p>
            {answer?.reason && (
              <p className="mt-1 whitespace-pre-wrap text-[11px] leading-relaxed text-on-surface-variant">
                {answer.reason}
              </p>
            )}
          </section>
        );
      })}
    </div>
  );
}

function Pending({ label, busy, onRetry }: { label: string; busy: boolean; onRetry: () => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3">
      <Loader2
        className={cn(
          "h-5 w-5 text-on-surface-variant",
          busy && "animate-spin motion-reduce:animate-none",
        )}
      />
      <p className="text-xs text-on-surface-variant">{label}</p>
      {/* 저장된 답변은 그대로라 실행만 다시 하면 된다. */}
      {!busy && (
        <Button variant="outline" size="sm" className="gap-1.5 text-xs" onClick={onRetry}>
          <RotateCcw className="h-3.5 w-3.5" />
          다시 실행
        </Button>
      )}
    </div>
  );
}

// 실험이나 채점이 실패해 세션이 멈춘 상태. 적어둔 답변은 남아 있다.
function RecoveryNotice({ onRetry, busy }: { onRetry: () => void; busy: boolean }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3">
      <p className="text-xs text-on-surface-variant">
        학습 흐름이 중단되었습니다. 저장된 답변은 그대로 있습니다.
      </p>
      <Button variant="outline" size="sm" className="gap-1.5 text-xs" disabled={busy} onClick={onRetry}>
        <RotateCcw className="h-3.5 w-3.5" />
        이어서 다시 시도
      </Button>
    </div>
  );
}

function FeedbackPlaceholder() {
  return (
    <p className="text-center text-xs text-on-surface-variant">
      최종 설명 화면은 준비 중입니다.
    </p>
  );
}
