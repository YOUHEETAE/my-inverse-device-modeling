import { useState } from "react";
import { ChevronDown, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { formatTimestamp } from "./CaseCard";
import type { CaseProgress, LearningPortfolio, SessionSummary, TopicSummary } from "../types";

// 데스크톱 앱의 단계 이름 (panel.py의 _cover_step_label).
const STEP_LABELS: Record<string, string> = {
  INTRODUCTION: "Case 이해",
  BASELINE_SETUP: "Case 이해",
  PREDICTION_QUESTION: "초기 예측",
  PREDICTION_SUBMITTED: "실험 대기",
  SIMULATION_RUNNING: "실험 진행 중",
  RESULT_READY: "결과 관찰",
  OBSERVATION_QUESTION: "결과 관찰",
  OBSERVATION_SUBMITTED: "채점 대기",
  FEEDBACK_READY: "최종 설명",
  NEXT_EXPERIMENT: "최종 설명",
  SESSION_COMPLETE: "완료",
  ERROR: "복구 필요",
};

interface LearningOverviewProps {
  portfolio: LearningPortfolio;
  sessions: SessionSummary[];
  topics: TopicSummary[];
  onOpen: (sessionId: string) => void;
}

export function LearningOverview({ portfolio, sessions, topics, onOpen }: LearningOverviewProps) {
  const [showRecords, setShowRecords] = useState(false);

  const recent = mostRecent(portfolio.cases);
  const titles = new Map(topics.map((topic) => [topic.topic_id, topic.title]));
  const percent = portfolio.total_case_count
    ? (portfolio.completed_case_count / portfolio.total_case_count) * 100
    : 0;

  return (
    <section className="rounded-md border border-outline-variant bg-surface-container-low p-4">
      <h2 className="text-xs font-bold uppercase tracking-wide">내 학습 현황</h2>

      <p className="mt-3 text-sm font-bold">
        현재 제공 Case {portfolio.completed_case_count}/{portfolio.total_case_count} 완료
      </p>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-container-highest">
        <div
          className="h-full rounded-full bg-accent-green transition-[width] duration-500 ease-out motion-reduce:transition-none"
          style={{ width: `${percent}%` }}
        />
      </div>

      {recent && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <p className="text-[11px] text-on-surface-variant">
            최근 학습 · {recent.title} · {formatTimestamp(recent.updated_at ?? "")}
          </p>
          {/* 끝내지 않은 케이스만 이어서 할 수 있다. */}
          {recent.latest_step !== "SESSION_COMPLETE" && resume(sessions, recent.topic_id) && (
            <Button
              size="sm"
              variant="outline"
              className="h-6 gap-1 px-2 text-[10px]"
              onClick={() => onOpen(resume(sessions, recent.topic_id)!.session_id)}
            >
              <Play className="h-3 w-3" />
              이어서 하기
            </Button>
          )}
        </div>
      )}

      {sessions.length > 0 && (
        <>
          <Button
            variant="ghost"
            size="sm"
            className="mt-2 h-6 gap-1 px-1 text-[11px] text-on-surface-variant"
            onClick={() => setShowRecords((value) => !value)}
            aria-expanded={showRecords}
          >
            학습 기록 {sessions.length}개 {showRecords ? "접기" : "보기"}
            <ChevronDown
              className={cn(
                "h-3 w-3 transition-transform duration-200 motion-reduce:transition-none",
                showRecords && "rotate-180",
              )}
            />
          </Button>

          {/* grid 0fr -> 1fr 은 내용 높이를 모르고도 부드럽게 열고 닫는다. */}
          <div
            className={cn(
              "grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none",
              showRecords ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
            )}
          >
            <div className="overflow-hidden">
              <ul className="max-h-64 space-y-1 overflow-y-auto pt-2">
                {sessions.map((session) => (
                  <li
                    key={session.session_id}
                    className="flex items-center gap-2 rounded-sm px-2 py-1.5 hover:bg-surface-container"
                  >
                    <span className="min-w-0 flex-1 truncate text-[11px]">
                      <span className="text-on-surface-variant">
                        {titles.get(session.topic_id) ?? session.topic_id} ·{" "}
                      </span>
                      {session.display_name}
                    </span>
                    <span className="shrink-0 font-mono text-[10px] text-on-surface-variant">
                      {STEP_LABELS[session.current_step] ?? session.current_step} ·{" "}
                      {formatTimestamp(session.updated_at)}
                    </span>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-6 shrink-0 px-2 text-[10px]"
                      onClick={() => onOpen(session.session_id)}
                    >
                      {session.completed ? "결과 보기" : "이어서 하기"}
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </>
      )}
    </section>
  );
}

function mostRecent(cases: CaseProgress[]): CaseProgress | undefined {
  return cases
    .filter((item) => item.updated_at)
    .sort((a, b) => (a.updated_at! < b.updated_at! ? 1 : -1))[0];
}

function resume(sessions: SessionSummary[], topicId: string): SessionSummary | undefined {
  return sessions.find((session) => session.topic_id === topicId && !session.completed);
}
