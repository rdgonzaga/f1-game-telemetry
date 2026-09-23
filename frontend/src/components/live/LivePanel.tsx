import type { ComponentProps } from "react";

import { Panel } from "@/components/Panel";
import { cn } from "@/lib/utils";
import { useLiveStatus } from "@/live/useLive";

/**
 * A panel on the live view. Once packets stop it keeps its last values, dimmed and desaturated.
 *
 * docs/design.md: zeroing them would be a lie, and hiding them throws away what the car was doing when the
 * game dropped out. The status changes rarely, so reading it here costs a render per state change, not per
 * frame.
 */
export function LivePanel({ className, ...props }: ComponentProps<typeof Panel>) {
  const status = useLiveStatus();
  const stale = status === "paused" || status === "offline";

  return (
    <Panel
      {...props}
      className={cn(
        "[transition-property:border-color,background-color,filter] duration-[var(--f1-duration-base)]",
        stale && "[filter:var(--f1-stale-filter)]",
        className,
      )}
    />
  );
}
