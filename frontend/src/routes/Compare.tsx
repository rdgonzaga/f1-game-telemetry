import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { CompareResult, SessionSummary } from "@/api/types";
import { useApi } from "@/api/useApi";
import { Trace, type TraceSeries } from "@/components/charts/Trace";
import { Panel } from "@/components/Panel";
import { anchorLap, defaultPair, formatLapRef, parseLapRef, previousLap, type LapRef } from "@/lib/compare";
import { formatStarted } from "@/lib/laps";
import { deltaTone, formatDelta, formatLapTime } from "@/lib/timing";
import { numberToken } from "@/lib/tokens";
import { cn } from "@/lib/utils";

/** Two laps on one distance grid. Lap A is the one you are looking at; lap B is what it is measured against. */
export default function Compare() {
  const [params, setParams] = useSearchParams();
  const sessions = useApi("sessions", (signal) => api.sessions(signal));

  if (sessions.state !== "ready") {
    return (
      <Message>
        {sessions.state === "loading" ? "Loading saved sessions." : "Can't reach the app's backend to list sessions."}
      </Message>
    );
  }
  const list = sessions.data.filter((s) => s.laps.length > 0);
  const asked = [parseLapRef(params.get("a")), parseLapRef(params.get("b"))] as const;
  const pair = asked[0] && asked[1] ? ([asked[0], asked[1]] as const) : defaultPair(list, params.get("session"));
  if (!pair) {
    return <Message>Comparing needs two saved laps on the same track. Drive a couple and they land here.</Message>;
  }
  const pick = (a: LapRef, b: LapRef) => setParams({ a: formatLapRef(a), b: formatLapRef(b) });
  return <CompareView sessions={list} a={pair[0]} b={pair[1]} onPick={pick} />;
}

function CompareView({
  sessions,
  a,
  b,
  onPick,
}: {
  sessions: SessionSummary[];
  a: LapRef;
  b: LapRef;
  onPick: (a: LapRef, b: LapRef) => void;
}) {
  const result = useApi(`compare:${formatLapRef(a)}:${formatLapRef(b)}`, (signal) => api.compare(a, b, signal));
  const sessionA = sessions.find((s) => s.id === a.session);
  const sameTrack = sessions.filter((s) => s.track.id === sessionA?.track.id);

  const pickA = (ref: LapRef) => {
    const next = sessions.find((s) => s.id === ref.session);
    // The API refuses two tracks, so moving A to another track brings B along to the same session.
    if (next && next.track.id !== sessionA?.track.id) {
      const other = previousLap(next, ref.lap);
      if (other != null) return onPick(ref, { session: next.id, lap: other });
    }
    onPick(ref, b);
  };

  return (
    <div className="flex flex-col gap-[var(--f1-gap)]">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm text-text-3">Compare</p>
          <h1 className="truncate text-2xl font-extrabold tracking-[var(--f1-tracking-display)] text-text-1">
            {sessionA?.track.name ?? "Two laps"}
          </h1>
        </div>
        {result.state === "ready" && <Gap result={result.data} />}
      </header>

      <Panel title="Laps">
        <div className="flex flex-col gap-[var(--f1-space-3)]">
          <LapPicker which="A" sessions={sessions} value={a} onChange={pickA} />
          <LapPicker which="B" sessions={sameTrack} value={b} onChange={(ref) => onPick(a, ref)} />
        </div>
      </Panel>

      {result.state === "ready" ? (
        <Comparison result={result.data} />
      ) : (
        <Panel title="Speed">
          <p className="text-text-3">
            {result.state === "loading"
              ? "Lining the two laps up."
              : result.state === "missing"
                ? "One of these laps isn't saved here any more."
                : `Can't compare these laps: ${result.message}`}
          </p>
        </Panel>
      )}
    </div>
  );
}

const LAP_STROKE = { A: "--f1-lap-a", B: "--f1-lap-b" } as const;

/** Session and lap for one side. The line swatch is the same one the chart legend draws, so the two can't drift. */
function LapPicker({
  which,
  sessions,
  value,
  onChange,
}: {
  which: "A" | "B";
  sessions: SessionSummary[];
  value: LapRef;
  onChange: (ref: LapRef) => void;
}) {
  const session = sessions.find((s) => s.id === value.session);
  const select =
    "h-[var(--f1-control-h)] min-w-0 rounded-sm border border-border-control bg-surface-sunken px-2 text-sm text-text-1";
  return (
    <div className="flex flex-wrap items-center gap-3">
      <span
        aria-hidden
        className="w-8 border-t-2"
        style={{ borderTopColor: `var(${LAP_STROKE[which]})`, borderTopStyle: which === "B" ? "dashed" : "solid" }}
      />
      <span className="w-12 text-xs font-semibold tracking-[var(--f1-tracking-label)] text-text-3 uppercase">
        Lap {which}
      </span>
      <select
        aria-label={`Lap ${which} session`}
        className={cn(select, "flex-1 sm:max-w-md")}
        value={value.session}
        onChange={(event) => {
          const next = sessions.find((s) => s.id === event.target.value);
          const lap = next && anchorLap(next);
          if (next && lap != null) onChange({ session: next.id, lap });
        }}
      >
        {sessions.map((s) => (
          <option key={s.id} value={s.id}>
            {s.track.name} · {s.session_type.name} · {formatStarted(s.started_at)}
          </option>
        ))}
      </select>
      <select
        aria-label={`Lap ${which} number`}
        className={cn(select, "tnum font-mono")}
        value={value.lap}
        onChange={(event) => onChange({ session: value.session, lap: Number(event.target.value) })}
      >
        {session?.laps.map((lap) => (
          <option key={lap.number} value={lap.number}>
            Lap {lap.number} · {formatLapTime(lap.lap_time_ms)}
            {lap.number === session.best_lap ? " · best" : lap.invalid ? " · invalid" : lap.partial ? " · partial" : ""}
          </option>
        ))}
      </select>
    </div>
  );
}

