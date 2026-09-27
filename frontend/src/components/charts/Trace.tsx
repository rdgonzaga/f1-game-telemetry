import { useEffect, useRef } from "react";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";

import { formatDistance } from "@/lib/trace";
import { numberToken, stringToken } from "@/lib/tokens";

type Token = `--f1-${string}`;

export interface TraceSeries {
  label: string;
  values: number[];
  /** Which lap: `--f1-lap-a` or `--f1-lap-b` (docs/design.md, the compare rule). */
  stroke: Token;
  /** A px length token, e.g. `--f1-lap-a-width`. */
  width: Token;
  dash?: Token;
  /** Which channel: an `--f1-chart-*` colour, tinted under the line. */
  fill?: Token;
  /** Where the fill closes: 0 for a channel either side of zero (steering). Defaults to the bottom of the chart. */
  fillTo?: number;
  /** Hold each value until the next, for a channel that jumps rather than moves (gear). */
  stepped?: boolean;
  /** One bar per value, centred on its distance (minisectors). */
  bars?: boolean;
  /**
   * Coloured by sign instead of by lap: loss above zero, gain below. For the delta, which belongs to neither lap
   * (docs/design.md). `stroke` then only colours the legend swatch.
   */
  signed?: boolean;
  format: (value: number) => string;
}

const stepped = uPlot.paths.stepped?.({ align: 1 });
const bars = uPlot.paths.bars?.({ size: [0.86, Infinity], align: 0 });

/** A vertical gradient with a hard stop at zero, so one line changes colour exactly where it crosses. */
function bySign(u: uPlot, above: string, below: string): CanvasGradient {
  const { top, height } = u.bbox;
  const zero = Math.min(Math.max((u.valToPos(0, "y", true) - top) / height, 0), 1);
  const gradient = u.ctx.createLinearGradient(0, top, 0, top + height);
  gradient.addColorStop(0, above);
  gradient.addColorStop(zero, above);
  gradient.addColorStop(zero, below);
  gradient.addColorStop(1, below);
  return gradient;
}

/**
 * One channel against lap distance, with a crosshair readout and drag-to-zoom (double-click resets).
 *
 * uPlot draws straight onto a canvas, so moving the cursor never re-renders React: the readout is written into
 * its spans from uPlot's own hook. Charts sharing a `syncKey` move one cursor together. Pass memoised `series`
 * and `distance`, since a new array rebuilds the chart.
 */
