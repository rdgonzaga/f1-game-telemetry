import { describe, expect, it } from "vitest";

import type { LapSummary, LiveMessage, LiveSnapshot, SessionDocument } from "@/api/types";
import { createLiveStore, reduce, type LiveState } from "@/live/store";

function snapshot(over: Partial<LiveSnapshot> = {}): LiveSnapshot {
  return {
    type: "snapshot",
    connected: false,
    packet_format: null,
    player_index: null,
    packets_per_second: 0,
    session: null,
    lap: null,
    telemetry: null,
    status: null,
    damage: null,
    telemetry2: null,
    delta: null,
    ...over,
  };
}

function apply(state: LiveState, message: LiveMessage, now = 1000): LiveState {
  return { ...state, ...reduce(state, message, now) };
}

const session = { id: "20260921-002514_spa_race", laps: [] } as unknown as SessionDocument;
const lap: LapSummary = { number: 3, lap_time_ms: 126601, invalid: false, partial: false, samples: 7159 };

describe("waiting versus paused", () => {
  it("is waiting when nothing has ever arrived", () => {
    // Every packet slot null: the game has never spoken, so the user still needs the setup prompt.
    const state = apply(createLiveStore().getState(), snapshot(), 1000);
    expect(state.status).toBe("waiting");
  });

  it("is paused, not waiting, once the game has been seen", () => {
    // A paused game leaves the backend holding the last packet of each kind, so the slots stay full.
    let state = apply(createLiveStore().getState(), snapshot({ connected: true, telemetry: {} as never }), 1000);
    expect(state.status).toBe("live");

    state = apply(state, snapshot({ connected: false, telemetry: {} as never }), 3000);
    expect(state.status).toBe("paused");
  });

  it("goes back to waiting when a fresh backend has no packets at all", () => {
    // Found by restarting the backend under a running dashboard. The socket reconnects on its own and
    // the new backend has never received anything, so the setup prompt is what the user needs. Judging
    // this from "have we ever seen a packet" instead of from the snapshot showed Paused and hid it.
    let state = apply(createLiveStore().getState(), snapshot({ connected: true, telemetry: {} as never }), 1000);
    expect(state.lastPacketAt).toBe(1000);

    state = apply(state, snapshot(), 9000);
    expect(state.status).toBe("waiting");
    expect(state.lastPacketAt).toBeNull();
    expect(state.staleSeconds).toBe(0);
  });

  it("is paused even on the first snapshot, if it carries packets", () => {
    // Connecting to a backend whose game is already sitting in a menu: packets are there, the
    // connection flag is not. Showing "turn UDP on" would be wrong; it is plainly on.
    const state = apply(createLiveStore().getState(), snapshot({ telemetry: {} as never }), 1000);
    expect(state.status).toBe("paused");
  });

  it("keeps the last snapshot when the game goes quiet", () => {
    // Zeroing or dropping it loses the one thing worth having after the game drops out mid-lap.
    const telemetry = {} as never;
    let state = apply(createLiveStore().getState(), snapshot({ connected: true, packets_per_second: 60, telemetry }), 1000);
    state = apply(state, snapshot({ connected: false, packets_per_second: 0, telemetry }), 3000);
    expect(state.snapshot).not.toBeNull();
    expect(state.lastPacketAt).toBe(1000);
  });
});

describe("session events", () => {
  it("drops the last lap when a new session starts", () => {
    let state = apply(createLiveStore().getState(), { type: "lap_completed", lap, session }, 0);
    expect(state.lastLap).toBe(lap);

    state = apply(state, { type: "session_started", session }, 0);
    expect(state.lastLap).toBeNull();
  });

  it("drops a lap a flashback took back", () => {
    let state = apply(createLiveStore().getState(), { type: "lap_completed", lap, session }, 0);
    state = apply(state, { type: "lap_reopened", lap_number: 3, session }, 0);
    expect(state.lastLap).toBeNull();
  });

  it("keeps the last lap when a different lap is reopened", () => {
    let state = apply(createLiveStore().getState(), { type: "lap_completed", lap, session }, 0);
    state = apply(state, { type: "lap_reopened", lap_number: 2, session }, 0);
    expect(state.lastLap).toBe(lap);
  });
});

describe("transient subscriptions", () => {
  it("does not wake a status subscriber on a snapshot", () => {
    // The whole performance argument: snapshots land 30 times a second and must not reach React.
    const store = createLiveStore();
    let statusChanges = 0;
    store.subscribe((s) => s.status, () => statusChanges++);

    store.setState(reduce(store.getState(), snapshot({ connected: true }), 1000));
    expect(statusChanges).toBe(1); // offline -> live

    for (let i = 0; i < 30; i++) {
      store.setState(reduce(store.getState(), snapshot({ connected: true, packets_per_second: i }), 1000 + i));
    }
    expect(statusChanges).toBe(1); // still live; nothing re-rendered
  });
});
