import type { LapDocument } from "@/api/types";

type Columns = LapDocument["columns"];
export type Channel = Exclude<keyof Columns, "lap_distance">;

/** A lap's columns on a distance axis uPlot can search: `distance` strictly rising, every channel cut to match. */
export interface LapTrace {
  distance: number[];
  channels: Partial<Record<Channel, number[]>>;
}

/**
 * Keep only the samples whose distance moves forward, as `compare.py` does.
 *
 * Saved laps step back by 0.1 m at crawling speed (rounding jitter) and repeat after a flashback. uPlot finds the
 * cursor's sample by binary search on x, so one backward step puts the readout on the wrong metre.
 */
export function lapTrace(columns: Columns, channels: readonly Channel[]): LapTrace {
  const keep: number[] = [];
  const distance: number[] = [];
  let furthest = -Infinity;
  columns.lap_distance.forEach((metres, i) => {
    if (metres > furthest) {
      keep.push(i);
      distance.push(metres);
      furthest = metres;
    }
  });
  const picked: LapTrace["channels"] = {};
  for (const channel of channels) {
    // A version 1 lap file has no tyre, fuel, ERS or position columns.
    const values = columns[channel];
    if (values) picked[channel] = keep.map((i) => values[i] ?? Number.NaN);
  }
  return { distance, channels: picked };
}

/** Axis and readout text for a lap distance: metres under a kilometre, then kilometres. */
export function formatDistance(metres: number): string {
  return metres < 1000 ? `${Math.round(metres)} m` : `${(metres / 1000).toFixed(2)} km`;
}
