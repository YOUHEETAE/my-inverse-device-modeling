import { apiClient } from "@/lib/apiClient";
import { getErrorMessage } from "@/features/curves/api";
import type { AnswerSubmission, GradeResponse, TopicDetail, TopicSummary } from "./types";

export { getErrorMessage };

export async function fetchCaseStudyTopics() {
  const response = await apiClient.get<TopicSummary[]>("/case-study/topics");
  return response.data;
}

export async function fetchCaseStudyTopic(topicId: string) {
  const response = await apiClient.get<TopicDetail>(`/case-study/topics/${topicId}`);
  return response.data;
}

export async function gradeCaseStudy(
  topicId: string,
  predictionAnswers: AnswerSubmission[],
  observationAnswers: AnswerSubmission[],
) {
  const response = await apiClient.post<GradeResponse>(`/case-study/topics/${topicId}/grade`, {
    prediction_answers: predictionAnswers,
    observation_answers: observationAnswers,
  });
  return response.data;
}
