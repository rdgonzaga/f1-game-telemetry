import { expect, it } from "vitest";

import { deltaTone, formatDelta, formatLapTime, fuelLaps } from "@/lib/timing";

it("reads fuel_remaining_laps as a margin in a race and as laps on board anywhere else", () => {
  // Values from career-weekend-2026.f1raw: 20 kg in a 13-lap race vs 20 kg in practice.
  expect(fuelLaps(1.52, 15)).toEqual({ text: "+1.52 laps to finish", short: false });
  expect(fuelLaps(-0.4, 16)).toEqual({ text: "-0.40 laps to finish", short: true });
  expect(fuelLaps(13.27, 1)).toEqual({ text: "13.3 laps", short: false });
  // Time Trial freezes fuel.
  expect(fuelLaps(3, 18).text).toBe("—");
});

it("keeps the delta neutral inside the noise band and signs it from the driver's side", () => {
  expect(deltaTone(0.05, 0.05)).toBe("neutral");
  expect(deltaTone(-0.05, 0.05)).toBe("neutral");
  expect(deltaTone(0.051, 0.05)).toBe("loss");
  expect(deltaTone(-0.051, 0.05)).toBe("gain");
  expect(formatDelta(0.1234)).toBe("+0.123");
  expect(formatDelta(-0.1234)).toBe("-0.123");
  expect(formatDelta(-0.0004)).toBe("0.000");
});

it("never rounds a lap time up to 60 seconds", () => {
  expect(formatLapTime(119999.6)).toBe("2:00.000");
  expect(formatLapTime(83456)).toBe("1:23.456");
  expect(formatLapTime(0)).toBe("—");
});
