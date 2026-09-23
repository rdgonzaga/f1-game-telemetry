import { act, render, screen } from "@testing-library/react";
import { Profiler } from "react";
import { afterEach, expect, it, vi } from "vitest";

import type { LiveSnapshot } from "@/api/types";
import { CarPanel } from "@/components/live/CarPanel";
import { liveStore, reduce } from "@/live/store";

afterEach(() => {
  vi.unstubAllGlobals();
  liveStore.setState({ status: "offline", snapshot: null, lastPacketAt: null, staleSeconds: 0 });
});

it("paints 30 Hz telemetry without rendering React", () => {
  const frames: FrameRequestCallback[] = [];
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => frames.push(cb));
  vi.stubGlobal("cancelAnimationFrame", () => {});

  let commits = 0;
  render(
    <Profiler id="car" onRender={() => commits++}>
      <CarPanel />
    </Profiler>,
  );
  const before = commits;

  act(() => {
    for (let i = 0; i < 30; i++) {
      const snapshot = {
        type: "snapshot",
        connected: true,
        telemetry: { speed: 300 + i, gear: 8, engine_rpm: 12000, throttle: 1, brake: 0, steer: -0.2 },
        status: { max_rpm: 13000 },
      } as LiveSnapshot;
      liveStore.setState(reduce(liveStore.getState(), snapshot, 1000 + i));
    }
  });
  act(() => frames.splice(0).forEach((cb) => cb(0)));

  expect(screen.getByText("329")).toBeTruthy();
  expect(screen.getByText("L 0.20")).toBeTruthy();
  // One commit for the status going offline -> live (the panel undims), none for the 30 snapshots.
  expect(commits - before).toBe(1);
});
