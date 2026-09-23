import { useImperativeHandle, useRef, useState } from "react";

import type { LiveSnapshot } from "@/api/types";
import { LivePanel } from "@/components/live/LivePanel";
import { BRAKE_BANDS, TYRE_BANDS, band, bandsFor, readBrakeTokens, readTyreTokens, type Band } from "@/lib/tyres";
import { useLiveFrame } from "@/live/useLive";

type Corner = "fl" | "fr" | "rl" | "rr";

/**
 * The four corners laid out like the car: carcass temperature, surface, wear, pressure and brake temperature.
 *
 * The carcass carries the colour; the surface swings 43-152 C inside one lap and would make the grid strobe,
 * so it is shown uncoloured (docs/design.md). Like `CarPanel`, nothing here renders per frame: values are
 * written through refs, and a colour is only touched when its band changes.
 */
export function TyrePanel() {
  const fl = useRef<CornerHandle>(null);
  const fr = useRef<CornerHandle>(null);
  const rl = useRef<CornerHandle>(null);
  const rr = useRef<CornerHandle>(null);
  const compound = useRef<HTMLSpanElement>(null);
  const compoundDot = useRef<HTMLSpanElement>(null);
  const age = useRef<HTMLSpanElement>(null);
  // Read once: getComputedStyle forces a style recalculation, which has no place in a frame callback.
  const [tyreTokens] = useState(readTyreTokens);
  const [brakeTokens] = useState(readBrakeTokens);

  useLiveFrame((snapshot) => {
    const fitted = snapshot.status?.visual_tyre_compound;
    const bands = bandsFor(fitted, tyreTokens);
    const corners = { fl, fr, rl, rr };
    for (const corner of CORNERS) corners[corner].current?.set(read(snapshot, corner), bands, brakeTokens);

    const tyre = fitted === undefined ? undefined : COMPOUNDS[fitted];
    text(compound, fitted === undefined ? "—" : (tyre?.name ?? `Compound ${fitted}`));
    if (compoundDot.current) compoundDot.current.style.backgroundColor = tyre ? `var(${tyre.colour})` : "transparent";
    text(age, snapshot.status ? `${snapshot.status.tyres_age_laps} laps` : "");
  });

  return (
    <LivePanel
      title="Tyres"
      aside={
        <span className="flex items-center gap-[var(--f1-space-2)] text-xs font-semibold tracking-[var(--f1-tracking-label)] text-text-2 uppercase">
          <span ref={compoundDot} className="size-2 rounded-full" />
          <span ref={compound} />
          <span ref={age} className="tnum font-mono font-normal tracking-normal text-text-3 normal-case" />
        </span>
      }
    >
      <div className="grid h-full grid-cols-2 gap-[var(--f1-gap)]">
        <CornerCell ref={fl} label="Front left" />
        <CornerCell ref={fr} label="Front right" mirrored />
        <CornerCell ref={rl} label="Rear left" />
        <CornerCell ref={rr} label="Rear right" mirrored />
      </div>
    </LivePanel>
  );
}

const CORNERS: readonly Corner[] = ["fl", "fr", "rl", "rr"];

/** Visual compound ids to the sidewall the game draws. F2's wet takes the wet colour, classic tyres stay unnamed. */
const COMPOUNDS: Record<number, { name: string; colour: `--f1-tyre-${string}` }> = {
  7: { name: "Inter", colour: "--f1-tyre-inter" },
  8: { name: "Wet", colour: "--f1-tyre-wet" },
  15: { name: "Wet", colour: "--f1-tyre-wet" },
  16: { name: "Soft", colour: "--f1-tyre-soft" },
  17: { name: "Medium", colour: "--f1-tyre-medium" },
  18: { name: "Hard", colour: "--f1-tyre-hard" },
  19: { name: "Super soft", colour: "--f1-tyre-soft" },
  20: { name: "Soft", colour: "--f1-tyre-soft" },
  21: { name: "Medium", colour: "--f1-tyre-medium" },
  22: { name: "Hard", colour: "--f1-tyre-hard" },
};

interface CornerValues {
  carcass?: number;
  surface?: number;
  pressure?: number;
  brake?: number;
  wear?: number;
}

