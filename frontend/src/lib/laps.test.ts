import { expect, it } from "vitest";

import type { LapSummary } from "@/api/types";
import { bestSectors, formatSectorTime } from "@/lib/laps";

const lap = (number: number, sectors: number[] | null, extra: Partial<LapSummary> = {}): LapSummary => ({
  number,
  lap_time_ms: sectors ? sectors.reduce((a, b) => a + b, 0) : 90000,
  invalid: false,
  partial: false,
  samples: 5000,
  sector_times_ms: sectors,
  ...extra,
});

it("takes each sector's best from valid, complete laps that recorded it", () => {
  const laps = [
    lap(1, [30000, 29000, 31000], { partial: true }), // joined mid-lap: its sector 1 isn't a real time
    lap(2, [28000, 29500, 30500]),
    lap(3, [27000, 28000, 29000], { invalid: true }), // cut a corner: fastest, and doesn't count
    lap(4, [28500, 0, 0]), // saved without sectors 2 and 3
    lap(5, null), // saved before sector times existed
  ];
  expect(bestSectors(laps)).toEqual([28000, 29500, 30500]);
});

it("has no best sector when no counted lap has one", () => {
  expect(bestSectors([lap(1, null), lap(2, [28000, 29000, 30000], { invalid: true })])).toEqual([null, null, null]);
});

it("writes a sector as seconds, with minutes only past one", () => {
  expect(formatSectorTime(28880)).toBe("28.880");
  expect(formatSectorTime(65123)).toBe("1:05.123");
  expect(formatSectorTime(0)).toBe("—");
});
