import { expect, it } from "vitest";

import type { LapDocument } from "@/api/types";
import { lapTrace } from "@/lib/trace";

it("drops samples whose distance does not move forward, keeping channels aligned", () => {
  // Rounding jitter at crawling speed (measured, Montreal lap 4) and a repeat after a flashback.
  const columns = { lap_distance: [0, 5.1, 5.0, 5.2, 5.2, 9], speed: [10, 12, 11, 13, 13, 40] };
  const trace = lapTrace(columns as unknown as LapDocument["columns"], ["speed"]);
  expect(trace.distance).toEqual([0, 5.1, 5.2, 9]);
  expect(trace.channels.speed).toEqual([10, 12, 13, 40]);
});
