import { useCallback, useRef, useState } from "react";
import { THREAD_FULL, fetchThread, toChatError, type ChatError } from "./api";
import { toTurns, type ChatReply, type ChatTurn } from "./types";

/** 페이지마다 보내는 본문이 달라서 호출부를 주입받는다. */
type Ask = (question: string, threadId: number | null) => Promise<ChatReply>;

/** 서버가 chat_thread.device_config에 저장하는 것과 같은 모양 */
type DeviceConfig = Record<string, unknown>;

/**
 * @param currentConfig 화면의 현재 소자 설정. 첫 질문에서 얼린 설정과 비교해
 *   "화면 변경됨"을 알리는 데만 쓴다 — 서버는 얼린 설정을 따로 들고 있어서
 *   이 값이 바뀌어도 대화 내용에는 영향이 없다.
 */
export function useChat(ask: Ask, currentConfig: DeviceConfig) {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [threadId, setThreadId] = useState<number | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<ChatError | null>(null);
  const [turnsUsed, setTurnsUsed] = useState(0);
  const [turnLimit, setTurnLimit] = useState(0);

  // 첫 질문이 얼린 소자 설정. 데스크톱 앱과 같은 규칙이라 이후 화면을
  // 바꿔도 대화는 이 설정 기준으로 이어진다.
  const [frozenConfig, setFrozenConfig] = useState<DeviceConfig | null>(null);

  // 낙관적으로 넣은 질문을 답변이 왔을 때 찾아 바꾸기 위한 키
  const pendingKey = useRef(0);

  const send = useCallback(
    async (question: string): Promise<boolean> => {
      const trimmed = question.trim();
      if (!trimmed || sending) return false;

      const key = `pending-${pendingKey.current++}`;
      const configAtSend = currentConfig;
      // 답을 기다리는 동안에도 자기 질문은 보여야 대화처럼 읽힌다.
      setTurns((prev) => [...prev, { key, question: trimmed, answer: null, failed: false }]);
      setSending(true);
      setError(null);

      try {
        const reply = await ask(trimmed, threadId);
        // 첫 턴에서만 얼린다. 서버도 같은 시점에 device_config를 저장한다.
        setFrozenConfig((prev: DeviceConfig | null) => prev ?? configAtSend);
        setThreadId(reply.thread_id);
        setTurnsUsed(reply.turns_used);
        setTurnLimit(reply.turn_limit);
        setTurns((prev) =>
          prev.map((t) =>
            t.key === key
              ? { ...t, answer: reply.answer, failed: reply.source === "external_error" }
              : t,
          ),
        );
        return true;
      } catch (err) {
        const chatError = toChatError(err);
        setError(chatError);
        // 상한에 걸린 질문은 서버가 저장하지 않았으므로 화면에서도 되돌린다.
        // 남겨두면 답이 영영 오지 않는 말풍선이 된다.
        setTurns((prev) => prev.filter((t) => t.key !== key));
        return false;
      } finally {
        setSending(false);
      }
    },
    [ask, sending, threadId, currentConfig],
  );

  /** 상한에 닿았거나 사용자가 주제를 바꿀 때. thread_id를 비우면 서버가 새로 만든다. */
  const startNew = useCallback(() => {
    setTurns([]);
    setThreadId(null);
    setTurnsUsed(0);
    setError(null);
    setFrozenConfig(null);
  }, []);

  const restore = useCallback(async (id: number) => {
    setError(null);
    try {
      const thread = await fetchThread(id);
      setTurns(toTurns(thread.messages));
      setThreadId(thread.thread_id);
      setFrozenConfig(thread.device_config);
      setTurnsUsed(thread.turns_used);
      setTurnLimit(thread.turn_limit);
    } catch (err) {
      setError(toChatError(err));
    }
  }, []);

  return {
    turns,
    threadId,
    frozenConfig,
    // 얼린 설정과 화면이 달라졌음을 알린다. 막지는 않는다 — 대화는 얼린
    // 설정 기준으로 멀쩡히 이어지고, 바뀐 설정으로 묻고 싶으면 새 대화다.
    screenChanged:
      frozenConfig !== null && JSON.stringify(frozenConfig) !== JSON.stringify(currentConfig),
    sending,
    error,
    turnsUsed,
    turnLimit,
    threadFull: error?.status === THREAD_FULL,
    send,
    startNew,
    restore,
  };
}
