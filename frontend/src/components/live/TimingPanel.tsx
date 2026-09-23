import { useRef, useState, type ReactNode } from "react";

import { LivePanel } from "@/components/live/LivePanel";
import { RACE_SESSION_TYPES, deltaTone, formatDelta, formatLapTime, fuelLaps } from "@/lib/timing";
import { numberToken } from "@/lib/tokens";
import { useLiveFrame, useLiveSession } from "@/live/useLive";

/**
 * Lap time, the live delta to the session's best lap, last and best laps, fuel, and where the session is.
 *
 * Like `CarPanel`, nothing here renders per frame. Values are written through refs, and colour is a `data-tone`
 * attribute that the classes below select on, so a frame never touches a class list. The track, session type and
 * best lap come from the session document, which changes only on session and lap events.
 *
 * The delta is used as the backend sends it: positive is slower, already from the driver's side. The B-A sign
 * that needs negating belongs to `compare_laps`, not to this.
 */
export function TimingPanel() {
  const session = useLiveSession();
  const lapLabel = useRef<HTMLSpanElement>(null);
  const current = useRef<HTMLSpanElement>(null);
  const invalid = useRef<HTMLSpanElement>(null);
  const delta = useRef<HTMLSpanElement>(null);
  const deltaRef = useRef<HTMLSpanElement>(null);
  const last = useRef<HTMLSpanElement>(null);
  const fuelKg = useRef<HTMLSpanElement>(null);
  const fuelRange = useRef<HTMLSpanElement>(null);
  // Read once: getComputedStyle forces a style recalculation, which has no place in a frame callback.
  const [band] = useState(() => numberToken("--f1-delta-neutral"));

  const bestMs = session?.laps.find((lap) => lap.number === session.best_lap)?.lap_time_ms;

  useLiveFrame(({ lap, session: packet, status, delta: gap }) => {
    const race = packet ? RACE_SESSION_TYPES.has(packet.session_type) : false;
    text(lapLabel, lap ? (race ? `Lap ${lap.current_lap_num} / ${packet?.total_laps}` : `Lap ${lap.current_lap_num}`) : "Lap");

    text(current, formatLapTime(lap?.current_lap_time_ms));
    attr(current, "data-invalid", String(lap?.current_lap_invalid ?? false));
    if (invalid.current) invalid.current.hidden = !lap?.current_lap_invalid;

    text(delta, gap ? formatDelta(gap.seconds) : "—");
    attr(delta, "data-tone", gap ? deltaTone(gap.seconds, band) : "neutral");
    text(deltaRef, gap ? `vs lap ${gap.best_lap}` : "no best lap yet");

    const lastMs = lap?.last_lap_time_ms;
    text(last, formatLapTime(lastMs));
    attr(last, "data-tone", !lastMs || bestMs === undefined ? "" : lastMs === bestMs ? "best" : lastMs > bestMs ? "slow" : "");

    text(fuelKg, status ? `${status.fuel_in_tank.toFixed(2)} kg` : "—");
    const range = status && packet ? fuelLaps(status.fuel_remaining_laps, packet.session_type) : null;
    text(fuelRange, range?.text ?? "—");
    attr(fuelRange, "data-tone", range?.short ? "loss" : "");
  });

  return (
    <LivePanel
      title="Timing"
      aside={
        session && (
          <span className="truncate text-xs font-semibold tracking-[var(--f1-tracking-label)] text-text-2 uppercase">
            {session.track.name} · {session.session_type.name}
          </span>
        )
      }
    >
      <div className="flex h-full flex-col justify-between gap-[var(--f1-space-4)]">
        <div className="grid grid-cols-2 gap-[var(--f1-gap)]">
          <Stat label={<span ref={lapLabel} className="tnum" />}>
            <span className={`${HERO} data-[invalid=true]:text-text-3`} ref={current} />
            <span
              ref={invalid}
              hidden
              className="mt-[var(--f1-space-1)] text-xs font-semibold tracking-[var(--f1-tracking-label)] text-loss uppercase"
            >
              Invalid
            </span>
          </Stat>
          <Stat label="Delta">
            <span className={`${HERO} ${TONES}`} ref={delta} />
            <span ref={deltaRef} className="mt-[var(--f1-space-1)] text-sm text-text-3" />
          </Stat>
        </div>

        <div className="grid grid-cols-2 gap-[var(--f1-gap)]">
          <Stat label="Last lap">
            <span className={`${VALUE} ${TONES}`} ref={last} />
          </Stat>
          <Stat label="Best lap">
            <span className={`${VALUE} text-timing-best`}>{formatLapTime(bestMs)}</span>
          </Stat>
        </div>

        <div className="grid grid-cols-2 gap-[var(--f1-gap)]">
          <Stat label="Fuel">
            <span className={VALUE} ref={fuelKg} />
          </Stat>
          <Stat label="Fuel laps">
            <span className={`${VALUE} ${TONES}`} ref={fuelRange} />
          </Stat>
        </div>
      </div>
    </LivePanel>
  );
}

const HERO = "tnum font-mono text-xl leading-none font-semibold text-text-1";
const VALUE = "tnum font-mono text-lg leading-none text-text-1";
/** Delta and timing share hues on purpose (docs/design.md): green is good in both, yellow is caution in both. */
const TONES = [
  "data-[tone=gain]:text-gain",
  "data-[tone=loss]:text-loss",
  "data-[tone=neutral]:text-neutral",
  "data-[tone=best]:text-timing-best",
  "data-[tone=slow]:text-timing-slow",
].join(" ");

function Stat({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col">
      <span className="mb-[var(--f1-space-2)] text-xs font-semibold tracking-[var(--f1-tracking-label)] text-text-3 uppercase">
        {label}
      </span>
      {children}
    </div>
  );
}

function text(ref: React.RefObject<Element | null>, value: string) {
  if (ref.current && ref.current.textContent !== value) ref.current.textContent = value;
}

function attr(ref: React.RefObject<Element | null>, name: string, value: string) {
  if (ref.current && ref.current.getAttribute(name) !== value) ref.current.setAttribute(name, value);
}
