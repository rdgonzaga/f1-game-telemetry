import { Link, useNavigate } from "react-router-dom";

import type { LapSummary } from "@/api/types";
import { bestSectors, formatSectorTime } from "@/lib/laps";
import { formatLapTime } from "@/lib/timing";
import { cn } from "@/lib/utils";

/**
 * Every lap of a saved session: time, sectors and whether it counted.
 *
 * docs/design.md: purple is session best. The best lap's time and the fastest time in each sector column are
 * purple, taken only from laps that count, so a quicker invalid lap never wears it.
 */
export function LapTable({
  sessionId,
  laps,
  bestLap,
}: {
  sessionId: string;
  laps: readonly LapSummary[];
  bestLap: number | null | undefined;
}) {
  const navigate = useNavigate();
  const best = bestSectors(laps);
  const href = (number: number) => `/sessions/${encodeURIComponent(sessionId)}/laps/${number}`;

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[32rem] border-collapse text-sm">
        <thead>
          <tr className="border-b border-border-soft text-left">
            {["Lap", "Time", "S1", "S2", "S3", ""].map((label, i) => (
              <th
                key={i}
                scope="col"
                className="px-3 py-2 text-xs font-semibold tracking-[var(--f1-tracking-label)] text-text-3 uppercase"
              >
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {laps.map((lap) => {
            const sectors = lap.sector_times_ms ?? [0, 0, 0];
            return (
              <tr
                key={lap.number}
                aria-label={`Lap ${lap.number}`}
                onClick={() => void navigate(href(lap.number))}
                className="cursor-pointer border-b border-border-soft transition-colors last:border-0 hover:bg-surface-2"
              >
                <td className="px-3 py-2">
                  <Link to={href(lap.number)} className="tnum font-mono text-text-1 hover:underline">
                    {lap.number}
                  </Link>
                </td>
                <TimeCell best={lap.number === bestLap} struck={lap.invalid} strong>
                  {formatLapTime(lap.lap_time_ms)}
                </TimeCell>
                {sectors.map((ms, i) => (
                  <TimeCell key={i} best={!lap.invalid && !lap.partial && ms > 0 && ms === best[i]}>
                    {formatSectorTime(ms)}
                  </TimeCell>
                ))}
                <td className="px-3 py-2">
                  {lap.invalid && <Tag>Invalid</Tag>}
                  {lap.partial && <Tag muted>Partial</Tag>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function TimeCell({
  best,
  struck = false,
  strong = false,
  children,
}: {
  best: boolean;
  struck?: boolean;
  strong?: boolean;
  children: string;
}) {
  return (
    <td
      data-best={best}
      className={cn(
        "tnum px-3 py-2 font-mono",
        strong ? "text-text-1" : "text-text-2",
        best && "font-semibold text-timing-best",
        struck && "text-text-3 line-through",
      )}
    >
      {children}
    </td>
  );
}

function Tag({ muted = false, children }: { muted?: boolean; children: string }) {
  return (
    <span
      className={cn(
        "mr-1 inline-block rounded-full border px-2 py-0.5 text-xs font-semibold tracking-[var(--f1-tracking-label)] uppercase",
        muted ? "border-border-soft text-text-3" : "border-timing-slow/50 text-timing-slow",
      )}
    >
      {children}
    </span>
  );
}
