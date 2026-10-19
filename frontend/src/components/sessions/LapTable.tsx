import { Link, useNavigate } from "react-router-dom";

import type { LapSummary } from "@/api/types";
import { bestSectors, formatSectorTime } from "@/lib/laps";
import { formatLapTime } from "@/lib/timing";
import { COMPOUNDS } from "@/lib/tyres";
import { cn } from "@/lib/utils";

/**
 * Every lap of a saved session: time, sectors, the tyre and fuel it ended on, and whether it counted.
 *
 * docs/design.md: purple is session best. The best lap's time and the fastest time in each sector column are
 * purple, taken only from laps that count, so a quicker invalid lap never wears it. Laps saved before tyres and
 * fuel were summarised show a dash there.
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
      <table className="w-full min-w-[48rem] border-collapse text-sm">
        <thead>
          <tr className="border-b border-border-soft text-left">
            {["Lap", "Time", "S1", "S2", "S3", "Tyre", "Wear", "Fuel", "Used", ""].map((label, i) => (
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
                <TyreCell compound={lap.tyre_compound} />
                <NumberCell value={lap.tyre_wear} digits={0} unit="%" />
                <NumberCell value={lap.fuel_kg} digits={2} unit=" kg" />
                <NumberCell value={lap.fuel_used_kg} digits={2} unit=" kg" />
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

function TyreCell({ compound }: { compound: number | null | undefined }) {
  const tyre = compound == null ? undefined : COMPOUNDS[compound];
  return (
    <td className="px-3 py-2 whitespace-nowrap text-text-2">
      {compound == null ? (
        "—"
      ) : (
        <span className="inline-flex items-center gap-2">
          <span className="size-2 rounded-full" style={{ backgroundColor: tyre ? `var(${tyre.colour})` : undefined }} />
          {tyre?.name ?? `Compound ${compound}`}
        </span>
      )}
    </td>
  );
}

function NumberCell({ value, digits, unit }: { value: number | null | undefined; digits: number; unit: string }) {
  return (
    <td className="tnum px-3 py-2 font-mono whitespace-nowrap text-text-2">
      {value == null ? "—" : `${value.toFixed(digits)}${unit}`}
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
