import { useEffect, useState } from "react";

import { ApiError, api } from "@/api/client";
import type { SetupInfo } from "@/api/types";

/**
 * Whether the backend is there and whether the game is sending, polled from `/api/setup`.
 *
 * Deliberately thin: #53 owns the real status bar and the first-run setup screen, and #22 owns the live socket
 * that will replace this poll. It exists now so the scaffold proves the whole path end to end rather than
 * claiming it works.
 */
const POLL_MS = 2000;

type State = { kind: "loading" } | { kind: "offline" } | { kind: "ok"; setup: SetupInfo };

export function StatusBar() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      try {
        setState({ kind: "ok", setup: await api.setup(controller.signal) });
      } catch (error) {
        if (controller.signal.aborted) return;
        // Anything that is not an answer from the API means the app is not running or not reachable.
        if (error instanceof ApiError || error instanceof TypeError) setState({ kind: "offline" });
      }
      if (!controller.signal.aborted) timer = setTimeout(() => void poll(), POLL_MS);
    };

    void poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, []);

  return (
    <footer className="flex h-[var(--f1-statusbar-h)] shrink-0 items-center gap-3 border-t border-border bg-surface-sunken px-3 text-xs tracking-[var(--f1-tracking-label)] uppercase">
      <Indicator state={state} />
    </footer>
  );
}

function Indicator({ state }: { state: State }) {
  if (state.kind === "loading") {
    return <span className="text-text-3">Connecting</span>;
  }
  if (state.kind === "offline") {
    return (
      <>
        <Dot className="bg-critical" />
        <span className="text-text-2">Backend offline</span>
      </>
    );
  }
  const { setup } = state;
  return (
    <>
      <Dot className={setup.connected ? "bg-ok" : "bg-idle"} />
      <span className="text-text-2">{setup.connected ? "Receiving" : "Waiting for game"}</span>
      <span className="tnum text-text-3">
        UDP {setup.udp_host}:{setup.udp_port}
      </span>
      {setup.packet_format !== null && <span className="tnum text-text-3">Format {setup.packet_format}</span>}
      {setup.packet_warning !== null && <span className="text-warn">{setup.packet_warning}</span>}
    </>
  );
}

function Dot({ className }: { className: string }) {
  return <span className={`size-2 rounded-full ${className}`} aria-hidden />;
}