export function Trace({
  distance,
  series,
  range,
  height = 220,
  shade,
  syncKey,
  ticks: tickFormat,
  distanceLabels = true,
  splits,
  distanceRange,
}: {
  distance: number[];
  series: TraceSeries[];
  /** A fixed y range, for channels with known bounds; otherwise it fits the data. */
  range?: readonly [number, number];
  height?: number;
  /** Samples to shade across the full height (where the brake was down), aligned with `distance`. */
  shade?: boolean[];
  syncKey?: string;
  /** Y axis labels, when the raw value isn't what a reader expects (0-1 pedals read as percent). */
  ticks?: (value: number) => string;
  /** Off for all but the bottom chart of a stack: the gridlines stay, the repeated kilometres go. */
  distanceLabels?: boolean;
  /** Y ticks at exactly these values, where uPlot's own spacing would leave a short chart with one label. */
  splits?: number[];
  /** The x extent before any zoom, for a chart whose points don't reach the ends of the lap (minisector bars). */
  distanceRange?: readonly [number, number];
}) {
  const plotRef = useRef<HTMLDivElement>(null);
  const atRef = useRef<HTMLSpanElement>(null);
  const valueRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const [low, high] = range ?? [];
  const [start, end] = distanceRange ?? [];

  useEffect(() => {
    const root = plotRef.current;
    if (!root) return;
    const font = `${stringToken("--f1-text-xs")} ${stringToken("--f1-font-num")}`;
    const tick = stringToken("--f1-text-3");
    const grid = { stroke: stringToken("--f1-chart-grid"), width: 1 };
    const ticks = { stroke: stringToken("--f1-chart-axis"), width: 1 };
    const opacity = numberToken("--f1-chart-fill-opacity");
    const band = stringToken("--f1-accent-dim");
    const loss = stringToken("--f1-loss");
    const gain = stringToken("--f1-gain");

    const readout = (u: uPlot) => {
      const i = u.cursor.idx;
      if (atRef.current) atRef.current.textContent = i == null ? "—" : formatDistance(distance[i] ?? 0);
      series.forEach((s, n) => {
        const span = valueRefs.current[n];
        if (span) span.textContent = i == null ? "—" : s.format(s.values[i] ?? Number.NaN);
      });
    };

    const shadeRuns = (u: uPlot) => {
      if (!shade) return;
      const { ctx, bbox } = u;
      ctx.save();
      ctx.fillStyle = band;
      for (let i = 0; i < shade.length; i++) {
        if (!shade[i]) continue;
        const start = i;
        while (i + 1 < shade.length && shade[i + 1]) i++;
        const x0 = u.valToPos(distance[start] ?? 0, "x", true);
        const x1 = u.valToPos(distance[i] ?? 0, "x", true);
        ctx.fillRect(x0, bbox.top, Math.max(x1 - x0, 1), bbox.height);
      }
      ctx.restore();
    };

    const plot = new uPlot(
      {
        width: root.clientWidth,
        height,
        legend: { show: false },
        cursor: {
          sync: syncKey ? { key: syncKey } : undefined,
          drag: { x: true, y: false },
          points: { size: 7, fill: stringToken("--f1-chart-cursor") },
        },
        scales: {
          x: { time: false, range: start === undefined ? undefined : () => [start, end as number] },
          y: low === undefined ? {} : { range: [low, high as number] },
        },
        axes: [
          distanceLabels
            ? { stroke: tick, font, grid, ticks, values: (_u, splits) => splits.map(formatDistance) }
            : { grid, ticks: { show: false }, size: 6, values: (_u, splits) => splits.map(() => "") },
          {
            stroke: tick,
            font,
            grid,
            ticks,
            // A fixed width, so the plot areas of stacked charts line up and one cursor reads down all of them.
            size: 52,
            values: tickFormat ? (_u, values) => values.map(tickFormat) : undefined,
            splits: splits ? () => splits : undefined,
          },
        ],
        series: [
          {},
          ...series.map((s): uPlot.Series => {
            const signedFill = (alpha: number) => (u: uPlot) =>
              bySign(u, withAlpha(loss, alpha), withAlpha(gain, alpha));
            return {
              label: s.label,
              stroke: s.signed ? (u) => bySign(u, loss, gain) : stringToken(s.stroke),
              width: s.bars ? 0 : Number.parseFloat(stringToken(s.width)),
              dash: s.dash ? stringToken(s.dash).split(/\s+/).map(Number) : undefined,
              fill: s.bars
                ? signedFill(0.85)
                : s.signed
                  ? signedFill(opacity)
                  : s.fill && withAlpha(stringToken(s.fill), opacity),
              fillTo: s.fillTo,
              paths: s.bars ? bars : s.stepped ? stepped : undefined,
              points: { show: false },
            };
          }),
        ],
        hooks: { setCursor: [readout], drawClear: [shadeRuns] },
      },
      [distance, ...series.map((s) => s.values)],
      root,
    );
    readout(plot);

    const observer = new ResizeObserver(() => plot.setSize({ width: root.clientWidth, height }));
    observer.observe(root);
    return () => {
      observer.disconnect();
      plot.destroy();
    };
  }, [distance, series, low, high, height, shade, syncKey, tickFormat, distanceLabels, splits, start, end]);

  return (
    <div className="flex flex-col gap-[var(--f1-space-2)]">
      <div className="tnum flex flex-wrap items-baseline gap-x-[var(--f1-space-4)] font-mono text-sm">
        <span ref={atRef} className="w-20 text-text-3" />
        {series.map((s, n) => (
          <span key={s.label} className="flex items-baseline gap-2">
            {series.length > 1 && (
              // The legend docs/design.md requires for two or more series: the line itself, dash and all.
              <span
                aria-hidden
                className="w-6 self-center border-t-2"
                style={{ borderTopColor: `var(${s.stroke})`, borderTopStyle: s.dash ? "dashed" : "solid" }}
              />
            )}
            <span className="font-sans text-xs tracking-[var(--f1-tracking-label)] text-text-3 uppercase">
              {s.label}
            </span>
            <span
              ref={(span) => {
                valueRefs.current[n] = span;
              }}
              className={n === 0 ? "min-w-16 text-text-1" : "min-w-16 text-text-2"}
            />
          </span>
        ))}
      </div>
      <div ref={plotRef} className="rounded-sm bg-[var(--f1-surface-chart)]" />
    </div>
  );
}

function withAlpha(hex: string, alpha: number): string {
  const value = Number.parseInt(hex.slice(1, 7), 16);
  return `rgba(${value >> 16}, ${(value >> 8) & 255}, ${value & 255}, ${alpha})`;
}
