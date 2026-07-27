import type { ComponentType } from "react";
import { NavLink } from "react-router-dom";
import {
  Activity,
  BarChart3,
  BookOpen,
  FlaskConical,
  Info,
  Layers,
  Sigma,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  path: string;
  icon: ComponentType<{ className?: string }>;
  enabled: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { label: "Home", path: "/", icon: Activity, enabled: false },
  { label: "Guide", path: "/guide", icon: BookOpen, enabled: false },
  { label: "Theory", path: "/theory", icon: Sigma, enabled: false },
  { label: "Case Study", path: "/case-study", icon: FlaskConical, enabled: false },
  { label: "I-V Curve", path: "/curves", icon: BarChart3, enabled: true },
  { label: "Field Map", path: "/fields", icon: Layers, enabled: true },
  { label: "About", path: "/about", icon: Info, enabled: false },
];

export function Sidebar() {
  return (
    <aside className="flex h-screen w-52 shrink-0 flex-col border-r border-outline-variant bg-sidebar py-3 text-sidebar-foreground">
      <div className="mb-4 flex items-center gap-2 px-3">
        <div className="flex h-6 w-6 items-center justify-center rounded-sm border border-outline-variant bg-primary/10">
          <BarChart3 className="h-3.5 w-3.5 text-primary" />
        </div>
        <div>
          <h1 className="text-xs font-bold leading-snug">Inverse Device</h1>
          <p className="font-mono text-[9px] uppercase tracking-wide text-on-surface-variant">
            Modeling
          </p>
        </div>
      </div>
      <nav className="flex-1 space-y-0.5 px-2">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          if (!item.enabled) {
            return (
              <span
                key={item.path}
                className="flex cursor-not-allowed items-center gap-2 rounded-sm px-2.5 py-1.5 text-on-surface-variant/40"
                title="Not built yet"
              >
                <Icon className="h-3.5 w-3.5" />
                <span className="text-xs">{item.label}</span>
                <span className="ml-auto rounded-sm bg-surface-container-highest px-1 py-0.5 font-mono text-[9px] text-on-surface-variant">
                  soon
                </span>
              </span>
            );
          }
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
