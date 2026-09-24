import { expect, it } from "vitest";

import type { LiveSession, LiveTelemetry2 } from "@/api/types";
import { deployModeName, sections } from "@/lib/ers";

const session = (formula: number) => ({ formula }) as LiveSession;
const telemetry2 = (regs: boolean) => ({ regulations_2026_applicable: regs }) as LiveTelemetry2;

it("gates each section on the series and the regulations flag, never on the format or aero zones", () => {
  // The four states measured in docs/design.md. F2 in format 2026 lists four aero zones; the flag says no.
  expect(sections(session(13), telemetry2(true))).toEqual({ ers: true, regs2026: true });
  expect(sections(session(0), null)).toEqual({ ers: true, regs2026: false });
  expect(sections(session(2), telemetry2(false))).toEqual({ ers: false, regs2026: false });
  expect(sections(session(2), null)).toEqual({ ers: false, regs2026: false });
  // Before the first Session packet, nothing is known, so nothing is painted.
  expect(sections(null, null)).toEqual({ ers: false, regs2026: false });
});

it("names deploy mode 3 by format", () => {
  expect(deployModeName(3, 2025)).toBe("Overtake");
  expect(deployModeName(3, 2026)).toBe("Boost");
});
