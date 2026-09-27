import { useRef } from "react";

import { FORMULA_F2 } from "@/api/types";
import { useSetup, useSetupPoll } from "@/live/setup";
import { useLiveFrame, useLiveSession, useLiveStatus, useStaleSeconds } from "@/live/useLive";

/**
 * The four states of the dashboard, along the bottom.
 *
 * `paused` and `waiting` look different on purpose. Waiting means the game has never sent anything,
 * so the bar carries the port to type into the game. Paused means it was sending and stopped, so it
 * counts the silence instead; the panels keep their last values, dimmed. See `docs/design.md`.
 *
 * The packet format and rate change with every snapshot, so they are written through refs, not rendered.
 */
export function StatusBar() {
  const status = useLiveStatus();
  const session = useLiveSession();
  const stale = useStaleSeconds();
  useSetupPoll(status === "offline" || status === "waiting" ? POLL_MS : null);
  const setup = useSetup();
  const format = useRef<HTMLSpanElement>(null);
  const rate = useRef<HTMLSpanElement>(null);

  useLiveFrame((snapshot) => {
    if (format.current) format.current.textContent = snapshot.packet_format?.toString() ?? "—";
    if (rate.current) rate.current.textContent = snapshot.connected ? String(snapshot.packets_per_second) : "0";
  });

  return (
    <footer className="flex h-[var(--f1-statusbar-h)] shrink-0 items-center gap-3 border-t border-border bg-surface-sunken px-3 text-xs tracking-[var(--f1-tracking-label)] uppercase">
      <Dot status={status} />
      <span className="text-text-2">{LABEL[status]}</span>

      {status === "paused" && (
        <span className="tnum rounded-sm bg-warn px-2 py-0.5 font-semibold text-text-on-fill normal-case">
          no packets for {stale}s
        </span>
      )}

      {status === "waiting" && setup && (
        <span className="tnum text-text-3">
          Listening on {setup.udp_host}:{setup.udp_port}
        </span>
      )}

      {status === "offline" && <span className="text-text-3">Retrying</span>}

      {setup?.packet_warning != null && <span className="text-warn normal-case">{setup.packet_warning}</span>}

      <span className="ml-auto flex items-center gap-3">
        {session && (
          <>
            <span className="text-text-3">{session.track.name}</span>
            <span className="text-text-3">{session.session_type.name}</span>
            <span className="tnum text-text-3">
              {session.laps.length}
              {session.total_laps > 0 && ` / ${session.total_laps}`} laps
            </span>
            <span className="text-text-2">{session.formula.id === FORMULA_F2 ? "F2" : "F1"}</span>
          </>
        )}
        {status !== "offline" && (
          <>
            <span className="tnum text-text-3">
              format{" "}
              <span ref={format} className="text-text-2">
                —
              </span>
            </span>
            <span className="tnum text-text-3">
              <span ref={rate} className="text-text-2">
                0
              </span>{" "}
              pkt/s
            </span>
          </>
        )}
        {setup && <span className="tnum text-text-3">UDP {setup.udp_port}</span>}
      </span>
    </footer>
  );
}

const LABEL: Record<ReturnType<typeof useLiveStatus>, string> = {
  offline: "Backend offline",
  waiting: "Waiting for game",
  live: "Live",
  paused: "Paused",
};

function Dot({ status }: { status: ReturnType<typeof useLiveStatus> }) {
  const colour = {
    offline: "bg-critical",
    waiting: "bg-idle",
    live: "bg-ok",
    paused: "bg-warn",
  }[status];
  return <span className={`size-2 rounded-full ${colour}`} aria-hidden />;
}

/** How often `/api/setup` is asked while the game has not been heard from. */
const POLL_MS = 2000;
