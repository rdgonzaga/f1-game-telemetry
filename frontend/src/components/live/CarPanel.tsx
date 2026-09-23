import { useImperativeHandle, useRef, useState } from "react";

import { LivePanel } from "@/components/live/LivePanel";
import { numberToken } from "@/lib/tokens";
import { useLiveFrame } from "@/live/useLive";

/**
 * Speed, gear and rpm as an instrument cluster, with the throttle, brake and steering bars under it.
 *
 * Nothing here renders per frame. Every live value is a ref, and `useLiveFrame` writes text nodes, SVG
 * attributes and transforms directly. The bars move by `scaleX`, which skips layout entirely.
 */
export function CarPanel() {
  const rpm = useRef<HTMLParagraphElement>(null);
  const maxRpm = useRef<HTMLSpanElement>(null);
  const revFill = useRef<SVGPathElement>(null);
  const revRed = useRef<SVGPathElement>(null);
  const speed = useRef<HTMLSpanElement>(null);
  const gear = useRef<HTMLSpanElement>(null);
  const throttle = useRef<InputBar>(null);
  const brake = useRef<InputBar>(null);
  const steer = useRef<InputBar>(null);
  // Read once: getComputedStyle forces a style recalculation, which has no place in a frame callback.
  const [red] = useState(() => numberToken("--f1-rev-redline"));

  useLiveFrame(({ telemetry, status }) => {
    // max_rpm comes from CarStatus, which can lag CarTelemetry. Without it there is no scale to draw on.
    const rev = telemetry && status ? Math.min(1, telemetry.engine_rpm / status.max_rpm) : 0;
    revFill.current?.setAttribute("stroke-dashoffset", String(1 - Math.min(rev, red)));
    revRed.current?.setAttribute("stroke-dasharray", `0 ${red} ${Math.max(0, rev - red)} 2`);

    text(maxRpm, status ? `${(status.max_rpm / 1000).toFixed(1)}k rpm` : "—");
    text(rpm, telemetry ? `${telemetry.engine_rpm.toLocaleString("en-US")} rpm` : "— rpm");
    text(speed, telemetry ? String(telemetry.speed) : "—");
    text(gear, telemetry ? gearLabel(telemetry.gear) : "—");

    throttle.current?.set(telemetry?.throttle, (v) => `${Math.round(v * 100)}%`);
    brake.current?.set(telemetry?.brake, (v) => `${Math.round(v * 100)}%`);
    steer.current?.set(telemetry?.steer, steerLabel);
  });

  return (
    <LivePanel title="Car">
      <div className="relative mx-auto max-w-[360px]">
        <p ref={rpm} className="tnum text-center font-mono text-sm text-text-2" />
        <svg viewBox="0 0 200 104" className="block w-full" role="img" aria-label="Engine rpm against the rev limit">
          <path d={ARC} pathLength={1} fill="none" strokeWidth={9} className="stroke-surface-sunken" />
          <path
            d={ARC}
            pathLength={1}
            fill="none"
            strokeWidth={9}
            strokeDasharray={`0 ${red} 1 1`}
            className="stroke-brand opacity-30"
          />
          <path
            ref={revFill}
            d={ARC}
            pathLength={1}
            fill="none"
            strokeWidth={9}
            strokeDasharray="1 1"
            strokeDashoffset={1}
            className="stroke-text-1"
          />
          <path ref={revRed} d={ARC} pathLength={1} fill="none" strokeWidth={9} strokeDasharray="0 2" className="stroke-brand" />
        </svg>

        <div className="absolute inset-x-0 bottom-0 flex flex-col items-center">
          <span ref={speed} className="tnum font-mono text-hero leading-[0.82] font-semibold tracking-[-0.045em] text-text-1" />
          <span className="mt-[var(--f1-space-1)] text-sm tracking-[0.22em] text-text-3 uppercase">km/h</span>
        </div>
        <div className="absolute bottom-0 left-full ml-[var(--f1-space-4)] flex flex-col items-center">
          <span ref={gear} className="tnum font-mono text-3xl leading-none font-semibold text-text-1" />
          <span className="text-xs tracking-[var(--f1-tracking-label)] text-text-3 uppercase">Gear</span>
        </div>
      </div>
      <div className="mx-auto flex max-w-[360px] justify-between font-mono text-xs text-text-3">
        <span>0</span>
        <span ref={maxRpm} className="tnum" />
      </div>

      <div className="mt-[var(--f1-space-4)] grid gap-[var(--f1-space-2)]">
        <Bar ref={throttle} label="Throttle" fill="bg-[var(--f1-chart-throttle)]" />
        <Bar ref={brake} label="Brake" fill="bg-[var(--f1-chart-brake)]" />
        <Bar ref={steer} label="Steer" fill="bg-[var(--f1-chart-steer)]" centred />
      </div>
    </LivePanel>
  );
}

/** A half circle from 9 o'clock to 3 o'clock, drawn left to right so the dash fills the way the rpm rises. */
const ARC = "M 12 96 A 88 88 0 0 1 188 96";

function text(ref: React.RefObject<Element | null>, value: string) {
  if (ref.current && ref.current.textContent !== value) ref.current.textContent = value;
}

function gearLabel(gear: number): string {
  if (gear < 0) return "R";
  if (gear === 0) return "N";
  return String(gear);
}

function steerLabel(steer: number): string {
  const magnitude = Math.abs(steer).toFixed(2);
  if (magnitude === "0.00") return magnitude;
  return `${steer < 0 ? "L" : "R"} ${magnitude}`;
}

interface InputBar {
  set(value: number | undefined, format: (v: number) => string): void;
}

/**
 * One input as a bar. `centred` draws from the middle outwards, for steering: a negative `scaleX` with a
 * left origin extends the fill leftwards, so one element covers both directions.
 */
function Bar({ ref, label, fill, centred = false }: { ref: React.Ref<InputBar>; label: string; fill: string; centred?: boolean }) {
  const bar = useRef<HTMLDivElement>(null);
  const value = useRef<HTMLSpanElement>(null);

  useImperativeHandle(ref, () => ({
    set(v, format) {
      if (bar.current) bar.current.style.transform = `scaleX(${v ?? 0})`;
      text(value, v === undefined ? "—" : format(v));
    },
  }));

  return (
    <div className="grid grid-cols-[72px_1fr_64px] items-center gap-[var(--f1-space-3)]">
      <span className="text-xs font-semibold tracking-[var(--f1-tracking-label)] text-text-3 uppercase">{label}</span>
      <div className="relative h-2 overflow-hidden rounded-sm bg-surface-sunken">
        {centred && <div className="absolute inset-y-0 left-1/2 w-px bg-border-control" />}
        <div
          ref={bar}
          className={`absolute inset-y-0 ${centred ? "left-1/2 w-1/2" : "left-0 w-full"} origin-left ${fill}`}
          style={{ transform: "scaleX(0)" }}
        />
      </div>
      <span ref={value} className="tnum text-right font-mono text-sm text-text-1" />
    </div>
  );
}
