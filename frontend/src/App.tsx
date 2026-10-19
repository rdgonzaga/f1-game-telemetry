import { NavLink, Outlet } from "react-router-dom";

import { StatusBar } from "@/components/StatusBar";
import { cn } from "@/lib/utils";

const LINKS = [
  { to: "/", label: "Live", end: true },
  { to: "/sessions", label: "Sessions", end: false },
  { to: "/compare", label: "Compare", end: false },
  { to: "/setup", label: "Setup", end: false },
];

/**
 * The frame: the top bar, the route, and the status bar along the bottom.
 *
 * The top bar is the f1-prediction site's: black, a red rule under it, the skewed red mark and uppercase links.
 * Nothing here scrolls. Panels scroll inside the route, so a live value never moves because something else grew.
 */
export default function App() {
  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-surface-0 text-text-2">
      <header className="shrink-0 border-b-[length:var(--f1-topbar-rule)] border-brand bg-black">
        <div className="flex h-[var(--f1-topbar-h)] items-center gap-6 px-[var(--f1-space-4)]">
          <NavLink to="/" className="flex items-center gap-2 text-md font-black whitespace-nowrap text-text-1">
            <span className="size-3.5 -skew-x-[20deg] bg-brand" aria-hidden />
            F1<span className="text-brand">TELEMETRY</span>
          </NavLink>
          <nav className="flex gap-0.5 self-stretch overflow-x-auto" aria-label="Main">
            {LINKS.map(({ to, label, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  cn(
                    "flex items-center border-b-[length:var(--f1-topbar-rule)] px-2.5 pt-[3px] text-sm font-bold tracking-[0.06em] whitespace-nowrap uppercase transition-colors",
                    isActive ? "border-text-1 text-text-1" : "border-transparent text-text-2 hover:text-text-1",
                  )
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="min-h-0 flex-1 overflow-auto p-[var(--f1-gap)]">
        <Outlet />
      </main>
      <StatusBar />
    </div>
  );
}
