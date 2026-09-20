import { ComingIn } from "@/components/ComingIn";

/**
 * The live view. Not lazy: it is the route the app opens on, so its code must already be there.
 *
 * The panels land one issue at a time. Each will write its values through refs and requestAnimationFrame
 * rather than re-rendering per telemetry frame (AGENTS.md), so they are not simple children of this file.
 */
export default function Live() {
  return (
    <div className="grid h-full grid-cols-1 gap-[var(--f1-gap)] xl:grid-cols-3">
      <ComingIn title="Speed and inputs" issue={23} what="Speed, gear, RPM and the throttle, brake and steering bars." />
      <ComingIn title="Tyres" issue={24} what="Carcass temperature, wear and pressure for all four corners." />
      <ComingIn title="Timing" issue={25} what="Lap time, the delta to the session best, fuel and session info." />
      <ComingIn title="ERS and aero" issue={26} what="ERS store and deployment, overtake, and 2026 active aero." />
    </div>
  );
}
