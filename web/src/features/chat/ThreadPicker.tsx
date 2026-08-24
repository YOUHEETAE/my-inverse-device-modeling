import { useState } from "react";
import { History } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Menu, MenuContent, MenuItem, MenuTrigger } from "@/components/ui/menu";
import { fetchThreads } from "./api";
import { summarizeConfig } from "./summary";
import type { ChatThreadSummary } from "./types";

interface ThreadPickerProps {
  /** "curves" | "fields" — 다른 화면의 대화가 섞이면 고를 수 없다. */
  kind: string;
  onSelect: (threadId: number) => void;
}

// 상대 시각. 목록에서는 정확한 시각보다 "얼마 전"이 눈에 빨리 들어온다.
function relativeTime(iso: string): string {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return "방금";
  if (minutes < 60) return `${minutes}분 전`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}시간 전`;
  return `${Math.round(hours / 24)}일 전`;
}

export function ThreadPicker({ kind, onSelect }: ThreadPickerProps) {
  const [threads, setThreads] = useState<ChatThreadSummary[] | null>(null);
  const [failed, setFailed] = useState(false);

  // 열 때 가져온다. 자유질문을 안 쓰는 사용자에게까지 목록을 미리 부를
  // 이유가 없고, 열 때마다 새로 받아야 방금 만든 대화도 보인다.
  async function load(open: boolean) {
    if (!open) return;
    setFailed(false);
    try {
      setThreads(await fetchThreads(kind));
    } catch {
      setThreads([]);
      setFailed(true);
    }
  }

  return (
    <Menu onOpenChange={load}>
      <MenuTrigger
        render={
          <Button
            variant="ghost"
            size="sm"
            className="h-6 gap-1 px-2 text-[10px] uppercase text-on-surface-variant"
          >
            <History className="h-3 w-3" />
            이전 대화
          </Button>
        }
      />
      <MenuContent className="max-h-72 w-72 overflow-y-auto">
        {threads === null ? (
          <p className="px-2 py-3 text-center text-[11px] text-on-surface-variant">
            불러오는 중…
          </p>
        ) : failed ? (
          <p className="px-2 py-3 text-center text-[11px] text-destructive">
            목록을 불러오지 못했습니다.
          </p>
        ) : threads.length === 0 ? (
          <p className="px-2 py-3 text-center text-[11px] text-on-surface-variant">
            아직 저장된 대화가 없습니다.
          </p>
        ) : (
          threads.map((thread) => (
            <MenuItem
              key={thread.thread_id}
              onClick={() => onSelect(thread.thread_id)}
              className="flex-col items-start gap-0.5 py-1.5"
            >
              {/* 질문 문장만으로는 대화가 구분되지 않는다 — 같은 화면에서
                  비슷하게 물으면 미리보기가 전부 같아진다. */}
              <span className="font-mono text-[10px] text-on-surface-variant">
                {summarizeConfig(thread.device_config) ?? thread.kind} · {thread.turns_used}턴
              </span>
              <span className="line-clamp-2 text-xs leading-snug">
                {thread.first_question ?? "(질문 없음)"}
              </span>
              <span className="text-[10px] text-on-surface-variant/70">
                {relativeTime(thread.updated_at)}
              </span>
            </MenuItem>
          ))
        )}
      </MenuContent>
    </Menu>
  );
}
