import { useEffect, useState } from "react";

import { ApiError, api } from "@/api/client";
import type { SetupInfo } from "@/api/types";
import { useLiveSession, useLiveStatus, useStaleSeconds } from "@/live/useLive";

/**
 * The four states of the dashboard, along the bottom.
 *
 * `paused` and `waiting` look different on purpose. Waiting means the game has never sent anything,
 * so the bar carries the port to type into the game. Paused means it was sending and stopped, so it
 * counts the silence instead; the panels keep their last values, dimmed. See `docs/design.md`.
 *
 * #53 builds the full first-run setup screen. This is the bar only.
 */
export function StatusBar() {
  const status = useLiveStatus();
  const session = useLiveSession();
  const stale = useStaleSeconds();
  const setup = useSetupInfo(status === "offline" || status === "waiting");

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
          </>
        )}
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

/**
 * `/api/setup`, polled only while it could still tell us something.
 *
 * Once packets are flowing the port is not news, and the live socket already reports everything that
 * changes, so polling then would be a request every two seconds for nothing.
 */
const POLL_MS = 2000;

function useSetupInfo(wanted: boolean): SetupInfo | null {
  const [setup, setSetup] = useState<SetupInfo | null>(null);

  useEffect(() => {
    if (!wanted) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      try {
        setSetup(await api.setup(controller.signal));
      } catch (error) {
        if (controller.signal.aborted) return;
        if (error instanceof ApiError || error instanceof TypeError) setSetup(null);
      }
      if (!controller.signal.aborted) timer = setTimeout(() => void poll(), POLL_MS);
    };

    void poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [wanted]);

  return setup;
}
