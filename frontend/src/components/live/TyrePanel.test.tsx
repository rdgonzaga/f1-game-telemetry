import { act, render, screen } from "@testing-library/react";
import { Profiler } from "react";
import { afterEach, expect, it, vi } from "vitest";

import type { LiveSnapshot } from "@/api/types";
import { TyrePanel } from "@/components/live/TyrePanel";
import { liveStore, reduce } from "@/live/store";

afterEach(() => {
  vi.unstubAllGlobals();
  liveStore.setState({ status: "offline", snapshot: null, lastPacketAt: null, staleSeconds: 0 });
});

it("fills all four corners at 30 Hz without rendering React", () => {
  const frames: FrameRequestCallback[] = [];
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => frames.push(cb));
  vi.stubGlobal("cancelAnimationFrame", () => {});

  let commits = 0;
  render(
    <Profiler id="tyres" onRender={() => commits++}>
      <TyrePanel />
    </Profiler>,
  );
  const before = commits;

  const corner = (fl: number, fr: number, rl: number, rr: number) => ({ fl, fr, rl, rr });
  act(() => {
    for (let i = 0; i < 30; i++) {
      const carcass = corner(90 + i, 91, 92, 93);
      const telemetry: Record<string, number> = {};
      const damage: Record<string, number> = {};
      for (const c of ["fl", "fr", "rl", "rr"] as const) {
        telemetry[`tyre_inner_temperature_${c}`] = carcass[c];
        telemetry[`tyre_surface_temperature_${c}`] = 100;
        telemetry[`tyre_pressure_${c}`] = 22.5;
        telemetry[`brake_temperature_${c}`] = 600;
        damage[`tyre_wear_${c}`] = 12.4;
      }
      const snapshot = {
        type: "snapshot",
        connected: true,
        telemetry,
        damage,
        status: { visual_tyre_compound: 17, tyres_age_laps: 5 },
      } as unknown as LiveSnapshot;
      liveStore.setState(reduce(liveStore.getState(), snapshot, 1000 + i));
    }
  });
  act(() => frames.splice(0).forEach((cb) => cb(0)));

  for (const temp of ["119", "91", "92", "93"]) expect(screen.getByText(temp)).toBeTruthy();
  expect(screen.getAllByText("12%")).toHaveLength(4);
  expect(screen.getByText("Medium")).toBeTruthy();
  // One commit for the status going offline -> live (the panel undims), none for the 30 snapshots.
  expect(commits - before).toBe(1);
});
