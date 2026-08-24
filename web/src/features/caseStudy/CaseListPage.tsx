import { useCallback, useEffect, useState } from "react";
import { LogIn } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/features/auth/AuthProvider";
import { CaseCard } from "./components/CaseCard";
import { LearningOverview } from "./components/LearningOverview";
import { createSession, fetchPortfolio, fetchSessions, fetchTopics, getErrorMessage } from "./api";
import type { CaseProgress, LearningPortfolio, SessionSummary, TopicSummary } from "./types";

interface CaseListPageProps {
  onOpenSession: (sessionId: string) => void;
}

/**
 * 케이스 목록. 데스크톱 앱의 표지 화면에 해당한다 (panel.py의 _build_cover).
 *
 * 케이스와 설명은 로그인 없이도 볼 수 있고, 진행 상황과 학습 기록만 로그인이
 * 필요하다 — 둘러보러 온 사람을 로그인 벽으로 막지 않기 위해서다.
 */
export default function CaseListPage({ onOpenSession }: CaseListPageProps) {
  const { me } = useAuth();
  const [topics, setTopics] = useState<TopicSummary[]>([]);
  const [portfolio, setPortfolio] = useState<LearningPortfolio | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    fetchTopics().then(setTopics).catch((err) => setError(getErrorMessage(err)));
  }, []);

  // 진행 상황은 로그인한 사람에게만 있다.
  const loadProgress = useCallback(() => {
    if (!me.authenticated) {
      setPortfolio(null);
      setSessions([]);
      return;
    }
    Promise.all([fetchPortfolio(), fetchSessions()])
      .then(([loadedPortfolio, loadedSessions]) => {
        setPortfolio(loadedPortfolio);
        setSessions(loadedSessions);
      })
      .catch((err) => setError(getErrorMessage(err)));
  }, [me.authenticated]);

  useEffect(loadProgress, [loadProgress]);

  async function start(topicId: string) {
    if (starting) return;
    setStarting(true);
    try {
      const session = await createSession(topicId);
      onOpenSession(session.session_id);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setStarting(false);
    }
  }

  const progressByTopic = new Map(portfolio?.cases.map((item) => [item.topic_id, item]));
  const latestByTopic = new Map<string, SessionSummary>();
  for (const session of sessions) {
    // 목록은 최근 순이라 먼저 만난 것이 가장 최근이다.
    if (!latestByTopic.has(session.topic_id)) latestByTopic.set(session.topic_id, session);
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 p-6">
        <header>
          <h1 className="text-xl font-bold">Case Study Learning Lab</h1>
          <p className="mt-1 text-xs text-on-surface-variant">
            Case별 진행 상황을 확인하고 학습을 이어가세요.
          </p>
        </header>

        {error && <p className="text-[11px] text-destructive">{error}</p>}

        {me.authenticated && portfolio ? (
          <LearningOverview
            portfolio={portfolio}
            sessions={sessions}
            topics={topics}
            onOpen={onOpenSession}
          />
        ) : (
          <SignInNotice />
        )}

        <div className="grid gap-4 md:grid-cols-2">
          {topics.map((topic, index) => (
            <CaseCard
              key={topic.topic_id}
              index={index}
              topic={topic}
              progress={progressByTopic.get(topic.topic_id) ?? placeholder(topic, index)}
              latest={latestByTopic.get(topic.topic_id)}
              onOpen={onOpenSession}
              onStart={start}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function SignInNotice() {
  const { login } = useAuth();
  return (
    <section className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-outline-variant bg-surface-container-low p-4">
      <p className="text-xs text-on-surface-variant">
        로그인하면 진행 상황이 저장되어 다음에 이어서 학습할 수 있습니다.
      </p>
      <Button size="sm" variant="outline" className="gap-1.5 text-xs" onClick={login}>
        <LogIn className="h-3.5 w-3.5" />
        로그인
      </Button>
    </section>
  );
}

/**
 * 비로그인일 때 쓸 진행 상황. 첫 케이스만 열어 두는 이유는, 선행 조건이
 * 실제로 있고 진도를 모르는 상태에서 전부 열어 보이면 눌렀을 때 로그인
 * 요구로 막히기 때문이다.
 */
function placeholder(topic: TopicSummary, index: number): CaseProgress {
  return {
    topic_id: topic.topic_id,
    title: topic.title,
    status: index === 0 ? "not_started" : "locked",
    session_count: 0,
    completed_session_count: 0,
    latest_step: null,
    completed_concepts: [],
    remaining_concepts: [],
    updated_at: null,
    prerequisites: topic.prerequisite_topic_ids,
    prerequisites_met: index === 0,
  };
}
