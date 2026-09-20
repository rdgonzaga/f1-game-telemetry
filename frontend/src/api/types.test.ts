import { describe, expect, it } from "vitest";

import { hasErs, regulations2026Apply } from "@/api/types";
import type { LiveSession, LiveTelemetry2 } from "@/api/types";

// The trap docs/design.md measured: an F2 session in a 2026-format stream still lists four active aero zones
// and reports a 0.00 MJ ERS store. Gating on the format, or on the zone list, paints two dead widgets.
const F2_IN_2026: Pick<LiveTelemetry2, "regulations_2026_applicable"> = { regulations_2026_applicable: false };
const F1_IN_2026: Pick<LiveTelemetry2, "regulations_2026_applicable"> = { regulations_2026_applicable: true };

function session(formula: number): LiveSession {
  return { formula } as LiveSession;
}

describe("active aero gating", () => {
  it("follows the regulations flag, not the packet format", () => {
    expect(regulations2026Apply(F1_IN_2026 as LiveTelemetry2)).toBe(true);
    expect(regulations2026Apply(F2_IN_2026 as LiveTelemetry2)).toBe(false);
  });

  it("is off when the packet is absent, which is every 2025-format stream", () => {
    expect(regulations2026Apply(null)).toBe(false);
    expect(regulations2026Apply(undefined)).toBe(false);
  });
});

describe("ERS gating", () => {
  it("is off for F2, which has no ERS at all", () => {
    expect(hasErs(session(2))).toBe(false);
  });

  it("is on for F1, modern and 2026 alike", () => {
    expect(hasErs(session(0))).toBe(true); // F1 Modern
    expect(hasErs(session(13))).toBe(true); // F1 26
  });

  it("is off before a Session packet has arrived", () => {
    expect(hasErs(null)).toBe(false);
  });
});
