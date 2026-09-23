/**
 * Temperature bands for the tyre grid. The thresholds live in `tokens.css`; this only picks and applies them.
 *
 * docs/design.md: the band set follows the fitted compound, never the weather. A driver who stayed out on
 * slicks in the rain is on slicks, and that is the moment the grid most needs to be right.
 */
import { numberToken } from "@/lib/tokens";

export type Band = "cold" | "warming" | "optimal" | "hot" | "critical";

/** One name per gap between thresholds, so a list of N edges takes N + 1 names. */
export const TYRE_BANDS = ["cold", "warming", "optimal", "hot", "critical"] as const satisfies readonly Band[];
export const BRAKE_BANDS = ["cold", "optimal", "hot", "critical"] as const satisfies readonly Band[];

export interface TyreTokens {
  slick: readonly number[];
  inter: readonly number[];
  wet: readonly number[];
  interCompound: number;
  wetCompound: number;
}

/** Read every tyre threshold once. Call at mount, never per frame: `getComputedStyle` forces a style recalc. */
export function readTyreTokens(): TyreTokens {
  const set = (prefix: string) =>
    (["cold", "warming", "optimal", "hot"] as const).map((edge) => numberToken(`--f1-tyre-inner-${prefix}${edge}`));
  return {
    slick: set(""),
    inter: set("inter-"),
    wet: set("wet-"),
    interCompound: numberToken("--f1-tyre-compound-inter"),
    wetCompound: numberToken("--f1-tyre-compound-wet"),
  };
}

export function readBrakeTokens(): readonly number[] {
  return [numberToken("--f1-brake-cold"), numberToken("--f1-brake-working"), numberToken("--f1-brake-hot")];
}

/** The carcass thresholds for a visual compound id. Anything that is not an inter or a full wet is a slick. */
export function bandsFor(compound: number | undefined, tokens: TyreTokens): readonly number[] {
  if (compound === tokens.interCompound) return tokens.inter;
  if (compound === tokens.wetCompound) return tokens.wet;
  return tokens.slick;
}

/** A value sitting exactly on a threshold belongs to the band above it: "below this: cold". */
export function band(value: number, edges: readonly number[], names: readonly Band[]): Band {
  const above = edges.filter((edge) => value >= edge).length;
  return names[above] ?? "critical";
}
