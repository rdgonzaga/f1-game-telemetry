import { describe, expect, it } from "vitest";

import type { LiveMessage, LiveSnapshot } from "@/api/types";
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

describe("waiting versus paused", () => {
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

  it("keeps the last packet time when the game goes quiet", () => {
    // Resetting it would restart the "no packets for Ns" count every time the game drops out.
    const telemetry = {} as never;
    let state = apply(createLiveStore().getState(), snapshot({ connected: true, packets_per_second: 60, telemetry }), 1000);
    state = apply(state, snapshot({ connected: false, packets_per_second: 0, telemetry }), 3000);
    expect(state.lastPacketAt).toBe(1000);
  });
});
