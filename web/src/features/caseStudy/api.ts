import { apiClient } from "@/lib/apiClient";
import { getErrorMessage } from "@/features/curves/api";
import type {
  ExperimentReply,
  ExperimentResult,
  LearningPortfolio,
  LearningSession,
  SessionSummary,
  TopicDetail,
  TopicSummary,
} from "./types";

export { getErrorMessage };

// 케이스 목록과 내용은 로그인 없이도 볼 수 있다. 기록이 남는 학습 세션만
// 로그인을 요구한다 (java_service의 SecurityConfig).
export async function fetchTopics() {
  const response = await apiClient.get<TopicSummary[]>("/case-study/topics");
  return response.data;
}

export async function fetchTopic(topicId: string) {
  const response = await apiClient.get<TopicDetail>(`/case-study/topics/${topicId}`);
  return response.data;
}

/** 내 학습 현황. 진도·잠금·다음 추천이 전부 여기서 나온다. */
export async function fetchPortfolio() {
  const response = await apiClient.get<LearningPortfolio>("/case-study/portfolio");
  return response.data;
}

export async function fetchSessions(topicId?: string) {
  const response = await apiClient.get<SessionSummary[]>("/case-study/sessions", {
    params: topicId ? { topic_id: topicId } : undefined,
  });
  return response.data;
}

export async function fetchSession(sessionId: string) {
  const response = await apiClient.get<LearningSession>(`/case-study/sessions/${sessionId}`);
  return response.data;
}

export async function createSession(topicId: string) {
  const response = await apiClient.post<LearningSession>("/case-study/sessions", {
    topic_id: topicId,
  });
  return response.data;
}

export async function renameSession(sessionId: string, displayName: string) {
  await apiClient.patch(`/case-study/sessions/${sessionId}`, { display_name: displayName });
}

export async function deleteSession(sessionId: string) {
  await apiClient.delete(`/case-study/sessions/${sessionId}`);
}

// ---- 학습 진행 ----
//
// 서버가 세션을 보관하므로 프론트는 sessionId만 들고 다니면 된다. 각 호출은
// 갱신된 세션을 돌려주고, 그게 곧 다음 화면의 상태다.

const step = (sessionId: string, action: string) =>
  apiClient
    .post<LearningSession>(`/case-study/sessions/${sessionId}/${action}`)
    .then((response) => response.data);

export const beginPrediction = (sessionId: string) => step(sessionId, "begin-prediction");
export const resetSession = (sessionId: string) => step(sessionId, "reset");
/** 실험이나 채점이 실패해 ERROR로 멈춘 세션을 실패 직전 단계로 되돌린다. */
export const recoverSession = (sessionId: string) => step(sessionId, "recover");
export const evaluateSession = (sessionId: string) => step(sessionId, "evaluation");

export async function submitPredictions(sessionId: string, answers: Record<string, unknown>) {
  const response = await apiClient.post<LearningSession>(
    `/case-study/sessions/${sessionId}/predictions`,
    { answers },
  );
  return response.data;
}

export async function submitObservations(sessionId: string, answers: Record<string, unknown>) {
  const response = await apiClient.post<LearningSession>(
    `/case-study/sessions/${sessionId}/observations`,
    { answers },
  );
  return response.data;
}

/** 모델 추론이 도는 단계라 느리다. 세션과 그릴 곡선이 함께 온다. */
export async function runExperiment(sessionId: string) {
  const response = await apiClient.post<ExperimentReply>(
    `/case-study/sessions/${sessionId}/experiment`,
  );
  return response.data;
}

/**
 * 저장된 세션을 다시 열었을 때 그래프만 되살린다. 곡선은 세션에 저장하지
 * 않기 때문에 필요하다 — 데스크톱 앱의 "그래프 다시 생성"과 같다.
 */
export async function regenerateExperiment(sessionId: string) {
  const response = await apiClient.post<ExperimentResult>(
    `/case-study/sessions/${sessionId}/regenerate`,
  );
  return response.data;
}

export async function askCaseFollowup(sessionId: string, question: string) {
  const response = await apiClient.post<{ answer: string; source: string }>(
    `/case-study/sessions/${sessionId}/followup`,
    { question },
  );
  return response.data;
}
