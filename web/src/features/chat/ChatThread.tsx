import { useEffect, useRef, useState } from "react";
import { ChevronDown, CornerDownLeft, LogIn, MessageSquarePlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { ChatError } from "./api";
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
  /** 소자 조건이 안 맞을 때 (Field는 2개 이상 필요) */
  disabled?: boolean;
  disabledReason?: string;
  /** 실패하면 false — 입력한 질문을 지우지 않기 위해 결과를 받는다. */
  onSend: (question: string) => Promise<boolean>;
  onStartNew: () => void;
}

// 상한이 다가올 때 미리 알린다. 서버는 임계값을 정하지 않고 사용량만
// 내려주므로(turns_used/turn_limit) 언제 알릴지는 화면이 정한다.
const WARN_AT = 0.8;

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
  disabled,
  disabledReason,
  onSend,
  onStartNew,
}: ChatThreadProps) {
  const [draft, setDraft] = useState("");
  const [collapsed, setCollapsed] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const open = turns.length > 0 && !collapsed;

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
    // 접어둔 채로 질문하면 답이 보이지 않는다. 새 질문은 언제나 펼친다.
    setCollapsed(false);
    // 실패했는데 입력까지 비우면 사용자가 질문을 다시 타이핑해야 한다.
    if (await onSend(draft)) setDraft("");
  }

  return (
    <div className="flex flex-col gap-2 border-t border-outline-variant pt-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h4 className="text-xs font-bold uppercase tracking-wide">Ask a question</h4>
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
        {turns.length > 0 && (
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              className="h-6 gap-1 px-2 text-[10px] uppercase text-on-surface-variant"
              onClick={onStartNew}
            >
              <MessageSquarePlus className="h-3 w-3" />
              New
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0 text-on-surface-variant"
              onClick={() => setCollapsed((c) => !c)}
              aria-expanded={open}
              aria-label={open ? "Collapse conversation" : "Expand conversation"}
            >
              <ChevronDown
                className={cn(
                  "h-3.5 w-3.5 transition-transform duration-300 motion-reduce:transition-none",
                  open ? "rotate-0" : "-rotate-90",
                )}
              />
            </Button>
          </div>
        )}
      </div>

      {frozenSummary && (
        // 첫 질문이 소자 설정을 얼린다. 화면을 바꿔도 이 대화는 원래 소자를
        // 계속 얘기하므로, 무엇을 기준으로 답하는지 밝혀야 한다.
        // (데스크톱 앱의 "… 스냅샷 기준 · 화면 변경됨 (새 대화로 반영)")
        <p className="font-mono text-[10px] leading-relaxed text-on-surface-variant">
          {frozenSummary} 스냅샷 기준
          {screenChanged && (
            <span className="text-accent-orange"> · 화면 변경됨 (새 대화로 반영)</span>
          )}
        </p>
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
            className="max-h-80 space-y-2 overflow-y-auto rounded-md border border-outline-variant bg-surface-container-lowest p-2"
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
                    <p
                      className={cn(
                        "max-w-[85%] whitespace-pre-wrap break-words rounded-md rounded-bl-sm px-2.5 py-1.5 text-xs leading-relaxed",
                        turn.failed
                          ? "bg-destructive/10 text-destructive"
                          : "bg-surface-container-highest text-on-surface-variant",
                      )}
                    >
                      {turn.answer}
                    </p>
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
          <p className="text-[11px] leading-relaxed text-on-surface-variant">{error?.message}</p>
          <Button size="sm" className="h-6 shrink-0 gap-1 px-2 text-[10px] uppercase" onClick={onStartNew}>
            <MessageSquarePlus className="h-3 w-3" />
            New chat
          </Button>
        </div>
      )}
      {sessionExpired && (
        // 세션이 끊긴 것뿐이라 실패가 아니다. 아래 로그인 버튼이 이미
        // 떠 있으므로 여기서는 이유만 알려준다.
        <p className="text-[11px] text-on-surface-variant">
          로그인 세션이 만료되었습니다. 다시 로그인하면 이어서 질문할 수 있습니다.
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
