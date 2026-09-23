/**
 * Lap times, the live delta and fuel, as the timing panel writes them.
 *
 * Pure and allocation-light: these run inside a frame callback.
 */

/** `names.SESSION_TYPES` on the backend: Race, Race 2 and Race 3. */
export const RACE_SESSION_TYPES: ReadonlySet<number> = new Set([15, 16, 17]);
/** Time Trial freezes fuel (docs/udp-spec.md), so nothing about it is worth showing. */
export const TIME_TRIAL = 18;

export type Tone = "gain" | "loss" | "neutral";

/** `m:ss.sss`, or an em dash for 0, which is what the game sends before there is a time. */
export function formatLapTime(ms: number | null | undefined): string {
  if (!ms || ms <= 0) return "—";
  const whole = Math.round(ms);
  const minutes = Math.floor(whole / 60000);
  const seconds = Math.floor((whole % 60000) / 1000);
  const millis = whole % 1000;
  return `${minutes}:${String(seconds).padStart(2, "0")}.${String(millis).padStart(3, "0")}`;
}

/** Signed seconds; positive is slower, as `snapshot.delta` sends it. */
export function formatDelta(seconds: number): string {
  const fixed = Math.abs(seconds).toFixed(3);
  if (fixed === "0.000") return fixed;
  return `${seconds < 0 ? "-" : "+"}${fixed}`;
}

/** Inside the noise band the delta reads neutral rather than flickering between green and yellow. */
export function deltaTone(seconds: number, band: number): Tone {
  if (Math.abs(seconds) <= band) return "neutral";
  return seconds < 0 ? "gain" : "loss";
}

/**
 * The game's `fuel_remaining_laps` means two different things, measured on real recordings:
 *
 * - In a race it is the MFD's margin over the finish: 20 kg on lap 1 of a 13-lap race read +1.52, not 13.
 * - Anywhere else it is laps of fuel on board: 20 kg in practice read 13.27.
 *
 * So the label depends on the session type, and a negative race margin (the car cannot reach the flag) is a loss.
 */
export function fuelLaps(remaining: number, sessionType: number): { text: string; short: boolean } {
  if (sessionType === TIME_TRIAL) return { text: "—", short: false };
  if (RACE_SESSION_TYPES.has(sessionType)) {
    const margin = `${remaining < 0 ? "-" : "+"}${Math.abs(remaining).toFixed(2)}`;
    return { text: `${margin} laps to finish`, short: remaining < 0 };
  }
  return { text: `${remaining.toFixed(1)} laps`, short: false };
}
