/**
 * Which two laps the compare view shows. The pair lives in the URL as `?a=<session>:<lap>&b=<session>:<lap>`, so
 * a comparison can be linked and the back button undoes a pick. Session ids never contain a colon.
 */
import type { SessionSummary } from "@/api/types";

export interface LapRef {
  session: string;
  lap: number;
}

export function parseLapRef(value: string | null): LapRef | null {
  const match = value?.match(/^(.+):(\d+)$/);
  return match ? { session: match[1] ?? "", lap: Number(match[2]) } : null;
}

export function formatLapRef(ref: LapRef): string {
  return `${ref.session}:${ref.lap}`;
}

/** The session's best lap, or its fastest timed lap when none counts, or its first. */
export function anchorLap(session: SessionSummary): number | null {
  if (session.best_lap != null) return session.best_lap;
  const timed = session.laps.filter((lap) => lap.lap_time_ms > 0);
  const fastest = timed.sort((x, y) => x.lap_time_ms - y.lap_time_ms)[0] ?? session.laps[0];
  return fastest?.number ?? null;
}

/** What the anchor lap is compared with by default: the lap before it, else the one after, else any other. */
export function previousLap(session: SessionSummary, anchor: number): number | null {
  const numbers = session.laps.map((lap) => lap.number).filter((n) => n !== anchor);
  if (numbers.includes(anchor - 1)) return anchor - 1;
  if (numbers.includes(anchor + 1)) return anchor + 1;
  return numbers[numbers.length - 1] ?? null;
}

/** Best lap against the lap before it, in `preferred` if it has two laps, else the newest session that does. */
export function defaultPair(sessions: readonly SessionSummary[], preferred?: string | null): [LapRef, LapRef] | null {
  const candidates = [...sessions.filter((s) => s.id === preferred), ...sessions];
  for (const session of candidates) {
    const anchor = anchorLap(session);
    const other = anchor == null ? null : previousLap(session, anchor);
    if (anchor != null && other != null) {
      return [
        { session: session.id, lap: anchor },
        { session: session.id, lap: other },
      ];
    }
  }
  return null;
}