/** Temperatures and pressure come from CarTelemetry, wear from CarDamage; either can be missing on its own. */
function read({ telemetry, damage }: LiveSnapshot, corner: Corner): CornerValues {
  return {
    carcass: telemetry?.[`tyre_inner_temperature_${corner}`],
    surface: telemetry?.[`tyre_surface_temperature_${corner}`],
    pressure: telemetry?.[`tyre_pressure_${corner}`],
    brake: telemetry?.[`brake_temperature_${corner}`],
    wear: damage?.[`tyre_wear_${corner}`],
  };
}

function text(ref: React.RefObject<Element | null>, value: string) {
  if (ref.current && ref.current.textContent !== value) ref.current.textContent = value;
}

function paint(el: HTMLElement | null, value: Band | undefined) {
  const next = value ?? "";
  if (!el || el.dataset.band === next) return;
  el.dataset.band = next;
  if (value) el.style.setProperty("--band", `var(--f1-temp-${value})`);
  else el.style.removeProperty("--band");
}

interface CornerHandle {
  set(values: CornerValues, tyreBands: readonly number[], brakeBands: readonly number[]): void;
}

/**
 * One corner. The tyre is a slab on the outside edge, tinted by the carcass band, so the four read as a car
 * from across the room; `mirrored` puts it on the right for the right-hand corners.
 */
function CornerCell({ ref, label, mirrored = false }: { ref: React.Ref<CornerHandle>; label: string; mirrored?: boolean }) {
  const tyre = useRef<HTMLDivElement>(null);
  const carcass = useRef<HTMLSpanElement>(null);
  const surface = useRef<HTMLSpanElement>(null);
  const wear = useRef<HTMLSpanElement>(null);
  const pressure = useRef<HTMLSpanElement>(null);
  const brake = useRef<HTMLSpanElement>(null);

  useImperativeHandle(ref, () => ({
    set({ carcass: c, surface: s, pressure: p, brake: b, wear: w }, tyreBands, brakeBands) {
      paint(tyre.current, c === undefined ? undefined : band(c, tyreBands, TYRE_BANDS));
      paint(brake.current, b === undefined ? undefined : band(b, brakeBands, BRAKE_BANDS));
      text(carcass, c === undefined ? "—" : String(c));
      text(surface, s === undefined ? "—" : `${s}°`);
      text(wear, w === undefined ? "—" : `${Math.round(w)}%`);
      text(pressure, p === undefined ? "—" : p.toFixed(1));
      text(brake, b === undefined ? "—" : `${b}°`);
    },
  }));

  return (
    <div className={`flex min-h-0 items-stretch gap-[var(--f1-space-3)] ${mirrored ? "flex-row-reverse" : ""}`}>
      <div
        ref={tyre}
        aria-label={`${label} carcass temperature`}
        className="flex w-[72px] shrink-0 flex-col items-center justify-center rounded-md border-2 border-[var(--band,var(--f1-border))] bg-[color-mix(in_srgb,var(--band,transparent)_14%,transparent)] transition-colors duration-[var(--f1-duration-base)]"
      >
        <span ref={carcass} className="tnum font-mono text-lg leading-none font-semibold text-[var(--band,var(--f1-text-1))]" />
        <span className="mt-[var(--f1-space-1)] text-xs text-text-3">°C</span>
      </div>

      <div className="flex min-w-0 flex-1 flex-col justify-center gap-[var(--f1-space-1)] text-sm">
        <p className={`text-xs font-semibold tracking-[var(--f1-tracking-label)] text-text-3 uppercase ${mirrored ? "text-right" : ""}`}>
          {label}
        </p>
        <dl className="grid gap-y-[var(--f1-space-1)]">
          <Row label="Surface">
            <span ref={surface} />
          </Row>
          <Row label="Wear">
            <span ref={wear} />
          </Row>
          <Row label="psi">
            <span ref={pressure} />
          </Row>
          <Row label="Brake">
            <span ref={brake} className="text-[var(--band,var(--f1-text-1))]" />
          </Row>
        </dl>
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-[var(--f1-space-2)]">
      <dt className="text-xs text-text-3">{label}</dt>
      <dd className="tnum font-mono text-text-1">{children}</dd>
    </div>
  );
}
