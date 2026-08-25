import axios from "axios";
import { apiClient } from "@/lib/apiClient";
import type { CurveConfig } from "../curves/types";
import type { FieldConfig } from "../fields/types";
import type { ChatReply, ChatThreadSummary, ChatThreadView } from "./types";

/** 대화가 상한을 채웠을 때 서버가 주는 상태. 오류가 아니라 안내다. */
export const THREAD_FULL = 409;

export interface ChatError {
  /** 409면 "새 대화 시작"을, 401이면 로그인을 안내해야 한다. */
  status: number | null;
  message: string;
}

export function toChatError(err: unknown): ChatError {
  if (axios.isAxiosError(err)) {
    const status = err.response?.status ?? null;
    return {
      status,
      // 401은 본문 없이 상태 코드만 온다(SecurityConfig의
      // HttpStatusEntryPoint). detail이 없을 때 err.message로 떨어지면
      // "Request failed with status code 401"이 그대로 보인다.
      message:
        err.response?.data?.detail ??
        (status === 401
          ? "로그인이 필요합니다. 로그인 후 다시 시도해 주세요."
          : "질문을 보내지 못했습니다. 잠시 후 다시 시도해 주세요."),
    };
  }
  return { status: null, message: "질문을 보내지 못했습니다." };
}

export async function askCurveChat(curves: CurveConfig[], question: string, threadId: number | null) {
  const response = await apiClient.post<ChatReply>("/chat/curves", {
    curves,
    question,
    thread_id: threadId,
  });
  return response.data;
}

export async function askFieldChat(
  fields: FieldConfig[],
  display: string,
  scaleMode: string,
  rangeMode: string,
  question: string,
  threadId: number | null,
) {
  const response = await apiClient.post<ChatReply>("/chat/fields", {
    fields,
    display,
    scale_mode: scaleMode,
    range_mode: rangeMode,
    question,
    thread_id: threadId,
  });
  return response.data;
}

export async function fetchThread(threadId: number) {
  const response = await apiClient.get<ChatThreadView>(`/chat/threads/${threadId}`);
  return response.data;
}

export async function fetchThreads(kind?: string) {
  const response = await apiClient.get<ChatThreadSummary[]>("/chat/threads", {
    params: kind ? { kind } : undefined,
  });
  return response.data;
}
