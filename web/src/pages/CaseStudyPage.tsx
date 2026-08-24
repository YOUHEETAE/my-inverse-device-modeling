import { useState } from "react";
import CaseListPage from "@/features/caseStudy/CaseListPage";
import CaseSessionPage from "@/features/caseStudy/CaseSessionPage";

interface OpenCase {
  sessionId: string;
  /** 목록에서의 순서. 상단에 "Case 03"으로 보여주는 값. */
  caseNumber: number;
}

/**
 * Case Study는 목록과 케이스 진행, 두 화면을 오간다. 데스크톱 앱도 같은
 * 구조다 (panel.py의 show_cover) — 케이스 안으로 들어가면 화면 전체를 쓰고,
 * "Case 목록"으로 돌아온다.
 *
 * 라우트를 나누지 않는 이유는 진행 상태가 세션에 있어서 URL만으로는 어느
 * 단계를 그릴지 알 수 없기 때문이다. 서버에서 세션을 받아야 정해진다.
 */
export default function CaseStudyPage() {
  const [open, setOpen] = useState<OpenCase | null>(null);

  if (open) {
    return (
      <CaseSessionPage
        sessionId={open.sessionId}
        caseNumber={open.caseNumber}
        onBack={() => setOpen(null)}
      />
    );
  }

  return (
    <CaseListPage
      onOpenSession={(sessionId, caseNumber) => setOpen({ sessionId, caseNumber })}
    />
  );
}
