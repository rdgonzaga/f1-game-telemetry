import { CarPanel } from "@/components/live/CarPanel";
import { PowerPanel } from "@/components/live/PowerPanel";
import { TimingPanel } from "@/components/live/TimingPanel";
import { TyrePanel } from "@/components/live/TyrePanel";
import { SetupScreen } from "@/components/setup/SetupScreen";
import { useLiveStatus } from "@/live/useLive";

/**
 * The live view. Not lazy: it is the route the app opens on, so its code must already be there.
 *
 * Each panel writes its values through refs and requestAnimationFrame rather than re-rendering per
 * telemetry frame (AGENTS.md), so they are not simple children of this file.
 *
 * Two columns of equal rows, so four panels sit 2 by 2 and none is left alone on a row.
 *
 * Until the game has sent anything there is nothing to draw, so the first run shows the setup screen here.
 * Paused is different: the last values stay up, dimmed.
 */
export default function Live() {
  const status = useLiveStatus();
  if (status === "waiting") return <SetupScreen />;
  return (
    <div className="grid h-full grid-cols-1 gap-[var(--f1-gap)] xl:grid-cols-2 xl:auto-rows-fr">
      <CarPanel />
      <TyrePanel />
      <TimingPanel />
      <PowerPanel />
    </div>
  );
}
