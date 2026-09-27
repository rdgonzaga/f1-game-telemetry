import { Link, useParams } from "react-router-dom";

import { api } from "@/api/client";
import { useApi } from "@/api/useApi";
import { Panel } from "@/components/Panel";
import { LapTable } from "@/components/sessions/LapTable";
import { formatStarted } from "@/lib/laps";
import { formatLapTime } from "@/lib/timing";

/** One saved session: what it was, its best lap, and every lap to pick from. */
export default function Session() {
  const { sessionId = "" } = useParams();
  const session = useApi(`session:${sessionId}`, (signal) => api.session(sessionId, signal));

  if (session.state !== "ready") {
    const text = {
      loading: "Loading the session.",
      missing: "This session isn't saved here any more.",
      failed: "Can't reach the app's backend to load this session.",
    }[session.state];
    return (
      <Panel title="Session">
        <p className="text-text-3">{text}</p>
        <Link to="/sessions" className="mt-[var(--f1-space-2)] inline-block text-sm text-text-2 hover:underline">
          All sessions
        </Link>
      </Panel>
    );
  }

  const data = session.data;
  const best = data.laps.find((lap) => lap.number === data.best_lap);
  return (
    <div className="flex flex-col gap-[var(--f1-gap)]">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <Link to="/sessions" className="text-sm text-text-3 hover:text-text-2 hover:underline">
            Sessions
          </Link>
          <h1 className="truncate text-2xl font-extrabold tracking-[var(--f1-tracking-display)] text-text-1">
            {data.track.name}
          </h1>
          <p className="text-sm text-text-3">
            {data.session_type.name} · {data.formula.name} · {formatStarted(data.started_at)}
          </p>
        </div>
        <div className="flex flex-col items-end">
          <span className="tnum font-mono text-xl font-semibold text-timing-best">
            {formatLapTime(best?.lap_time_ms)}
          </span>
          <span className="text-xs tracking-[var(--f1-tracking-label)] text-text-3 uppercase">
            {best ? `Best lap · lap ${best.number}` : "No complete valid lap"}
          </span>
        </div>
      </header>

      <Panel
        title="Laps"
        aside={<span className="text-xs text-text-3">Click a lap to open it</span>}
        className="[&>div]:p-0"
      >
        {data.laps.length ? (
          <LapTable sessionId={data.id} laps={data.laps} bestLap={data.best_lap} />
        ) : (
          <p className="p-[var(--f1-panel-pad)] text-text-3">No lap was completed in this session.</p>
        )}
      </Panel>
    </div>
  );
}
