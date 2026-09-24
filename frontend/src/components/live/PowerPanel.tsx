import { useRef, type ReactNode } from "react";

import { LivePanel } from "@/components/live/LivePanel";
import { ERS_STORE_MAX_J, activation, deployModeName, mj, sections } from "@/lib/ers";
import { useLiveFrame } from "@/live/useLive";

/**
 * The ERS store and this lap's energy, then 2026 overtake and active aero.
 *
 * Like `TimingPanel`, nothing here renders per frame, including the series gates: which sections apply is worked
 * out per frame and written as `hidden`, so switching from F1 to F2 never re-renders either. Colour is a
 * `data-tone` attribute the classes select on.
 *
 * Deployed energy is a plain number, not a share of the store: a 2026 lap deploys up to 8.6 MJ from a 4 MJ store.
 */
export function PowerPanel() {
  const body = useRef<HTMLDivElement>(null);
  const noErs = useRef<HTMLParagraphElement>(null);
  const regs = useRef<HTMLDivElement>(null);
  const noRegs = useRef<HTMLParagraphElement>(null);
  const store = useRef<HTMLSpanElement>(null);
  const storeBar = useRef<HTMLDivElement>(null);
  const storeMj = useRef<HTMLSpanElement>(null);
  const deploy = useRef<HTMLSpanElement>(null);
  const harvested = useRef<HTMLSpanElement>(null);
  const deployed = useRef<HTMLSpanElement>(null);
  const overtake = useRef<HTMLSpanElement>(null);
  const overtakeAt = useRef<HTMLSpanElement>(null);
  const aero = useRef<HTMLSpanElement>(null);
  const aeroAt = useRef<HTMLSpanElement>(null);

  useLiveFrame(({ session, status, telemetry2, packet_format }) => {
    const show = sections(session, telemetry2);
    // Before the Session packet the series is unknown, so show the ERS layout rather than claim it is F2.
    const ers = session == null || show.ers;
    hide(body, !ers);
    hide(noErs, ers);
    hide(regs, !show.regs2026);
    hide(noRegs, show.regs2026);

    if (status) {
      const fraction = Math.min(Math.max(status.ers_store_energy / ERS_STORE_MAX_J, 0), 1);
      text(store, `${Math.round(fraction * 100)}%`);
      if (storeBar.current) storeBar.current.style.transform = `scaleX(${fraction})`;
      text(storeMj, `${mj(status.ers_store_energy)} MJ`);
      text(deploy, deployModeName(status.ers_deploy_mode, packet_format));
      const harvest = mj(status.ers_harvested_this_lap_mguk + status.ers_harvested_this_lap_mguh);
      const limit = status.ers_harvest_limit_per_lap;
      text(harvested, limit ? `${harvest} / ${mj(limit)} MJ` : `${harvest} MJ`);
      text(deployed, `${mj(status.ers_deployed_this_lap)} MJ`);
    } else {
      for (const ref of [store, storeMj, deploy, harvested, deployed]) text(ref, "—");
      if (storeBar.current) storeBar.current.style.transform = "scaleX(0)";
    }

    if (telemetry2 && show.regs2026) {
      const state = telemetry2.overtake_active ? "active" : telemetry2.overtake_available ? "available" : "off";
      text(overtake, state === "active" ? "Active" : state === "available" ? "Available" : "Off");
      attr(overtake, "data-tone", state);
      text(overtakeAt, activation(telemetry2.overtake_available, telemetry2.overtake_activation_distance));

      const straight = telemetry2.active_aero_mode === 1;
      text(aero, straight ? "Straight" : "Corner");
      attr(aero, "data-tone", straight ? "straight" : "corner");
      text(aeroAt, activation(telemetry2.active_aero_available, telemetry2.active_aero_activation_distance));
    }
  });

  return (
    <LivePanel title="ERS and aero">
      <p ref={noErs} hidden className="text-sm text-text-3">
        F2 cars have no ERS or active aero.
      </p>
      <div ref={body} className="flex h-full flex-col justify-between gap-[var(--f1-space-4)]">
        <div className="grid grid-cols-2 gap-[var(--f1-gap)]">
          <Stat label="ERS store">
            <span className={HERO} ref={store} />
            <div className="mt-[var(--f1-space-2)] h-2 overflow-hidden rounded-sm bg-surface-sunken">
              <div ref={storeBar} className="h-full w-full origin-left bg-ers" style={{ transform: "scaleX(0)" }} />
            </div>
            <span ref={storeMj} className="tnum mt-[var(--f1-space-1)] font-mono text-sm text-text-3" />
          </Stat>
          <Stat label="Deploy mode">
            <span className={VALUE} ref={deploy} />
          </Stat>
        </div>

        <div className="grid grid-cols-2 gap-[var(--f1-gap)]">
          <Stat label="Harvested this lap">
            <span className={VALUE} ref={harvested} />
          </Stat>
          <Stat label="Deployed this lap">
            <span className={VALUE} ref={deployed} />
          </Stat>
        </div>

        <p ref={noRegs} className="text-sm text-text-3">
          Overtake and active aero: 2026 regulations only.
        </p>
        <div ref={regs} hidden className="grid grid-cols-2 gap-[var(--f1-gap)]">
          <Stat label="Overtake">
            <span className={`${VALUE} ${TONES}`} ref={overtake} />
            <span ref={overtakeAt} className="tnum mt-[var(--f1-space-1)] text-sm text-text-3" />
          </Stat>
          <Stat label="Active aero">
            <span className={`${VALUE} ${TONES}`} ref={aero} />
            <span ref={aeroAt} className="tnum mt-[var(--f1-space-1)] text-sm text-text-3" />
          </Stat>
        </div>
      </div>
    </LivePanel>
  );
}

const HERO = "tnum font-mono text-xl leading-none font-semibold text-text-1";
const VALUE = "tnum font-mono text-lg leading-none text-text-1";
const TONES = [
  "data-[tone=active]:text-overtake",
  "data-[tone=off]:text-text-3",
  "data-[tone=straight]:text-[var(--f1-aero-straight)]",
  "data-[tone=corner]:text-[var(--f1-aero-corner)]",
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

function hide(ref: React.RefObject<HTMLElement | null>, hidden: boolean) {
  if (ref.current && ref.current.hidden !== hidden) ref.current.hidden = hidden;
}

function text(ref: React.RefObject<Element | null>, value: string) {
  if (ref.current && ref.current.textContent !== value) ref.current.textContent = value;
}

function attr(ref: React.RefObject<Element | null>, name: string, value: string) {
  if (ref.current && ref.current.getAttribute(name) !== value) ref.current.setAttribute(name, value);
}
