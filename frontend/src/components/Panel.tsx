import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * A card: its own surface, a 1px border, a header strip, lifting on hover.
 *
 * docs/design.md rejected hairline dividers on a flat ground as not enough separation, so every section on
 * every screen is one of these.
 */
export function Panel({
  title,
  aside,
  className,
  children,
}: {
  title: string;
  aside?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section
      className={cn(
        "flex min-w-0 flex-col rounded-md border border-border bg-surface-1 transition-colors",
        "hover:border-border-hover hover:bg-surface-2",
        className,
      )}
    >
      <header className="flex h-[var(--f1-header-h)] shrink-0 items-center justify-between gap-3 border-b border-border-soft bg-surface-sunken px-[var(--f1-space-4)]">
        <h2 className="text-xs font-semibold tracking-[var(--f1-tracking-label)] text-text-3 uppercase">{title}</h2>
        {aside}
      </header>
      <div className="min-h-0 flex-1 p-[var(--f1-panel-pad)]">{children}</div>
    </section>
  );
}
