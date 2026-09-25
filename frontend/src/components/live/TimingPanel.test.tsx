import { act, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import type { LiveSnapshot, SessionDocument } from "@/api/types";
import { TimingPanel } from "@/components/live/TimingPanel";
import { liveStore, reduce } from "@/live/store";

afterEach(() => {
  vi.unstubAllGlobals();
  liveStore.setState({ status: "offline", snapshot: null, session: null, lastPacketAt: null, staleSeconds: 0 });
});

it("colours the last lap against the best lap from a session that arrives after mount", () => {
  const frames: FrameRequestCallback[] = [];
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => frames.push(cb));
  vi.stubGlobal("cancelAnimationFrame", () => {});

  render(<TimingPanel />);

  const session = {
    track: { id: 13, name: "Suzuka", length: 5807 },
    session_type: { id: 15, name: "Race" },
    best_lap: 2,
    laps: [
      { number: 1, lap_time_ms: 95000 },
      { number: 2, lap_time_ms: 91234 },
    ],
  } as unknown as SessionDocument;
  const snapshot = {
    type: "snapshot",
    connected: true,
    session: { session_type: 15, total_laps: 13 },
    lap: { current_lap_num: 4, current_lap_time_ms: 30500, current_lap_invalid: false, last_lap_time_ms: 92000 },
  } as unknown as LiveSnapshot;
  act(() => {
    liveStore.setState({ session });
    liveStore.setState(reduce(liveStore.getState(), snapshot, 1000));
  });
  act(() => frames.splice(0).forEach((cb) => cb(0)));

  expect(screen.getByText("Lap 4 / 13")).toBeTruthy();
  expect(screen.getByText("1:31.234")).toBeTruthy();
  expect(screen.getByText("1:32.000").getAttribute("data-tone")).toBe("slow");
});
