/**
 * Saved laps as the sessions list and lap table show them.
 *
 * "Counted" matches the backend's best lap (`store.best_lap_number`): valid, driven end to end, with a time.
 * A partial lap's sector 1 starts wherever the recording joined, and an invalid lap cut the track, so neither
 * may set a best.
 */
import type { LapSummary } from "@/api/types";

export type Sectors = [number | null, number | null, number | null];

export function counted(lap: LapSummary): boolean {
  return !lap.invalid && !lap.partial && lap.lap_time_ms > 0;
}

/** The fastest time in each sector over counted laps; a sector of 0 was never seen, so it doesn't count. */
export function bestSectors(laps: readonly LapSummary[]): Sectors {
  const best: Sectors = [null, null, null];
  for (const lap of laps) {
    if (!counted(lap) || !lap.sector_times_ms) continue;
    lap.sector_times_ms.forEach((ms, i) => {
      const current = best[i] ?? null;
      if (ms > 0 && (current === null || ms < current)) best[i] = ms;
    });
  }
  return best;
}

/** `ss.sss`, or `m:ss.sss` for a sector over a minute (a pit lane), or an em dash when there is no time. */
export function formatSectorTime(ms: number | null | undefined): string {
  if (!ms || ms <= 0) return "—";
  const minutes = Math.floor(ms / 60000);
  const seconds = ((ms % 60000) / 1000).toFixed(3);
  return minutes ? `${minutes}:${seconds.padStart(6, "0")}` : seconds;
}

export type SessionKind = "Race" | "Qualifying" | "Practice" | "Time Trial";
export const SESSION_KINDS: readonly SessionKind[] = ["Race", "Qualifying", "Practice", "Time Trial"];

/** Group the game's session types (`names.SESSION_TYPES`) the way the filter shows them; sprint shootouts qualify. */
export function sessionKind(sessionType: number): SessionKind | null {
  if (sessionType >= 1 && sessionType <= 4) return "Practice";
  if (sessionType >= 5 && sessionType <= 14) return "Qualifying";
  if (sessionType >= 15 && sessionType <= 17) return "Race";
  if (sessionType === 18) return "Time Trial";
  return null;
}

const WHEN = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

/** A saved `started_at` is local time without a zone, which `Date` also reads as local. */
export function formatStarted(startedAt: string): string {
  const date = new Date(startedAt);
  return Number.isNaN(date.getTime()) ? startedAt : WHEN.format(date);
}
