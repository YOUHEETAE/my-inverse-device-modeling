import { useCallback, useEffect, useState } from "react";
import {
  beginPrediction,
  fetchSession,
  fetchTopic,
  getErrorMessage,
  recoverSession,
  regenerateExperiment,
  resetSession,
  runExperiment,
  submitObservations,
  submitPredictions,
  evaluateSession,
} from "./api";
import type { Answer } from "./components/QuestionCard";
import type { ExperimentResult, LearningPage, LearningSession, TopicDetail } from "./types";

/** 세션의 단계에서 기본으로 보여줄 페이지 (panel.py의 _default_learning_page). */
export function defaultPage(session: LearningSession | null): LearningPage {
  const step = stepOf(session);
  if (["INTRODUCTION", "BASELINE_SETUP"].includes(step)) return "understanding";
  if (["PREDICTION_QUESTION", "PREDICTION_SUBMITTED", "SIMULATION_RUNNING"].includes(step)) {
    return "prediction";
  }
  if (["RESULT_READY", "OBSERVATION_QUESTION", "OBSERVATION_SUBMITTED"].includes(step)) {
    return "observation";
  }
  return "explanation";
}

/**
 * 되돌아가 볼 수 있는 페이지인지 (panel.py의 _is_learning_page_unlocked).
 *
 * 단계만 보지 않고 남아 있는 답변·분석·피드백도 함께 본다 — 완료한 세션을
 * 다시 열었을 때 앞 단계를 못 보면 복습이 안 된다.
 */
export function isUnlocked(session: LearningSession | null, page: LearningPage): boolean {
  if (!session) return page === "understanding";
  const step = stepOf(session);
  if (page === "understanding") return true;
  if (page === "prediction") {
    return has(session, "prediction_answers") || !["INTRODUCTION", "BASELINE_SETUP"].includes(step);
  }
  if (page === "observation") {
    return (
      has(session, "analysis_snapshot") ||
      [
        "RESULT_READY",
        "OBSERVATION_QUESTION",
        "OBSERVATION_SUBMITTED",
        "FEEDBACK_READY",
        "NEXT_EXPERIMENT",
        "SESSION_COMPLETE",
      ].includes(step)
    );
  }
  return (
    has(session, "feedback_snapshot") ||
    has(session, "summary_snapshot") ||
    ["FEEDBACK_READY", "NEXT_EXPERIMENT", "SESSION_COMPLETE"].includes(step)
  );
}

/** ERROR면 실패 직전 단계를 기준으로 본다 — 그래야 복구 후 갈 곳이 맞다. */
export function stepOf(session: LearningSession | null): string {
  if (!session) return "INTRODUCTION";
  const step = String(session.current_step);
  if (step !== "ERROR") return step;
  return String(session.recovery_step ?? "INTRODUCTION");
}

function has(session: LearningSession, key: string): boolean {
  const value = session[key];
  if (Array.isArray(value)) return value.length > 0;
  if (value && typeof value === "object") return Object.keys(value).length > 0;
  return false;
}

/**
 * 케이스 한 판의 상태.
 *
 * 세션은 서버가 보관하므로 여기서는 sessionId만 들고 다니고, 걸음마다 서버가
 * 돌려준 세션으로 갈아 끼운다. 곡선만 예외인데, 세션에 저장하지 않아서
 * 실행할 때 받아 화면에서만 들고 있는다 — 새로고침하면 다시 만들어야 한다.
 */
export function useCaseSession(sessionId: string) {
  const [session, setSession] = useState<LearningSession | null>(null);
  const [topic, setTopic] = useState<TopicDetail | null>(null);
  const [result, setResult] = useState<ExperimentResult | null>(null);
  const [page, setPage] = useState<LearningPage | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setResult(null);
    setPage(null);
    fetchSession(sessionId)
      .then(async (loaded) => {
        if (cancelled) return;
        setSession(loaded);
        setTopic(await fetchTopic(String(loaded.topic_id)));
      })
      .catch((err) => !cancelled && setError(getErrorMessage(err)));
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  // 서버 호출은 전부 같은 모양이다: 진행 중 표시를 켜고, 돌아온 세션으로
  // 갈아 끼우고, 실패하면 이유를 남긴다.
  const run = useCallback(async <T,>(task: () => Promise<T>, apply: (value: T) => void) => {
    setBusy(true);
    setError(null);
    try {
      apply(await task());
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }, []);

  const view = page ?? defaultPage(session);

  return {
    session,
    topic,
    result,
    busy,
    error,
    page: view,
    /** 잠긴 페이지로는 넘어가지 않는다. */
    setPage: (next: LearningPage) => isUnlocked(session, next) && !busy && setPage(next),
    dismissError: () => setError(null),

    begin: () =>
      run(() => beginPrediction(sessionId), (next) => {
        setSession(next);
        setPage("prediction");
      }),

    /**
     * 예측 제출과 실험 실행은 나뉘어 있다. 서버가 그 사이에 저장하기 때문에
     * 실험이 실패해도 적어둔 답은 남고, 다시 실행만 하면 된다.
     */
    submitPrediction: (answers: Record<string, Answer>) =>
      run(
        async () => {
          await submitPredictions(sessionId, answers);
          return runExperiment(sessionId);
        },
        (reply) => {
          setSession(reply.session);
          setResult(reply.result);
          setPage("observation");
        },
      ),

    /** 실험만 다시. 제출은 이미 저장돼 있어 답변을 다시 적을 필요가 없다. */
    retryExperiment: () =>
      run(() => runExperiment(sessionId), (reply) => {
        setSession(reply.session);
        setResult(reply.result);
      }),

    submitObservation: (answers: Record<string, Answer>) =>
      run(
        async () => {
          await submitObservations(sessionId, answers);
          return evaluateSession(sessionId);
        },
        (next) => {
          setSession(next);
          setPage("explanation");
        },
      ),

    /** 채점만 다시 (panel.py의 _resume_evaluation). */
    retryEvaluation: () =>
      run(() => evaluateSession(sessionId), (next) => {
        setSession(next);
        setPage("explanation");
      }),

    /** 곡선은 세션에 없어서 다시 열면 만들어야 한다. */
    regenerate: () => run(() => regenerateExperiment(sessionId), setResult),

    reset: () =>
      run(() => resetSession(sessionId), (next) => {
        setSession(next);
        setResult(null);
        setPage("understanding");
      }),

    recover: () =>
      run(() => recoverSession(sessionId), (next) => {
        setSession(next);
        setPage(defaultPage(next));
      }),
  };
}
