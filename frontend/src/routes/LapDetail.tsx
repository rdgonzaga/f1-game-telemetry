import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "@/api/client";
import type { LapDocument } from "@/api/types";
import { useApi } from "@/api/useApi";
import { Trace, type TraceSeries } from "@/components/charts/Trace";
import { Panel } from "@/components/Panel";
import { formatSectorTime } from "@/lib/laps";
import { formatLapTime } from "@/lib/timing";
import { numberToken } from "@/lib/tokens";
import { lapTrace } from "@/lib/trace";

/** One saved lap: its times, and its traces against distance. */
export default function LapDetail() {
  const { sessionId = "", lapNumber = "" } = useParams();
  const number = Number(lapNumber);
  const session = useApi(`session:${sessionId}`, (signal) => api.session(sessionId, signal));
  const lap = useApi(`lap:${sessionId}:${number}`, (signal) => api.lap(sessionId, number, signal));
  const back = `/sessions/${encodeURIComponent(sessionId)}`;

  if (lap.state !== "ready") {
    const text = {
      loading: "Loading the lap.",
      missing: "This lap isn't saved here any more.",
      failed: "Can't reach the app's backend to load this lap.",
    }[lap.state];
    return (
      <Panel title={`Lap ${lapNumber}`}>
        <p className="text-text-3">{text}</p>
        <Link to={back} className="mt-[var(--f1-space-2)] inline-block text-sm text-text-2 hover:underline">
          Back to the session
        </Link>
      </Panel>
    );
  }

  const data = lap.data;
  return (
    <div className="flex flex-col gap-[var(--f1-gap)]">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <p className="flex gap-4 text-sm text-text-3">
            <Link to={back} className="hover:text-text-2 hover:underline">
              {session.state === "ready" ? `${session.data.track.name} · ${session.data.session_type.name}` : "Session"}
            </Link>
          </p>
          <h1 className="text-2xl font-extrabold tracking-[var(--f1-tracking-display)] text-text-1">
            Lap {data.number}
            {data.invalid && <span className="ml-3 align-middle text-sm font-semibold text-timing-slow">Invalid</span>}
            {data.partial && <span className="ml-3 align-middle text-sm font-semibold text-text-3">Partial</span>}
          </h1>
        </div>
        <dl className="flex items-end gap-[var(--f1-space-5)]">
          {(data.sector_times_ms ?? []).map((ms, i) => (
            <Figure key={i} label={`S${i + 1}`} value={formatSectorTime(ms)} />
          ))}
          <Figure label="Lap time" value={formatLapTime(data.lap_time_ms)} large />
        </dl>
      </header>

      <LapTraces lap={data} />
    </div>
  );
}

const percent = (v: number) => `${Math.round(v * 100)}%`;
const steer = (v: number) => (Math.abs(v) < 0.005 ? "0%" : `${percent(Math.abs(v))} ${v < 0 ? "L" : "R"}`);
// Full lock both ways, fixed: hairpins reach 0.9-1.0 (Montreal) where fast tracks stay near 0.5, and a scale
// fitted to each lap would make the same steering look different on two laps.
const FULL_LOCK = [-1, 0, 1];
const gear = (v: number) => (v < 0 ? "R" : v === 0 ? "N" : String(v));

/** One lap's channel as a chart series: white stroke for the lap, the channel's colour in the fill. */
function channel(
  label: string,
  values: number[] | undefined,
  fill: TraceSeries["fill"],
  format: TraceSeries["format"],
  extra: Partial<TraceSeries> = {},
): TraceSeries[] {
  return [{ label, values: values ?? [], stroke: "--f1-lap-a", width: "--f1-lap-a-width", fill, format, ...extra }];
}

/** Speed on top, the driver's inputs under it. All share one cursor and one zoom, so a reader looks straight down. */
function LapTraces({ lap }: { lap: LapDocument }) {
  const charts = useMemo(() => {
    const { distance, channels } = lapTrace(lap.columns, ["speed", "throttle", "brake", "steer", "gear"]);
    const brakeOn = numberToken("--f1-brake-on");
    return {
      distance,
      braking: (channels.brake ?? []).map((b) => b > brakeOn),
      speed: channel("Speed", channels.speed, "--f1-chart-speed", (v) => `${Math.round(v)} km/h`),
      throttle: channel("Throttle", channels.throttle, "--f1-chart-throttle", percent),
      brake: channel("Brake", channels.brake, "--f1-chart-brake", percent),
      steer: channel("Steering", channels.steer, "--f1-chart-steer", steer, { fillTo: 0 }),
      gear: channel("Gear", channels.gear, "--f1-chart-gear", gear, { stepped: true }),
    };
  }, [lap]);
  const { distance, braking } = charts;
  const shared = { distance, syncKey: "lap", height: 110 };
  const inner = { ...shared, height: 96, distanceLabels: false };

  return (
    <>
      <Panel title="Speed" aside={<span className="text-xs text-text-3">Red bands: brake on · drag to zoom</span>}>
        <Trace {...shared} series={charts.speed} shade={braking} height={280} />
      </Panel>
      <Panel title="Inputs">
        <div className="flex flex-col gap-[var(--f1-space-4)]">
          <Trace {...inner} series={charts.throttle} shade={braking} range={[0, 1]} ticks={percent} />
          <Trace {...inner} series={charts.brake} range={[0, 1]} ticks={percent} />
          <Trace {...inner} series={charts.steer} shade={braking} range={[-1, 1]} ticks={steer} splits={FULL_LOCK} />
          <Trace {...shared} series={charts.gear} shade={braking} range={[-1, 8]} ticks={gear} height={140} />
        </div>
      </Panel>
    </>
  );
}

function Figure({ label, value, large = false }: { label: string; value: string; large?: boolean }) {
  return (
    <div className="flex flex-col-reverse items-end">
      <dt className="text-xs tracking-[var(--f1-tracking-label)] text-text-3 uppercase">{label}</dt>
      <dd className={large ? "tnum font-mono text-xl font-semibold text-text-1" : "tnum font-mono text-text-2"}>
        {value}
      </dd>
    </div>
  );
}