/** Lap A against lap B from A's side: negative is A quicker. The API sends B minus A, so it is flipped here. */
function Gap({ result }: { result: CompareResult }) {
  const [lapA, lapB] = result.laps;
  if (!lapA || !lapB || lapA.lap_time_ms <= 0 || lapB.lap_time_ms <= 0) return null;
  const seconds = (lapA.lap_time_ms - lapB.lap_time_ms) / 1000;
  const tone = deltaTone(seconds, numberToken("--f1-delta-neutral"));
  return (
    <div className="flex flex-col items-end">
      <span
        className={cn(
          "tnum font-mono text-xl font-semibold",
          tone === "gain" ? "text-gain" : tone === "loss" ? "text-loss" : "text-neutral",
        )}
      >
        {formatDelta(seconds)}
      </span>
      <span className="text-xs tracking-[var(--f1-tracking-label)] text-text-3 uppercase">
        Lap {lapA.number} vs lap {lapB.number}
      </span>
    </div>
  );
}

/** Seconds from the lowest to the highest value, always including zero, each end rounded out to a tenth. */
function secondsRange(values: number[]): [number, number] {
  const low = Math.floor(Math.min(0, ...values) * 10) / 10;
  const high = Math.ceil(Math.max(0, ...values) * 10) / 10;
  return low === high ? [-0.1, 0.1] : [low, high];
}

/** Ticks at the ends and at zero, the one line every reader of a delta looks for. */
function secondsTicks([low, high]: [number, number]): number[] {
  return [...new Set([low, 0, high])];
}

/** Speed overlaid, then where the time went: the running delta and each minisector on its own. One cursor. */
function Comparison({ result }: { result: CompareResult }) {
  const charts = useMemo(() => {
    const [lapA, lapB] = result.laps;
    const kmh = (v: number) => `${Math.round(v)} km/h`;
    const speed: TraceSeries[] = [
      {
        label: `Lap ${lapA?.number ?? "A"}`,
        values: lapA?.columns.speed ?? [],
        stroke: "--f1-lap-a",
        width: "--f1-lap-a-width",
        fill: "--f1-chart-speed",
        format: kmh,
      },
      {
        // Unfilled: two tints stacked over each other read as a third colour that means nothing.
        label: `Lap ${lapB?.number ?? "B"}`,
        values: lapB?.columns.speed ?? [],
        stroke: "--f1-lap-b",
        width: "--f1-lap-b-width",
        dash: "--f1-lap-b-dash",
        format: kmh,
      },
    ];
    // The API sends B minus A. Flipped to A's side, so above zero is time lap A lost, as on the live delta.
    const delta = result.delta.map((d) => -d);
    const sectors = result.minisectors.map((m) => -m.delta);
    // A lap that leads all the way never crosses zero, so a symmetric scale would leave half the chart empty.
    const deltaRange = secondsRange(delta);
    const sectorRange = secondsRange(sectors);
    const signed = { stroke: "--f1-neutral", width: "--f1-lap-a-width", signed: true, format: formatDelta } as const;
    return {
      speed,
      delta: [{ ...signed, label: "Delta", values: delta, fillTo: 0 }],
      deltaRange,
      deltaTicks: secondsTicks(deltaRange),
      sectorMid: result.minisectors.map((m) => (m.start + m.end) / 2),
      sectors: [{ ...signed, label: "Minisector", values: sectors, bars: true }],
      sectorRange,
      sectorTicks: secondsTicks(sectorRange),
      gained: sectors.filter((v) => v < 0).length,
      extent: [result.distance[0] ?? 0, result.distance[result.distance.length - 1] ?? 0] as const,
    };
  }, [result]);
  const [lapA] = result.laps;
  const shared = { syncKey: "compare", ticks: formatDelta };

  return (
    <>
      <Panel title="Speed" aside={<span className="text-xs text-text-3">Drag to zoom · double-click to reset</span>}>
        <Trace distance={result.distance} series={charts.speed} height={300} syncKey="compare" />
      </Panel>
      <Panel title="Delta" aside={<span className="text-xs text-text-3">Above zero: lap {lapA?.number} behind</span>}>
        <div className="flex flex-col gap-[var(--f1-space-4)]">
          <Trace
            {...shared}
            distance={result.distance}
            series={charts.delta}
            range={charts.deltaRange}
            splits={charts.deltaTicks}
            height={160}
            distanceLabels={false}
          />
          <Trace
            {...shared}
            distance={charts.sectorMid}
            distanceRange={charts.extent}
            series={charts.sectors}
            range={charts.sectorRange}
            splits={charts.sectorTicks}
            height={140}
          />
          <p className="text-sm text-text-3">
            Lap {lapA?.number} was quicker in{" "}
            <span className="tnum font-mono text-text-1">
              {charts.gained} of {charts.sectors[0]?.values.length}
            </span>{" "}
            minisectors. Each bar is the time gained or lost inside that slice alone.
          </p>
        </div>
      </Panel>
    </>
  );
}

function Message({ children }: { children: React.ReactNode }) {
  return (
    <Panel title="Compare">
      <p className="text-text-3">{children}</p>
      <Link to="/sessions" className="mt-[var(--f1-space-2)] inline-block text-sm text-text-2 hover:underline">
        Sessions
      </Link>
    </Panel>
  );
}
