import { useEffect, useRef, useState } from "react";
import { CornerDownLeft, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { askCaseFollowup, getErrorMessage } from "../api";
import type { LearningSession } from "../types";

/** 세션에 저장된 대화 한 턴 (Python의 FollowupTurn). */
interface FollowupTurn {
  question: string;
  answer: string;
  source: string;
}

/**
 * 케이스 안에서 묻는 AI 질문 (panel.py의 _build_chat).
 *
 * I-V/Field Map 화면의 자유질문과 달리 이 대화는 학습 세션에 붙어
 * followup_history로 함께 저장된다 — 케이스를 다시 열면 그대로 남아 있다.
 * 튜터는 이 케이스의 분석 결과를 근거로만 답한다.
 */
export function CaseFollowupChat({ session }: { session: LearningSession }) {
  const saved = (session.followup_history as FollowupTurn[] | undefined) ?? [];
  const [turns, setTurns] = useState<FollowupTurn[]>(saved);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  // 보냈지만 아직 답이 오지 않은 질문.
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // 세션을 다시 받아오면(다른 걸음 뒤) 저장된 이력으로 맞춘다.
  useEffect(() => setTurns(saved), [session.session_id, saved.length]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, sending]);

  async function submit() {
    const question = draft.trim();
    if (!question || sending) return;
    setDraft("");
    // 답을 기다리는 동안에도 방금 보낸 질문이 보여야 대화처럼 읽힌다.
    // 답이 온 뒤에야 말풍선을 만들면, 수십 초 동안 내가 무엇을 물었는지도
    // 화면에 없다.
    setPending(question);
    setSending(true);
    setError(null);
    try {
      const reply = await askCaseFollowup(String(session.session_id), question);
      setTurns((previous) => [...previous, { question, answer: reply.answer, source: reply.source }]);
    } catch (err) {
      setError(getErrorMessage(err));
      // 보내지 못했으면 되돌린다 — 다시 타이핑하게 만들지 않는다.
      setDraft(question);
    } finally {
      setPending(null);
      setSending(false);
    }
  }

  return (
    <div className="flex h-full flex-col gap-2">
      <div
        ref={scrollRef}
        className="min-h-0 flex-1 space-y-2 overflow-y-auto rounded-md border border-outline-variant bg-surface-container-lowest p-3"
      >
        {turns.length === 0 && !sending && (
          <p className="text-[11px] text-on-surface-variant">
            이 Case의 결과에 대해 물어보세요. 튜터는 실행된 분석 결과를 근거로만 답합니다.
          </p>
        )}
        {turns.map((turn, index) => (
          <div key={`${index}-${turn.question}`} className="space-y-1.5">
            <div className="flex justify-end">
              <p className="max-w-[85%] whitespace-pre-wrap break-words rounded-md rounded-br-sm bg-primary/10 px-2.5 py-1.5 text-xs leading-relaxed">
                {turn.question}
              </p>
            </div>
            <div className="flex justify-start">
              <p
                className={cn(
                  "max-w-[85%] whitespace-pre-wrap break-words rounded-md rounded-bl-sm px-2.5 py-1.5 text-xs leading-relaxed",
                  turn.source === "external_error"
                    ? "border border-outline-variant bg-surface-container"
                    : "bg-surface-container-highest text-on-surface-variant",
                )}
              >
                {turn.answer}
              </p>
            </div>
          </div>
        ))}
        {pending && (
          <div className="space-y-1.5">
            <div className="flex justify-end">
              <p className="max-w-[85%] whitespace-pre-wrap break-words rounded-md rounded-br-sm bg-primary/10 px-2.5 py-1.5 text-xs leading-relaxed">
                {pending}
              </p>
            </div>
            <div className="flex items-center gap-1.5 text-[11px] text-on-surface-variant">
              <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin motion-reduce:animate-none" />
              답변을 만드는 중입니다.
            </div>
          </div>
        )}
      </div>

      {error && <p className="text-[11px] text-destructive">{error}</p>}

      <div className="flex items-end gap-2">
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
          rows={1}
          maxLength={800}
          disabled={sending}
          placeholder="이 결과에 대해 물어보세요. (Enter 전송, Shift+Enter 줄바꿈)"
          className="min-h-8 flex-1 resize-none rounded-md border border-outline-variant bg-surface-container-lowest px-2.5 py-1.5 text-xs leading-relaxed outline-none placeholder:text-on-surface-variant/70 focus:border-primary disabled:opacity-60"
        />
        <Button
          size="sm"
          className="h-8 shrink-0 gap-1 px-2.5 text-xs"
          disabled={sending || draft.trim().length === 0}
          onClick={submit}
        >
          <CornerDownLeft className="h-3.5 w-3.5" />
          Send
        </Button>
      </div>
    </div>
  );
}
