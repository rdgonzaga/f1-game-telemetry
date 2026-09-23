/**
 * Read a unitless threshold out of `tokens.css`, so CSS and TypeScript share one number.
 *
 * Call it once at mount, never per frame: `getComputedStyle` forces a style recalculation.
 */
export function numberToken(name: `--f1-${string}`): number {
  return Number.parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name));
}
