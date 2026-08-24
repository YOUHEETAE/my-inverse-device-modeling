import type { ComponentType } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import {
  Activity,
  BarChart3,
  BookOpen,
  FlaskConical,
  Layers,
  Sigma,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { THEORY_CHAPTERS } from "@/features/theory/theoryChapters";

interface NavItem {
  label: string;
  path: string;
  icon: ComponentType<{ className?: string }>;
  // Rendered as a nested, indented list right under this item, but only
  // while its own route is active — lets Theory/Case Study's chapter list
  // live in the one main sidebar instead of a second TOC column that pushed
  // page content off-center.
  subItems?: { id: string; label: string }[];
}

const NAV_ITEMS: NavItem[] = [
  { label: "Home", path: "/", icon: Activity },
  { label: "Guide", path: "/guide", icon: BookOpen },
  { label: "Theory", path: "/theory", icon: Sigma, subItems: THEORY_CHAPTERS },
  // 하위 목록을 두지 않는다 — 케이스가 8개고 진행 상황과 잠금 상태까지
  // 보여줘야 해서 목록 화면이 따로 있다. 데스크톱도 탭 하나뿐이다.
  { label: "Case Study", path: "/case-study", icon: FlaskConical },
  { label: "I-V Curve", path: "/curves", icon: BarChart3 },
  { label: "Field Map", path: "/fields", icon: Layers },
];

export function Sidebar() {
  const location = useLocation();
  const activeSection = new URLSearchParams(location.search).get("section") ?? "overview";

  return (
    <aside className="flex h-screen w-52 shrink-0 flex-col border-r border-outline-variant bg-sidebar py-3 text-sidebar-foreground">
      <div className="mb-4 flex items-center gap-2 px-3">
        <div className="flex h-6 w-6 items-center justify-center rounded-sm border border-outline-variant bg-primary/10">
          <BarChart3 className="h-3.5 w-3.5 text-primary" />
        </div>
        <div>
          <h1 className="flex items-baseline gap-1 text-xs font-bold leading-snug">
            SemiScope
            <span className="text-[10px] font-bold italic tracking-tight text-primary">beta</span>
          </h1>
          <p className="font-mono text-[9px] uppercase tracking-wide text-on-surface-variant">
            AI
          </p>
        </div>
      </div>
      <nav className="flex-1 space-y-0.5 px-2">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isOnThisPage = location.pathname === item.path;
          return (
            <div key={item.path}>
              <NavLink
                to={item.path}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2 rounded-sm px-2.5 py-1.5 transition-colors",
                    isActive
                      ? "border border-primary/20 bg-primary/10 font-semibold text-primary"
                      : "text-on-surface-variant hover:bg-surface-container-high",
                  )
                }
              >
                <Icon className="h-3.5 w-3.5" />
                <span className="text-xs">{item.label}</span>
              </NavLink>
              {item.subItems && isOnThisPage && (
                <div className="mb-1 ml-3.5 mt-0.5 flex flex-col gap-0.5 border-l border-outline-variant pl-2.5">
                  {item.subItems.map((sub) => (
                    <Link
                      key={sub.id}
                      to={`${item.path}?section=${sub.id}`}
                      className={cn(
                        "rounded-sm px-2 py-1 text-[11px] leading-snug transition-colors",
                        activeSection === sub.id
                          ? "font-semibold text-primary"
                          : "text-on-surface-variant/80 hover:bg-surface-container-high hover:text-foreground",
                      )}
                    >
                      {sub.label}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
