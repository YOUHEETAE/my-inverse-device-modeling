import { useEffect, useRef, useState } from "react";
import {
  CornerDownLeft,
  Download,
  LogIn,
  MessageSquarePlus,
  RotateCcw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { ChatError } from "./api";
import { parseFailure } from "./failure";
import { ThreadPicker } from "./ThreadPicker";
import type { ChatTurn } from "./types";

interface ChatThreadProps {
  turns: ChatTurn[];
  sending: boolean;
  error: ChatError | null;
  threadFull: boolean;
  turnsUsed: number;
  turnLimit: number;
  /** 비로그인이면 입력창 대신 로그인 안내를 보여준다. */
  authenticated: boolean;
  onLogin: () => void;
  /** 첫 질문이 얼린 소자 설정을 사람이 읽을 수 있게 요약한 것 */
  frozenSummary: string | null;
  /** 그 뒤로 화면 설정이 바뀌었는지. 막지는 않고 알리기만 한다. */
  screenChanged: boolean;
  /** "curves" | "fields" — 이전 대화 목록을 이 종류로만 거른다. */
  kind: string;
  onRestore: (threadId: number) => void;
  /**
   * 화면과 다른 소자 조건의 대화를 열었을 때 그 조건을 작업대에 되살린다.
   * 현재 구성을 덮어쓰므로 사용자가 누를 때만 실행한다.
   */
  onLoadFrozenConfig: () => void;
  /** 소자 조건이 안 맞을 때 (Field는 2개 이상 필요) */
  disabled?: boolean;
  disabledReason?: string;
  /** 실패하면 false — 입력한 질문을 지우지 않기 위해 결과를 받는다. */
  onSend: (question: string) => Promise<boolean>;
  onStartNew: () => void;
}

// 실패한 턴. 서버가 만든 5줄짜리 상태 보고를 그대로 붉게 띄우면 뭔가
// 크게 망가진 것처럼 읽히는데, 대개는 다시 눌러보면 되는 상황이다.
// 사람이 읽을 문장을 앞세우고 조치는 버튼으로 준다 — "다시 시도해 주세요"만
// 적어두고 버튼이 없으면 사용자는 질문을 다시 타이핑해야 한다.
function FailureOrAnswer({
  turn,
  onRetry,
}: {
  turn: ChatTurn;
  onRetry: (question: string) => Promise<boolean>;
}) {
  if (!turn.failed) {
    return (
      <p className="max-w-[85%] whitespace-pre-wrap break-words rounded-md rounded-bl-sm bg-surface-container-highest px-2.5 py-1.5 text-xs leading-relaxed text-on-surface-variant">
        {turn.answer}
      </p>
    );
  }

  const failure = parseFailure(turn.answer ?? "");
  // 한도 초과는 최소 대기가 있다. 그동안 버튼을 눌러봐야 같은 실패라서
  // 남은 시간을 버튼에 그대로 보여주고 잠가둔다.
  const [wait, setWait] = useState(failure.waitSeconds ?? 0);
  useEffect(() => {
    if (wait <= 0) return;
    const id = setTimeout(() => setWait((s) => s - 1), 1000);
    return () => clearTimeout(id);
  }, [wait]);
  return (
    <div className="max-w-[85%] space-y-1.5 rounded-md rounded-bl-sm border border-outline-variant bg-surface-container px-2.5 py-2">
      <p className="text-xs font-bold">답변을 만들지 못했어요</p>
      <p className="text-xs leading-relaxed text-on-surface-variant">
        {failure.reason}
      </p>
      {failure.retryable ? (
        <Button
          variant="outline"
          size="sm"
          disabled={wait > 0}
          className="h-6 gap-1 px-2 text-[10px]"
          onClick={() => onRetry(turn.question)}
        >
          <RotateCcw className="h-3 w-3" />
          {wait > 0 ? `${wait}초 후 다시 시도` : "다시 시도"}
        </Button>
      ) : (
        failure.action && (
          <p className="text-[11px] text-on-surface-variant">
            {failure.action}
          </p>
        )
      )}
      {failure.preserved && (
        <p className="text-[10px] text-on-surface-variant/70">
          {failure.preserved}
        </p>
      )}
    </div>
  );
}

// 상한이 다가올 때 미리 알린다. 서버는 임계값을 정하지 않고 사용량만
// 내려주므로(turns_used/turn_limit) 언제 알릴지는 화면이 정한다.
const WARN_AT = 0.8;

// 말풍선 영역 높이. 넘치면 이 안에서만 스크롤되므로, 대화가 길어져도
// 카드와 그래프 위치는 그대로다.
const MESSAGES_HEIGHT = "max-h-80";

export function ChatThread({
  turns,
  sending,
  error,
  threadFull,
  turnsUsed,
  turnLimit,
  authenticated,
  onLogin,
  frozenSummary,
  screenChanged,
  kind,
  onRestore,
  onLoadFrozenConfig,
  disabled,
  disabledReason,
  onSend,
  onStartNew,
}: ChatThreadProps) {
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  const open = turns.length > 0;

  // 새 말풍선이 붙으면 아래로 따라간다 — 카드가 위로 자라는 느낌을 준다.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el || !open) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [turns, open]);

  const nearLimit = turnLimit > 0 && turnsUsed >= turnLimit * WARN_AT;
  // 401은 오류라기보다 "다시 로그인하세요"다. axios 원문을 그대로 보이면
  // 사용자는 무엇이 잘못됐는지 알 수 없다.
  const sessionExpired = error?.status === 401;
  const blocked = disabled || threadFull;

  async function submit() {
    if (blocked) return;
    // 말풍선이 이미 질문을 보여주므로 입력창은 바로 비운다. 응답을 기다리는
    // 동안 같은 문장이 두 군데 남아 있으면 보낸 건지 아닌지 헷갈린다.
    const sent = draft;
    setDraft("");
    // 다만 보내지 못했으면 되돌린다 — 다시 타이핑하게 만들지 않는다.
    if (!(await onSend(sent))) setDraft(sent);
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {turnLimit > 0 && turns.length > 0 && (
            <span
              className={cn(
                "font-mono text-[10px] tabular-nums",
                nearLimit ? "text-accent-orange" : "text-on-surface-variant",
              )}
            >
              {turnsUsed}/{turnLimit}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {authenticated && <ThreadPicker kind={kind} onSelect={onRestore} />}
          {turns.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 gap-1 px-2 text-[10px] uppercase text-on-surface-variant"
              onClick={onStartNew}
            >
              <MessageSquarePlus className="h-3 w-3" />
              New
            </Button>
          )}
        </div>
      </div>

      {frozenSummary && (
        // 첫 질문이 소자 설정을 얼린다. 화면을 바꿔도 이 대화는 원래 소자를
        // 계속 얘기하므로, 무엇을 기준으로 답하는지 밝혀야 한다.
        // (데스크톱 앱의 "… 스냅샷 기준 · 화면 변경됨 (새 대화로 반영)")
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <p className="font-mono text-[10px] leading-relaxed text-on-surface-variant">
            {frozenSummary} 스냅샷 기준
            {screenChanged && (
              <span className="text-accent-orange"> · 화면 변경됨</span>
            )}
          </p>
          {screenChanged && (
            // 말풍선 속 숫자와 화면 그래프가 어긋난 채로 이어서 묻게 두면
            // 어느 쪽을 보고 있는지 알 수 없다. 되살릴 수단을 준다.
            <Button
              variant="outline"
              size="sm"
              className="h-5 gap-1 px-1.5 text-[10px]"
              onClick={onLoadFrozenConfig}
            >
              <Download className="h-2.5 w-2.5" />
              이 설정 불러오기
            </Button>
          )}
        </div>
      )}

      {/* grid 0fr -> 1fr 는 내용 높이를 모르고도 부드럽게 열고 닫는다.
          max-height 로 하면 상한을 크게 잡을수록 애니메이션이 튄다. */}
      <div
        className={cn(
          "grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none",
          open ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
        )}
      >
        <div className="overflow-hidden">
          <div
            ref={scrollRef}
            className={cn(
              "space-y-2 overflow-y-auto rounded-md border border-outline-variant bg-surface-container-lowest p-2",
              MESSAGES_HEIGHT,
            )}
          >
            {turns.map((turn) => (
              <div key={turn.key} className="space-y-1.5">
                <div className="flex justify-end">
                  <p className="max-w-[85%] whitespace-pre-wrap break-words rounded-md rounded-br-sm bg-primary/10 px-2.5 py-1.5 text-xs leading-relaxed">
                    {turn.question}
                  </p>
                </div>
                <div className="flex justify-start">
                  {turn.answer === null ? (
                    <span className="flex items-center gap-1 px-1 py-1.5">
                      {[0, 1, 2].map((i) => (
                        <span
                          key={i}
                          className="h-1 w-1 animate-pulse rounded-full bg-on-surface-variant motion-reduce:animate-none"
                          style={{ animationDelay: `${i * 150}ms` }}
                        />
                      ))}
                    </span>
                  ) : (
                    <FailureOrAnswer turn={turn} onRetry={onSend} />
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {threadFull && (
        // 오류가 아니라 안내다 — 빨간 토스트로 띄우면 뭔가 고장난 것처럼 읽힌다.
        <div className="flex items-center justify-between gap-2 rounded-md border border-accent-orange/40 bg-accent-orange/10 px-2.5 py-2">
          <p className="text-[11px] leading-relaxed text-on-surface-variant">
            {error?.message}
          </p>
          <Button
            size="sm"
            className="h-6 shrink-0 gap-1 px-2 text-[10px] uppercase"
            onClick={onStartNew}
          >
            <MessageSquarePlus className="h-3 w-3" />
            New chat
          </Button>
        </div>
      )}
      {sessionExpired && (
        // 세션이 끊긴 것뿐이라 실패가 아니다. 아래 로그인 버튼이 이미
        // 떠 있으므로 여기서는 이유만 알려준다.
        <p className="text-[11px] text-on-surface-variant">
          로그인 세션이 만료되었습니다. 다시 로그인하면 이어서 질문할 수
          있습니다.
        </p>
      )}
      {error && !threadFull && !sessionExpired && (
        <p className="text-[11px] text-destructive">{error.message}</p>
      )}

      {!authenticated ? (
        <Button
          variant="outline"
          size="sm"
          className="gap-1.5 border-outline-variant text-xs text-on-surface-variant"
          onClick={onLogin}
        >
          <LogIn className="h-3.5 w-3.5" />
          Sign in to ask questions
        </Button>
      ) : (
        <div className="flex items-end gap-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              // Enter 전송 / Shift+Enter 줄바꿈 — 채팅의 관례
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            rows={1}
            maxLength={800}
            disabled={blocked}
            placeholder={
              disabled
                ? disabledReason
                : threadFull
                  ? "새 대화를 시작해 주세요."
                  : "이 결과에 대해 물어보세요. (Enter 전송, Shift+Enter 줄바꿈)"
            }
            className="min-h-8 flex-1 resize-none rounded-md border border-outline-variant bg-surface-container-lowest px-2.5 py-1.5 text-xs leading-relaxed outline-none placeholder:text-on-surface-variant/70 focus:border-primary disabled:opacity-60"
          />
          <Button
            size="sm"
            className="h-8 shrink-0 gap-1 px-2.5 text-xs"
            onClick={submit}
            disabled={blocked || sending || draft.trim().length === 0}
          >
            <CornerDownLeft className="h-3.5 w-3.5" />
            Send
          </Button>
        </div>
      )}
    </div>
  );
}
