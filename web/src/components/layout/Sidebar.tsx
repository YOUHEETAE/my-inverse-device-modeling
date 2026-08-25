import type { ComponentType } from "react";
import { NavLink } from "react-router-dom";
import {
  Activity,
  BarChart3,
  BookOpen,
  FlaskConical,
  Layers,
  Sigma,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  path: string;
  icon: ComponentType<{ className?: string }>;
}

// 하위 목록을 두지 않는다 — Theory도 Case Study도 장/케이스를 카드로 늘어놓는
// 목록 화면을 따로 갖고 있고, 거기서는 소개와 실습 도구 유무(Theory) 또는
// 진행 상황과 잠금 상태(Case Study)까지 보여줄 수 있다. 사이드바에 같은
// 목록을 한 번 더 펼치면 길이만 흔들린다.
const NAV_ITEMS: NavItem[] = [
  { label: "Home", path: "/", icon: Activity },
  { label: "Guide", path: "/guide", icon: BookOpen },
  { label: "Theory", path: "/theory", icon: Sigma },
  { label: "Case Study", path: "/case-study", icon: FlaskConical },
  { label: "I-V Curve", path: "/curves", icon: BarChart3 },
  { label: "Field Map", path: "/fields", icon: Layers },
];

export function Sidebar() {
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
          return (
            <NavLink
              key={item.path}
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
          );
        })}
      </nav>
    </aside>
  );
}
