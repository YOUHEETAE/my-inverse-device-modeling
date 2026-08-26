import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import type { ExplanationStatus } from "@/components/explanation/ExplanationPanel";
import type { ExplanationSection } from "@/components/explanation/explanationSections";
import type { ChatError } from "../chat/api";
import type { ChatTurn } from "../chat/types";

// AI 분석 결과와 자유질문 대화. deviceStore/viewStore/predictionCache와 같은
// 이유로 App 수준에 둔다 — Curves와 Field Map을 오갈 때마다 화면이 초기화되지
// 않게 하려는 것이다.
//
// 여기서는 이유가 하나 더 있다. 예측 결과는 다시 계산하면 그만이지만 이 둘은
// 외부 LLM 호출이라 계정의 하루 한도를 깎는다. 페이지를 옮겼다는 이유로
// 지워버리면 사용자가 같은 답을 두 번 사게 된다. 대화는 한 스레드에 20턴이라는
// 상한까지 걸려 있어 더 그렇다.
export type AnalysisKind = "curves" | "fields";

export interface ExplanationState {
  sections: ExplanationSection[];
  provider: "mock" | "external_llm" | null;
  /** 서버가 실제로 쓴 모델. 화면 배지가 이 값을 그대로 보여준다. */
  model: string | null;
  status: ExplanationStatus;
  error: string | null;
}

/** 대화 하나의 상태 전부. useChat이 이걸 읽고 쓴다. */
export interface ChatState {
  turns: ChatTurn[];
  threadId: number | null;
  /** 첫 질문이 얼린 소자 설정. 이후 화면을 바꿔도 대화는 이 기준으로 이어진다. */
  frozenConfig: Record<string, unknown> | null;
  turnsUsed: number;
  turnLimit: number;
  sending: boolean;
  error: ChatError | null;
  // 새로고침 복원(sessionStorage)을 앱이 떠 있는 동안 한 번만 시도하기 위한
  // 표시. 페이지를 오갈 때마다 다시 불러오면 이미 들고 있는 대화를 서버에서
  // 또 받아오게 된다.
  restored: boolean;
}

const EMPTY_EXPLANATION: ExplanationState = {
  sections: [],
  provider: null,
  model: null,
  status: "ready",
  error: null,
};

const EMPTY_CHAT: ChatState = {
  turns: [],
  threadId: null,
  frozenConfig: null,
  turnsUsed: 0,
  turnLimit: 0,
  sending: false,
  error: null,
  restored: false,
};

type ChatPatch = Partial<ChatState> | ((prev: ChatState) => Partial<ChatState>);

interface AnalysisStoreValue {
  explanation: Record<AnalysisKind, ExplanationState>;
  updateExplanation: (kind: AnalysisKind, patch: Partial<ExplanationState>) => void;
  chat: Record<AnalysisKind, ChatState>;
  updateChat: (kind: AnalysisKind, patch: ChatPatch) => void;
  /** 대화를 처음부터 다시 시작할 때. */
  resetChat: (kind: AnalysisKind) => void;
}

const AnalysisStoreContext = createContext<AnalysisStoreValue | null>(null);

export function AnalysisStoreProvider({ children }: { children: ReactNode }) {
  const [explanation, setExplanation] = useState<Record<AnalysisKind, ExplanationState>>({
    curves: EMPTY_EXPLANATION,
    fields: EMPTY_EXPLANATION,
  });
  const [chat, setChat] = useState<Record<AnalysisKind, ChatState>>({
    curves: EMPTY_CHAT,
    fields: EMPTY_CHAT,
  });

  const updateExplanation = useCallback((kind: AnalysisKind, patch: Partial<ExplanationState>) => {
    setExplanation((prev) => ({ ...prev, [kind]: { ...prev[kind], ...patch } }));
  }, []);

  const updateChat = useCallback((kind: AnalysisKind, patch: ChatPatch) => {
    setChat((prev) => {
      const slot = prev[kind];
      const next = typeof patch === "function" ? patch(slot) : patch;
      return { ...prev, [kind]: { ...slot, ...next } };
    });
  }, []);

  // restored는 남긴다 — 새 대화를 시작한 것이지 앱을 새로 연 것이 아니므로,
  // 복원을 다시 시도하면 방금 버린 대화를 되살리게 된다.
  const resetChat = useCallback((kind: AnalysisKind) => {
    setChat((prev) => ({ ...prev, [kind]: { ...EMPTY_CHAT, restored: true } }));
  }, []);

  return (
    <AnalysisStoreContext.Provider
      value={{ explanation, updateExplanation, chat, updateChat, resetChat }}
    >
      {children}
    </AnalysisStoreContext.Provider>
  );
}

export function useAnalysisStore() {
  const ctx = useContext(AnalysisStoreContext);
  if (!ctx) throw new Error("useAnalysisStore must be used within an AnalysisStoreProvider");
  return ctx;
}
