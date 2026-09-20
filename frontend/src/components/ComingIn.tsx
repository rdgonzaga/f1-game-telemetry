import { Panel } from "@/components/Panel";

/**
 * A panel that says which issue builds it, rather than drawing numbers nobody measured.
 *
 * docs/design.md: never show a value we cannot stand behind. An honest empty state beats a confident
 * fabrication, and that applies to a scaffold as much as to a missing track map.
 */
export function ComingIn({ title, issue, what }: { title: string; issue: number; what: string }) {
  return (
    <Panel title={title}>
      <p className="text-text-3">{what}</p>
      <p className="mt-[var(--f1-space-2)] text-sm text-text-disabled">Built in #{issue}.</p>
    </Panel>
  );
}
