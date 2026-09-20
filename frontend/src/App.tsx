import { Activity, GitCompareArrows, ListOrdered } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { StatusBar } from "@/components/StatusBar";
import { cn } from "@/lib/utils";

const LINKS = [
  { to: "/", label: "Live", icon: Activity, end: true },
  { to: "/sessions", label: "Sessions", icon: ListOrdered, end: false },
  { to: "/compare", label: "Compare", icon: GitCompareArrows, end: false },
];

/**
 * The frame: a fixed nav rail, the route, and the status bar along the bottom.
 *
 * Nothing here scrolls. Panels scroll inside the route, so a live value never moves because something else grew.
 */
export default function App() {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-surface-0 text-text-2">
      <nav className="flex w-[var(--f1-rail-w)] shrink-0 flex-col gap-1 border-r border-border bg-surface-1 p-2">
        <div className="mb-2 px-2 pt-2">
          <span className="font-sans text-md font-extrabold tracking-[var(--f1-tracking-display)] text-text-1">
            F1 TELEMETRY
          </span>
        </div>
        {LINKS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              cn(
                "flex h-[var(--f1-control-h)] items-center gap-3 rounded-sm px-3 text-sm font-semibold transition-colors",
                isActive ? "bg-surface-2 text-text-1" : "text-text-3 hover:bg-surface-2 hover:text-text-2",
              )
            }
          >
            <Icon className="size-4" aria-hidden />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="flex min-w-0 flex-1 flex-col">
        <main className="min-h-0 flex-1 overflow-auto p-[var(--f1-gap)]">
          <Outlet />
        </main>
        <StatusBar />
      </div>
    </div>
  );
}
