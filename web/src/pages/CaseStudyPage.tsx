import { useState } from "react";
import CaseListPage from "@/features/caseStudy/CaseListPage";

/**
 * Case Study는 목록과 케이스 진행, 두 화면을 오간다. 데스크톱 앱도 같은
 * 구조다 (panel.py의 show_cover) — 케이스 안으로 들어가면 화면 전체를 쓰고,
 * "← Case 목록"으로 돌아온다.
 *
 * 라우트를 나누지 않는 이유는 케이스 진행이 세션 상태에 묶여 있어서 URL로
 * 직접 들어오면 어느 단계를 그려야 할지 서버에 다시 물어야 하기 때문이다.
 * 지금은 목록을 거쳐 들어오는 흐름만 있으면 충분하다.
 */
export default function CaseStudyPage() {
  const [openSessionId, setOpenSessionId] = useState<string | null>(null);

  if (openSessionId) {
    // TODO: 케이스 진행 화면 (4단계). 다음 단계에서 붙인다.
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-xs text-on-surface-variant">
          세션 {openSessionId.slice(0, 8)} — 진행 화면은 준비 중입니다.
        </p>
      </div>
    );
  }

  return <CaseListPage onOpenSession={setOpenSessionId} />;
}
