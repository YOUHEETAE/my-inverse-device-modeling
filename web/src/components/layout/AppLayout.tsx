import type { ReactNode } from "react";
import { ChevronRight } from "lucide-react";
import { AccountMenu } from "@/features/auth/AccountMenu";
import { Sidebar } from "./Sidebar";

interface AppLayoutProps {
  title: string;
  breadcrumb: string[];
  children: ReactNode;
}

export function AppLayout({ title, breadcrumb, children }: AppLayoutProps) {
  return (
    <div className="flex h-screen w-screen overflow-hidden">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden bg-background">
        {/* h-11: 계정 아바타가 들어가면서 h-9(36px)로는 너무 눌렸다. */}
        <header className="flex h-11 shrink-0 items-center gap-3 border-b border-outline-variant bg-surface-container px-3">
          <h2 className="text-xs font-bold">{title}</h2>
          <div className="h-3 w-px bg-outline" />
          <nav className="flex items-center gap-1.5 font-mono text-[11px] text-on-surface-variant">
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
          <div className="ml-auto flex items-center">
            <AccountMenu />
          </div>
        </header>
        <main className="flex-1 overflow-hidden">{children}</main>
      </div>
    </div>
  );
}
