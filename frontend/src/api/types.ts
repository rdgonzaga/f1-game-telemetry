/**
 * Friendly names for the generated schema, so nothing outside this folder reaches into `components["schemas"]`.
 *
 * Everything here is an alias. Adding a field is a backend change followed by `npm run gen:api`; if a type here
 * looks wrong, the backend model in `f1telemetry/schemas.py` is what to fix.
 */
import type { components } from "./schema";

type Schemas = components["schemas"];

export type SetupInfo = Schemas["SetupInfo"];
export type SessionSummary = Schemas["SessionSummary"];
export type SessionDocument = Schemas["SessionDocument"];
export type LapSummary = Schemas["LapSummary"];
export type LapDocument = Schemas["LapDocument"];
export type LapColumns = Schemas["LapColumns"];
export type CompareResult = Schemas["CompareResult"];
export type CompareLap = Schemas["CompareLap"];
export type Minisector = Schemas["Minisector"];
export type Track = Schemas["Track"];

/** The `/ws/live` messages. Every one carries a `type`, so this is a discriminated union. */
export type LiveSnapshot = Schemas["LiveSnapshot"];
export type LiveHello = Schemas["LiveHello"];
export type LiveSessionStarted = Schemas["LiveSessionStarted"];
export type LiveLapCompleted = Schemas["LiveLapCompleted"];
export type LiveLapReopened = Schemas["LiveLapReopened"];
export type LiveSessionEnded = Schemas["LiveSessionEnded"];

export type LiveMessage =
  | LiveSnapshot
  | LiveHello
  | LiveSessionStarted
  | LiveLapCompleted
  | LiveLapReopened
  | LiveSessionEnded;

/** The packet slots inside a snapshot, each null until a packet of that kind has arrived. */
export type LiveSession = Schemas["LiveSession"];
export type LiveLap = Schemas["LiveLap"];
export type LiveTelemetry = Schemas["LiveTelemetry"];
export type LiveStatus = Schemas["LiveStatus"];
export type LiveDamage = Schemas["LiveDamage"];
export type LiveTelemetry2 = Schemas["LiveTelemetry2"];
export type LiveDelta = Schemas["LiveDelta"];

/**
 * Whether the 2026 regulations apply, which is what active aero must be gated on.
 *
 * Never gate on the packet format and never on the aero zone list being non-empty: an F2 session in a
 * 2026-format stream still lists four zones in the Session packet. See docs/design.md.
 */
export function regulations2026Apply(telemetry2: LiveTelemetry2 | null | undefined): boolean {
  return telemetry2?.regulations_2026_applicable ?? false;
}

/** `names.FORMULA_F2` on the backend. F1 Modern is 0 and F1 26 is 13, so this is not a range check. */
export const FORMULA_F2 = 2;

/** F2 has no ERS, and reports a 0.00 MJ store rather than nothing at all, so the store cannot be the test. */
export function hasErs(session: LiveSession | null | undefined): boolean {
  return session != null && session.formula !== FORMULA_F2;
}
