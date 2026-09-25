import { act, render, screen } from "@testing-library/react";
import { useRef } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { LiveSnapshot } from "@/api/types";
import { liveStore, reduce } from "@/live/store";
import { useLiveFrame, useLiveStatus } from "@/live/useLive";

function snapshot(speed: number, connected = true): LiveSnapshot {
  return {
    type: "snapshot",
    connected,
    packet_format: 2026,
    player_index: 21,
    packets_per_second: 60,
    session: null,
    lap: null,
    telemetry: { speed } as never,
    status: null,
    damage: null,
    telemetry2: null,
    delta: null,
  };
}

/** rAF under our control, so a frame happens exactly when the test says so. */
function captureFrames() {
  const pending: FrameRequestCallback[] = [];
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => pending.push(cb));
  vi.stubGlobal("cancelAnimationFrame", () => {});
  return () =>
    act(() => {
      const callbacks = pending.splice(0);
      for (const cb of callbacks) cb(0);
    });
}

let renders = 0;

function SpeedPanel() {
  renders++;
  const status = useLiveStatus();
  const value = useRef<HTMLSpanElement>(null);

  useLiveFrame((live) => {
    // How every live value is written: straight to a leaf text node, never through React.
    if (value.current) value.current.textContent = String(live.telemetry?.speed ?? "—");
  });

  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="speed" ref={value} />
    </div>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  liveStore.setState({ status: "offline", snapshot: null, lastPacketAt: null, staleSeconds: 0 });
  renders = 0;
});

describe("useLiveFrame", () => {
  it("writes telemetry without re-rendering the component", () => {
    const flush = captureFrames();
    render(<SpeedPanel />);
    const before = renders;

    act(() => {
      for (let i = 0; i < 30; i++) {
        liveStore.setState(reduce(liveStore.getState(), snapshot(300 + i), 1000 + i));
      }
    });
    flush();

    expect(screen.getByTestId("speed").textContent).toBe("329");
    // One render for the status going offline -> live, and not one of the 30 snapshots.
    expect(renders - before).toBe(1);
  });

  it("collapses a burst of snapshots into a single paint", () => {
    const flush = captureFrames();
    const painted: number[] = [];

    function Probe() {
      useLiveFrame((live) => painted.push(live.telemetry?.speed ?? 0));
      return null;
    }
    render(<Probe />);
    flush(); // the initial paint, which has nothing to show yet

    act(() => {
      for (const speed of [100, 200, 300]) {
        liveStore.setState(reduce(liveStore.getState(), snapshot(speed), 1000));
      }
    });
    flush();

    // Three snapshots inside one frame is one paint, carrying the newest value.
    expect(painted).toEqual([300]);
  });

  it("paints what is already there when a panel mounts mid-session", () => {
    liveStore.setState(reduce(liveStore.getState(), snapshot(214), 1000));
    const flush = captureFrames();

    render(<SpeedPanel />);
    flush();

    expect(screen.getByTestId("speed").textContent).toBe("214");
  });
});
