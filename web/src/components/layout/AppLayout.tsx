import { useEffect, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { ChevronRight, Menu, X } from "lucide-react";
import { AccountMenu } from "@/features/auth/AccountMenu";
import { Sidebar } from "./Sidebar";

interface AppLayoutProps {
  title: string;
  breadcrumb: string[];
  children: ReactNode;
}

/**
 * 화면 껍데기.
 *
 * md(768px) 아래에서는 사이드바가 폭을 나눠 쓰지 않고 서랍으로 물러난다.
 * 208px짜리 사이드바에 페이지 안쪽 패널 288px까지 더하면 496px인데, 휴대폰
 * 폭이 390px이라 내용이 들어갈 자리가 애초에 없었다. 게다가 이 바깥 상자가
 * overflow-hidden이라 넘친 부분으로 스크롤도 되지 않아, 화면이 그냥
 * 뭉개졌다.
 */
export function AppLayout({ title, breadcrumb, children }: AppLayoutProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();

  // 주소가 바뀌면 닫는다. 사이드바 항목은 스스로 닫지만, 페이지 안에서
  // 이동하는 길(예: Case 카드 클릭)도 있어서 여기서 한 번 더 받는다.
  useEffect(() => setMenuOpen(false), [location.pathname]);

  return (
    <div className="flex h-screen w-screen overflow-hidden">
      {/* 넓은 화면: 늘 자리를 차지하는 기둥 */}
      <div className="hidden md:flex">
        <Sidebar />
      </div>

      {/* 좁은 화면: 내용 위로 덮는 서랍 */}
      {menuOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden">
          <Sidebar onNavigate={() => setMenuOpen(false)} />
          {/* 바깥을 눌러도 닫힌다 — 닫기 버튼을 찾지 못해도 빠져나올 수 있게. */}
          <button
            type="button"
            aria-label="메뉴 닫기"
            className="flex-1 bg-black/50"
            onClick={() => setMenuOpen(false)}
          />
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden bg-background">
        {/* h-11: 계정 아바타가 들어가면서 h-9(36px)로는 너무 눌렸다. */}
        <header className="flex h-11 shrink-0 items-center gap-2 border-b border-outline-variant bg-surface-container px-3 md:gap-3">
          <button
            type="button"
            aria-label={menuOpen ? "메뉴 닫기" : "메뉴 열기"}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
            className="-ml-1 shrink-0 rounded-sm p-1 text-on-surface-variant hover:bg-surface-container-high md:hidden"
          >
            {menuOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
          <h2 className="shrink-0 text-xs font-bold">{title}</h2>
          <div className="hidden h-3 w-px bg-outline sm:block" />
          {/* 좁은 화면에서 제일 먼저 버릴 수 있는 것이 breadcrumb이다 —
              현재 위치는 제목이 이미 말해준다. */}
          <nav className="hidden items-center gap-1.5 font-mono text-[11px] text-on-surface-variant sm:flex">
            {breadcrumb.map((crumb, index) => (
              <span key={crumb} className="flex items-center gap-2">
                {index > 0 && <ChevronRight className="h-3 w-3" />}
                <span className={index === breadcrumb.length - 1 ? "text-foreground" : ""}>
                  {crumb}
                </span>
              </span>
            ))}
          </nav>
          {/* 계정은 "어디로 갈까"(사이드바)와 성격이 다른 관심사라 상단 오른쪽에
              둔다. */}
          <div className="ml-auto flex shrink-0 items-center">
            <AccountMenu />
          </div>
        </header>
        {/* 좁은 화면에서는 세로로 흐르게 둔다. 넓은 화면은 지금처럼 한 화면
            안에서 각 칸이 알아서 스크롤한다. */}
        <main className="flex-1 overflow-y-auto md:overflow-hidden">{children}</main>
      </div>
    </div>
  );
}
