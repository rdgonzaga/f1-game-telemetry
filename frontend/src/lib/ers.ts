/**
 * ERS, overtake and active aero, as the power panel writes them.
 *
 * Pure and allocation-light: these run inside a frame callback.
 */
import { hasErs, regulations2026Apply, type LiveSession, type LiveTelemetry2 } from "@/api/types";

/** The store's ceiling in both formats: every F1 recording tops out at exactly 4.00 MJ. */
export const ERS_STORE_MAX_J = 4_000_000;

/** `names.ERS_DEPLOY_MODES` on the backend. Mode 3 is Overtake in format 2025 and Boost in format 2026. */
export function deployModeName(mode: number, packetFormat: number | null | undefined): string {
  switch (mode) {
    case 0:
      return "None";
    case 1:
      return "Medium";
    case 2:
      return "Hotlap";
    case 3:
      return packetFormat === 2025 ? "Overtake" : "Boost";
    default:
      return `Mode ${mode}`;
  }
}

export interface Sections {
  /** F1 in either format; never F2, whose store reads 0.00 MJ rather than nothing. */
  ers: boolean;
  /** Overtake and active aero both live in CarTelemetry2 and both follow the 2026 regulations flag. */
  regs2026: boolean;
}

/**
 * Which parts of the panel apply. Aero is never gated on the packet format or on the Session packet's zone list:
 * F2 in a 2026-format stream lists four zones and has none (docs/design.md).
 */
export function sections(session: LiveSession | null | undefined, telemetry2: LiveTelemetry2 | null | undefined): Sections {
  return { ers: hasErs(session), regs2026: regulations2026Apply(telemetry2) };
}

/** Joules as megajoules, two places, no unit. */
export function mj(joules: number): string {
  return (joules / 1_000_000).toFixed(2);
}

/** The line under a 2026 state: where it can next be used, if the game says. */
export function activation(available: boolean, distance: number): string {
  if (distance > 0) return `in ${distance} m`;
  return available ? "available" : "";
}
