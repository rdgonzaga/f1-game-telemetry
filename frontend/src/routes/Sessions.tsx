import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "@/api/client";
import type { SessionSummary } from "@/api/types";
import { useApi } from "@/api/useApi";
import { Panel } from "@/components/Panel";
import { SESSION_KINDS, formatStarted, sessionKind, type SessionKind } from "@/lib/laps";
import { formatLapTime } from "@/lib/timing";
import { cn } from "@/lib/utils";

const STATUS: Record<SessionSummary["status"], string> = {
  recording: "Recording",
  complete: "Saved",
  interrupted: "Interrupted",
};

/** Every saved session, newest first as the API sends them, filtered by kind. */
export default function Sessions() {
  const sessions = useApi("sessions", (signal) => api.sessions(signal));
  const [filter, setFilter] = useState<SessionKind | null>(null);

  if (sessions.state === "loading") return <Message title="Sessions">Loading saved sessions.</Message>;
  if (sessions.state !== "ready") {
    return <Message title="Sessions">Can&rsquo;t reach the app&rsquo;s backend to list sessions.</Message>;
  }
  const shown = sessions.data.filter((s) => filter === null || sessionKind(s.session_type.id) === filter);

  return (
    <div className="flex flex-col gap-[var(--f1-gap)]">
      <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by session type">
        {[null, ...SESSION_KINDS].map((kind) => (
          <button
            key={kind ?? "all"}
            type="button"
            aria-pressed={filter === kind}
            onClick={() => setFilter(kind)}
            className={cn(
              "h-[var(--f1-control-h)] rounded-full border px-4 text-sm font-semibold transition-colors",
              filter === kind
                ? "border-border-hover bg-surface-2 text-text-1"
                : "border-border text-text-3 hover:bg-surface-2 hover:text-text-2",
            )}
          >
            {kind ?? "All"}
          </button>
        ))}
      </div>

      {shown.length === 0 ? (
        <Message title="Sessions">
          {filter ? `No ${filter} sessions yet.` : "No sessions yet."} Drive one and it lands here.
        </Message>
      ) : (
        <ul className="flex flex-col gap-2">
          {shown.map((session) => (
            <li key={session.id}>
              <SessionRow session={session} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function SessionRow({ session }: { session: SessionSummary }) {
  const best = session.laps.find((lap) => lap.number === session.best_lap);
  return (
    <Link
      to={`/sessions/${encodeURIComponent(session.id)}`}
      className="flex items-center gap-4 rounded-md border border-border bg-surface-1 px-[var(--f1-space-4)] py-3 transition-colors hover:border-border-hover hover:bg-surface-2"
    >
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-lg font-semibold text-text-1">{session.track.name}</span>
        <span className="truncate text-sm text-text-3">
          {session.session_type.name} · {session.formula.name} · {session.laps.length}{" "}
          {session.laps.length === 1 ? "lap" : "laps"} · {formatStarted(session.started_at)}
        </span>
      </span>
      <span className="flex flex-col items-end">
        <span className="tnum font-mono text-lg text-timing-best">{formatLapTime(best?.lap_time_ms)}</span>
        <span className="text-xs tracking-[var(--f1-tracking-label)] text-text-3 uppercase">Best lap</span>
      </span>
      <span
        className={cn(
          "w-28 rounded-full border px-2 py-0.5 text-center text-xs font-semibold tracking-[var(--f1-tracking-label)] uppercase",
          session.status === "recording" ? "border-ok/50 text-ok" : "border-border-soft text-text-3",
        )}
      >
        {STATUS[session.status]}
      </span>
    </Link>
  );
}

function Message({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Panel title={title}>
      <p className="text-text-3">{children}</p>
    </Panel>
  );
}
