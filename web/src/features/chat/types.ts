// 서버 응답은 snake_case로 온다 (java_service의 SNAKE_CASE 설정).

/** POST /chat/curves, /chat/fields */
export interface ChatReply {
  thread_id: number;
  answer: string;
  /** "external_llm" | "local_router" | "external_error" */
  source: string;
  intent: string | null;
  used_evidence_ids: string[];
  suggested_followup: string | null;
  needs_new_experiment: boolean;
  /** 실패한 턴은 세지 않으므로 messages 길이와 다를 수 있다. */
  turns_used: number;
  turn_limit: number;
}

/** GET /chat/threads/{id} 안의 한 턴 */
export interface ChatMessageView {
  id: number;
  question: string;
  answer: string;
  source: string;
  intent: string | null;
  created_at: string;
}

/** GET /chat/threads/{id} */
export interface ChatThreadView {
  thread_id: number;
  kind: string;
  device_config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  messages: ChatMessageView[];
  turns_used: number;
  turn_limit: number;
}

/** GET /chat/threads */
export interface ChatThreadSummary {
  thread_id: number;
  kind: string;
  updated_at: string;
  /** 마지막이 아니라 첫 질문 — 대화의 주제를 정한 쪽이라 식별에 쓸 수 있다. */
  first_question: string | null;
  /** 얼린 소자 조건. 질문 문장만으로는 대화가 구분되지 않아 필요하다. */
  device_config: Record<string, unknown>;
  turns_used: number;
}

/** 화면에 그리는 한 턴. 아직 답이 오지 않은 질문은 pending으로 둔다. */
export interface ChatTurn {
  key: string;
  question: string;
  answer: string | null;
  failed: boolean;
}

export function toTurns(messages: ChatMessageView[]): ChatTurn[] {
  return messages.map((m) => ({
    key: `saved-${m.id}`,
    question: m.question,
    answer: m.answer,
    failed: m.source === "external_error",
  }));
}
