import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "@/api/client";
import { useApi } from "@/api/useApi";
import { Panel } from "@/components/Panel";
import { LapTable } from "@/components/sessions/LapTable";
import { Button } from "@/components/ui/button";
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
        <div className="flex items-end gap-6">
          <div className="flex flex-col items-end">
            <span className="tnum font-mono text-xl font-semibold text-timing-best">
              {formatLapTime(best?.lap_time_ms)}
            </span>
            <span className="text-xs tracking-[var(--f1-tracking-label)] text-text-3 uppercase">
              {best ? `Best lap · lap ${best.number}` : "No complete valid lap"}
            </span>
          </div>
          {data.laps.length > 1 && (
            <Button variant="outline" asChild>
              <Link to={`/compare?session=${encodeURIComponent(data.id)}`}>Compare laps</Link>
            </Button>
          )}
          {data.status !== "recording" && <DeleteSession sessionId={data.id} />}
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

/** Two clicks, the second on a red button, so a stray click can't lose a session. No browser dialog. */
function DeleteSession({ sessionId }: { sessionId: string }) {
  const navigate = useNavigate();
  const [step, setStep] = useState<"idle" | "confirm" | "deleting">("idle");
  const [failed, setFailed] = useState<string | null>(null);

  if (step === "idle") {
    return (
      <Button variant="outline" onClick={() => setStep("confirm")}>
        Delete
      </Button>
    );
  }

  const remove = () => {
    setStep("deleting");
    setFailed(null);
    api.deleteSession(sessionId).then(
      () => navigate("/sessions", { replace: true }),
      (error: unknown) => {
        setFailed(error instanceof Error ? error.message : String(error));
        setStep("confirm");
      },
    );
  };

  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex gap-2">
        <Button variant="ghost" disabled={step === "deleting"} onClick={() => setStep("idle")}>
          Cancel
        </Button>
        <Button variant="destructive" disabled={step === "deleting"} onClick={remove}>
          Delete session and laps
        </Button>
      </div>
      {failed && <p className="text-sm text-critical">Couldn&rsquo;t delete: {failed}</p>}
    </div>
  );
}
