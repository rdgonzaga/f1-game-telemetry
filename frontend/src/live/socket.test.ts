import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LiveSocket, type SocketLike } from "@/live/socket";
import { createLiveStore, type LiveStore } from "@/live/store";

class FakeSocket implements SocketLike {
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  closed = false;

  close(): void {
    this.closed = true;
  }

  send(message: unknown): void {
    this.onmessage?.({ data: JSON.stringify(message) });
  }
}

let sockets: FakeSocket[];
let store: LiveStore;
let clock: number;

function build() {
  return new LiveSocket({
    url: "ws://test/ws/live",
    store,
    now: () => clock,
    createSocket: () => {
      const socket = new FakeSocket();
      sockets.push(socket);
      return socket;
    },
  });
}

const connected = { type: "snapshot", connected: true, packet_format: 2026, player_index: 21, packets_per_second: 60, session: null, lap: null, telemetry: null, status: null, damage: null, telemetry2: null, delta: null };

beforeEach(() => {
  vi.useFakeTimers();
  sockets = [];
  store = createLiveStore();
  clock = 0;
});

afterEach(() => {
  vi.useRealTimers();
});

describe("reconnect", () => {
  it("backs off 1, 2, 4, 8 and holds at 10 seconds", () => {
    const live = build();
    live.start();
    const delays: number[] = [];

    for (let attempt = 0; attempt < 6; attempt++) {
      delays.push(live.nextDelayMs);
      sockets.at(-1)!.onclose!();
      vi.advanceTimersByTime(live.nextDelayMs);
    }

    expect(delays).toEqual([1000, 2000, 4000, 8000, 10_000, 10_000]);
    live.stop();
  });

  it("resets the backoff only once a message proves the socket works", () => {
    // A backend that accepts and immediately drops would otherwise spin at one attempt per second.
    const live = build();
    live.start();

    sockets.at(-1)!.onclose!();
    vi.advanceTimersByTime(1000);
    sockets.at(-1)!.onclose!();
    expect(live.nextDelayMs).toBe(4000);

    vi.advanceTimersByTime(4000);
    sockets.at(-1)!.send(connected);
    expect(live.nextDelayMs).toBe(1000);
    live.stop();
  });

  it("says the backend is offline while it retries, without wiping the last values", () => {
    const live = build();
    live.start();
    sockets.at(-1)!.send(connected);
    expect(store.getState().status).toBe("live");

    sockets.at(-1)!.onclose!();
    expect(store.getState().status).toBe("offline");
    expect(store.getState().snapshot).not.toBeNull();
    live.stop();
  });

  it("ignores a late close from a socket it already replaced", () => {
    const live = build();
    live.start();
    const first = sockets[0]!;
    first.onclose!();
    vi.advanceTimersByTime(1000);
    expect(sockets).toHaveLength(2);

    first.onclose?.();
    vi.advanceTimersByTime(60_000);
    expect(sockets).toHaveLength(2); // no second reconnect was scheduled
    live.stop();
  });
});

describe("going quiet", () => {
  it("counts the silence for the paused badge", () => {
    const live = build();
    live.start();
    sockets.at(-1)!.send(connected);

    clock = 3500;
    vi.advanceTimersByTime(3500);
    expect(store.getState().staleSeconds).toBe(3);
    live.stop();
  });

  it("falls back to paused on its own when the feed says nothing at all", () => {
    // LiveFeed.tick sends nothing while the picture is unchanged, so a lost "disconnected" snapshot
    // would otherwise leave a Live badge up forever over frozen numbers.
    const live = build();
    live.start();
    sockets.at(-1)!.send(connected);
    expect(store.getState().status).toBe("live");

    clock = 2500;
    vi.advanceTimersByTime(2500);
    expect(store.getState().status).toBe("paused");
    live.stop();
  });

  it("stays live while packets keep arriving", () => {
    const live = build();
    live.start();
    for (let i = 0; i < 10; i++) {
      clock = i * 500;
      sockets.at(-1)!.send(connected);
      vi.advanceTimersByTime(500);
    }
    expect(store.getState().status).toBe("live");
    live.stop();
  });
});
