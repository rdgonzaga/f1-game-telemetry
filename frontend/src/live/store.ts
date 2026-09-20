/**
 * The live store: everything `/ws/live` tells us, held outside React.
 *
 * Snapshots arrive at 30 Hz. None of them may cause a React render, so the rule is:
 *
 * - **Coarse state** (`status`, `session`, `lastLap`) changes rarely and is read with `useStore`.
 *   Rendering on those is the point.
 * - **The snapshot itself** changes 30 times a second and is read only through a transient
 *   subscription, which writes into a DOM node inside `requestAnimationFrame`. A component that
 *   calls `useStore(s => s.snapshot)` would re-render the tree 30 times a second, which is exactly
 *   what AGENTS.md forbids. `subscribeWithSelector` keeps every other subscriber from waking up.
 *
 * The store knows nothing about WebSockets; `socket.ts` drives it. That split is what makes the
 * state machine testable without a network.
 */
import { createStore } from "zustand/vanilla";
import { subscribeWithSelector } from "zustand/middleware";

import type { LapSummary, LiveMessage, LiveSnapshot, SessionDocument } from "@/api/types";

/**
 * The four states the dashboard can be in. `docs/design.md` draws each one.
 *
 * `paused` and `waiting` are both "no packets", and they are not the same thing. Waiting means the
 * game has never sent anything and the user probably has to turn UDP on, so the screen explains how.
 * Paused means it was sending and stopped, so the last values stay on screen, dimmed, under a badge.
 * Showing the setup prompt to someone whose game just went to a menu mid-lap would be nonsense.
 */
export type LiveStatus = "offline" | "waiting" | "live" | "paused";

export interface LiveState {
  status: LiveStatus;
  /** 30 Hz. Never read this through `useStore` in a component; see the note above. */
  snapshot: LiveSnapshot | null;
  /** The open session, as the saved `session.json` shape. Null between sessions. */
  session: SessionDocument | null;
  /** The lap that completed most recently, for a panel that wants to flash it. */
  lastLap: LapSummary | null;
  /** `performance.now()` when a snapshot last reported the game as connected. */
  lastPacketAt: number | null;
  /** Whole seconds since then, ticked about once a second, for the "no packets for Ns" badge. */
  staleSeconds: number;
  /** How many times the socket has reconnected, so the UI can say so if it wants to. */
  reconnects: number;
}

const INITIAL: LiveState = {
  status: "offline",
  snapshot: null,
  session: null,
  lastLap: null,
  lastPacketAt: null,
  staleSeconds: 0,
  reconnects: 0,
};

export type LiveStore = ReturnType<typeof createLiveStore>;

export function createLiveStore(initial: Partial<LiveState> = {}) {
  return createStore<LiveState>()(subscribeWithSelector(() => ({ ...INITIAL, ...initial })));
}

/** The store the app uses. Tests build their own with `createLiveStore`. */
export const liveStore = createLiveStore();

/**
 * Fold one feed message into the state.
 *
 * Pure, and exported so the state machine can be tested by handing it messages. `now` is passed in
 * rather than read here for the same reason.
 */
export function reduce(state: LiveState, message: LiveMessage, now: number): Partial<LiveState> {
  switch (message.type) {
    case "snapshot": {
      // `connected` means a datagram arrived within the last second, which is the backend's own
      // judgement and better than anything measurable from here.
      if (message.connected) {
        return { snapshot: message, status: "live", lastPacketAt: now, staleSeconds: 0 };
      }
      // Not connected. Whether that is "paused" or "waiting" is answered by the snapshot alone: the
      // backend keeps the last packet of each kind in `LiveState` and never clears it, so slots that
      // still hold something mean the game spoke and stopped, and slots that are all null mean it has
      // never spoken at all.
      //
      // Deliberately NOT "have we ever seen a packet": that is remembered across reconnects, so
      // restarting the backend under a running dashboard showed "Paused" over a fresh backend that
      // had never received anything, hiding the setup prompt the user actually needed.
      if (hasAnyPacket(message)) return { snapshot: message, status: "paused" };
      return { snapshot: message, status: "waiting", lastPacketAt: null, staleSeconds: 0 };
    }
    case "hello":
      return { session: message.session };
    case "session_started":
      // A new session invalidates the last lap; it belonged to the previous one.
      return { session: message.session, lastLap: null };
    case "lap_completed":
      return { session: message.session, lastLap: message.lap };
    case "lap_reopened":
      // A flashback took the lap back. Drop it rather than showing a lap that no longer exists.
      return {
        session: message.session,
        lastLap: state.lastLap?.number === message.lap_number ? null : state.lastLap,
      };
    case "session_ended":
      return { session: message.session };
  }
}

/** True once any packet kind has arrived, which is what separates "paused" from "waiting". */
function hasAnyPacket(snapshot: LiveSnapshot): boolean {
  return (
    snapshot.session !== null ||
    snapshot.lap !== null ||
    snapshot.telemetry !== null ||
    snapshot.status !== null ||
    snapshot.damage !== null ||
    snapshot.telemetry2 !== null
  );
}
