import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  path: string;
  enabled: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { label: "Home", path: "/", enabled: false },
  { label: "Guide", path: "/guide", enabled: false },
  { label: "Theory", path: "/theory", enabled: false },
  { label: "Case Study", path: "/case-study", enabled: false },
  { label: "I-V Curve", path: "/curves", enabled: true },
  { label: "Field Map", path: "/fields", enabled: false },
  { label: "About", path: "/about", enabled: false },
];

export function Sidebar() {
  return (
    <aside className="flex h-screen w-56 shrink-0 flex-col border-r bg-sidebar text-sidebar-foreground">
      <div className="border-b px-4 py-4">
        <span className="text-sm font-semibold tracking-tight">
          Inverse Device Modeling
        </span>
      </div>
      <nav className="flex flex-col gap-0.5 p-2">
        {NAV_ITEMS.map((item) =>
          item.enabled ? (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                cn(
                  "rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                )
              }
            >
              {item.label}
            </NavLink>
          ) : (
            <span
              key={item.path}
              className="cursor-not-allowed rounded-md px-3 py-2 text-sm font-medium text-sidebar-foreground/30"
              title="Not built yet"
            >
              {item.label}
            </span>
          ),
        )}
      </nav>
    </aside>
  );
}
