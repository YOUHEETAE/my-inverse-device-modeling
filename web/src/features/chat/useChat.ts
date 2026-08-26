import { useCallback, useEffect, useRef } from "react";
import { useAnalysisStore, type AnalysisKind } from "../shared/analysisStore";
import { THREAD_FULL, fetchThread, toChatError, type ChatError } from "./api";
import { toTurns, type ChatReply, type ChatTurn } from "./types";

/** 페이지마다 보내는 본문이 달라서 호출부를 주입받는다. */
type Ask = (question: string, threadId: number | null) => Promise<ChatReply>;

/** 서버가 chat_thread.device_config에 저장하는 것과 같은 모양 */
type DeviceConfig = Record<string, unknown>;

/**
 * 대화 상태는 이 훅이 아니라 analysisStore가 들고 있다. Curves와 Field Map을
 * 오갈 때 페이지가 언마운트되는데, 여기에 두면 그때마다 대화가 사라지거나
 * 서버에서 다시 받아와야 한다. 한 스레드에 20턴이라는 상한이 걸린 자원이라
 * 화면을 옮겼다는 이유로 잃어서는 안 된다.
 *
 * 답을 기다리는 중에 페이지를 떠나도 되는 것도 그래서다 — 상태가 App 수준에
 * 있으므로 요청이 끝나면 그대로 반영되고, 돌아오면 답이 와 있다.
 *
 * @param currentConfig 화면의 현재 소자 설정. 첫 질문에서 얼린 설정과 비교해
 *   "화면 변경됨"을 알리는 데만 쓴다 — 서버는 얼린 설정을 따로 들고 있어서
 *   이 값이 바뀌어도 대화 내용에는 영향이 없다.
 * @param kind 어느 화면의 대화인가. 저장소 슬롯과 sessionStorage 키를 가른다.
 */
export function useChat(ask: Ask, currentConfig: DeviceConfig, kind: AnalysisKind) {
  const { chat, updateChat, resetChat } = useAnalysisStore();
  const state = chat[kind];
  const storageKey = `chat:thread:${kind}`;

  // 낙관적으로 넣은 질문을 답변이 왔을 때 찾아 바꾸기 위한 키
  const pendingKey = useRef(0);

  // 새로고침 직후 마지막 대화를 되살린다. 삭제됐거나 남의 것이면 조용히
  // 키를 버린다 — 사용자가 하지 않은 일에 오류를 띄울 이유가 없다.
  //
  // restored 표시를 두는 이유는 페이지를 오갈 때마다 이 훅이 다시 마운트되기
  // 때문이다. 표시가 없으면 이미 들고 있는 대화를 볼 때마다 서버에서 또
  // 받아온다.
  useEffect(() => {
    if (state.restored) return;
    updateChat(kind, { restored: true });

    const saved = sessionStorage.getItem(storageKey);
    if (!saved) return;
    fetchThread(Number(saved))
      .then((thread) => {
        updateChat(kind, {
          turns: toTurns(thread.messages),
          threadId: thread.thread_id,
          turnsUsed: thread.turns_used,
          turnLimit: thread.turn_limit,
          frozenConfig: thread.device_config,
        });
      })
      .catch(() => sessionStorage.removeItem(storageKey));
  }, [state.restored, kind, storageKey, updateChat]);

  const send = useCallback(
    async (question: string): Promise<boolean> => {
      const trimmed = question.trim();
      if (!trimmed || state.sending) return false;

      const key = `pending-${pendingKey.current++}`;
      const configAtSend = currentConfig;
      const threadId = state.threadId;

      // 답을 기다리는 동안에도 자기 질문은 보여야 대화처럼 읽힌다.
      updateChat(kind, (prev) => ({
        turns: [...prev.turns, { key, question: trimmed, answer: null, failed: false }],
        sending: true,
        error: null,
      }));

      try {
        const reply = await ask(trimmed, threadId);
        sessionStorage.setItem(storageKey, String(reply.thread_id));
        updateChat(kind, (prev) => ({
          // 첫 턴에서만 얼린다. 서버도 같은 시점에 device_config를 저장한다.
          frozenConfig: prev.frozenConfig ?? configAtSend,
          threadId: reply.thread_id,
          turnsUsed: reply.turns_used,
          turnLimit: reply.turn_limit,
          turns: prev.turns.map((t) =>
            t.key === key
              ? { ...t, answer: reply.answer, failed: reply.source === "external_error" }
              : t,
          ),
          sending: false,
        }));
        return true;
      } catch (err) {
        // 상한에 걸린 질문은 서버가 저장하지 않았으므로 화면에서도 되돌린다.
        // 남겨두면 답이 영영 오지 않는 말풍선이 된다.
        updateChat(kind, (prev) => ({
          error: toChatError(err),
          turns: prev.turns.filter((t) => t.key !== key),
          sending: false,
        }));
        return false;
      }
    },
    [ask, state.sending, state.threadId, currentConfig, kind, storageKey, updateChat],
  );

  /** 상한에 닿았거나 사용자가 주제를 바꿀 때. thread_id를 비우면 서버가 새로 만든다. */
  const startNew = useCallback(() => {
    resetChat(kind);
    sessionStorage.removeItem(storageKey);
  }, [kind, storageKey, resetChat]);

  const restore = useCallback(
    async (id: number) => {
      updateChat(kind, { error: null });
      try {
        const thread = await fetchThread(id);
        sessionStorage.setItem(storageKey, String(thread.thread_id));
        updateChat(kind, {
          turns: toTurns(thread.messages),
          threadId: thread.thread_id,
          frozenConfig: thread.device_config,
          turnsUsed: thread.turns_used,
          turnLimit: thread.turn_limit,
        });
      } catch (err) {
        updateChat(kind, { error: toChatError(err) });
      }
    },
    [kind, storageKey, updateChat],
  );

  return {
    turns: state.turns as ChatTurn[],
    threadId: state.threadId,
    frozenConfig: state.frozenConfig,
    // 얼린 설정과 화면이 달라졌음을 알린다. 막지는 않는다 — 대화는 얼린
    // 설정 기준으로 멀쩡히 이어지고, 바뀐 설정으로 묻고 싶으면 새 대화다.
    screenChanged:
      state.frozenConfig !== null &&
      JSON.stringify(state.frozenConfig) !== JSON.stringify(currentConfig),
    sending: state.sending,
    error: state.error as ChatError | null,
    turnsUsed: state.turnsUsed,
    turnLimit: state.turnLimit,
    threadFull: state.error?.status === THREAD_FULL,
    send,
    startNew,
    restore,
  };
}
