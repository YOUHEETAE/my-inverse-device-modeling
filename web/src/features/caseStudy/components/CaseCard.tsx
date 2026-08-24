import { Lock, Play, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { CASE_STATUS_LABELS, type CaseProgress, type CaseStatus, type SessionSummary, type TopicSummary } from "../types";

// 데스크톱 앱의 카드 색 (panel.py의 status_colors).
const STATUS_STYLES: Record<CaseStatus, string> = {
  completed: "text-accent-green",
  in_progress: "text-primary",
  not_started: "text-on-surface-variant",
  locked: "text-accent-orange",
};

interface CaseCardProps {
  index: number;
  topic: TopicSummary;
  progress: CaseProgress;
  /** 이 케이스의 세션 중 가장 최근 것. 없으면 아직 시작 전이다. */
  latest?: SessionSummary;
  onOpen: (sessionId: string) => void;
  onStart: (topicId: string) => void;
}

export function CaseCard({ index, topic, progress, latest, onOpen, onStart }: CaseCardProps) {
  const unlocked = progress.prerequisites_met;

  // 데스크톱과 같은 규칙 (panel.py의 _build_cover): 기록이 있으면 그 세션을
  // 열고, 없으면 새로 시작한다. 잠긴 케이스는 버튼 자체가 눌리지 않는다.
  const primaryLabel = latest
    ? latest.completed
      ? "결과 보기"
      : "이어서 하기"
    : unlocked
      ? "Case 살펴보기"
      : "선행 Case 완료 후 열림";

  return (
    <div
      className={cn(
        "flex flex-col rounded-md border border-outline-variant bg-surface-container-low p-4",
        !unlocked && "opacity-70",
      )}
    >
      <span className="font-mono text-[10px] uppercase tracking-wider text-on-surface-variant">
        Case {String(index + 1).padStart(2, "0")}
      </span>
      <h3 className="mt-1 text-sm font-bold leading-snug">{topic.title}</h3>
      <span className={cn("mt-1 text-[11px] font-bold", STATUS_STYLES[progress.status])}>
        {CASE_STATUS_LABELS[progress.status]}
      </span>

      <p className="mt-2 text-xs leading-relaxed text-on-surface-variant">{topic.description}</p>

      {/* 무엇을 바꿔 비교하는 케이스인지. 케이스마다 규칙이 달라 서버가
          문구를 만들어 준다. */}
      <p className="mt-3 text-[11px] text-primary">변경 조건 · {topic.comparison_caption}</p>

      <p className="mt-1 text-[11px] text-on-surface-variant">
        {progress.updated_at
          ? `최근 학습 · ${formatTimestamp(progress.updated_at)}`
          : "아직 학습 기록이 없습니다."}
      </p>

      {/* mt-auto: 카드 높이가 제각각이어도 버튼 줄은 아래에 붙는다. */}
      <div className="mt-auto flex gap-2 pt-4">
        <Button
          size="sm"
          variant={latest ? "default" : "outline"}
          className="flex-1 gap-1.5 text-xs"
          disabled={!unlocked}
          onClick={() => (latest ? onOpen(latest.session_id) : onStart(topic.topic_id))}
        >
          {unlocked ? <Play className="h-3.5 w-3.5" /> : <Lock className="h-3.5 w-3.5" />}
          {primaryLabel}
        </Button>
        {/* 끝낸 케이스는 다시 풀어볼 수 있다. 이전 기록은 그대로 남는다. */}
        {latest?.completed && (
          <Button
            size="sm"
            variant="outline"
            className="gap-1.5 text-xs"
            disabled={!unlocked}
            onClick={() => onStart(topic.topic_id)}
          >
            <RotateCcw className="h-3.5 w-3.5" />
            새 세션
          </Button>
        )}
      </div>
    </div>
  );
}

/** 데스크톱은 "2026-08-25 10:34"까지만 보여준다 (updated_at[:16]). */
export function formatTimestamp(value: string): string {
  return value.replace("T", " ").slice(0, 16);
}
