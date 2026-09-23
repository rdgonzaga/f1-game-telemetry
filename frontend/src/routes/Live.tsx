import { ComingIn } from "@/components/ComingIn";
import { CarPanel } from "@/components/live/CarPanel";
import { TimingPanel } from "@/components/live/TimingPanel";
import { TyrePanel } from "@/components/live/TyrePanel";

/**
 * The live view. Not lazy: it is the route the app opens on, so its code must already be there.
 *
 * Each panel writes its values through refs and requestAnimationFrame rather than re-rendering per
 * telemetry frame (AGENTS.md), so they are not simple children of this file.
 *
 * Two columns of equal rows, so four panels sit 2 by 2 and none is left alone on a row.
 */
export default function Live() {
  return (
    <div className="grid h-full grid-cols-1 gap-[var(--f1-gap)] xl:grid-cols-2 xl:auto-rows-fr">
      <CarPanel />
      <TyrePanel />
      <TimingPanel />
      <ComingIn title="ERS and aero" issue={26} what="ERS store and deployment, overtake, and 2026 active aero." />
    </div>
  );
}
