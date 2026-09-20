/**
 * React bindings for the live store.
 *
 * There are two kinds, and picking the wrong one is the performance bug this whole file exists to
 * prevent.
 *
 * - `useLiveStatus`, `useLiveSession`, `useLastLap`: coarse state that changes rarely. These render.
 * - `useLiveFrame`: a telemetry value at 30 Hz. This does **not** render. It subscribes outside
 *   React, coalesces into one `requestAnimationFrame`, and hands you the snapshot so you can write
 *   a ref's `textContent` yourself.
 *
 * If you find yourself wanting `useStore(s => s.snapshot)` in a panel, that is the bug: it re-renders
 * the subtree 30 times a second. Use `useLiveFrame` and write through a ref.
 */
import { useEffect, useRef } from "react";
import { useStore } from "zustand";

import type { LiveSnapshot } from "@/api/types";
import { liveStore, type LiveState, type LiveStatus } from "@/live/store";

export function useLiveStatus(): LiveStatus {
  return useStore(liveStore, (state) => state.status);
}

export function useLiveSession(): LiveState["session"] {
  return useStore(liveStore, (state) => state.session);
}

export function useLastLap(): LiveState["lastLap"] {
  return useStore(liveStore, (state) => state.lastLap);
}

/** Whole seconds since the last packet, for the paused badge. Changes about once a second. */
export function useStaleSeconds(): number {
  return useStore(liveStore, (state) => state.staleSeconds);
}

/**
 * Run `draw` on every animation frame in which the snapshot changed, without rendering.
 *
 * The subscription is transient: it fires outside React and only schedules a frame. Several
 * snapshots landing inside one frame collapse into a single call, so the work is bounded by the
 * display's refresh rate rather than by the 30 Hz feed.
 *
 * `draw` is held in a ref, so passing an inline arrow function does not resubscribe every render.
 */
export function useLiveFrame(draw: (snapshot: LiveSnapshot) => void): void {
  const latest = useRef(draw);
  // In an effect rather than during render: a ref write during render is what React 19 warns about,
  // and the subscription below only ever reads it from a frame callback anyway.
  useEffect(() => {
    latest.current = draw;
  });

  useEffect(() => {
    let frame: number | null = null;
    let pending: LiveSnapshot | null = null;

    const paint = () => {
      frame = null;
      const snapshot = pending;
      pending = null;
      if (snapshot) latest.current(snapshot);
    };

    const schedule = (snapshot: LiveSnapshot | null) => {
      if (snapshot === null) return;
      pending = snapshot;
      frame ??= requestAnimationFrame(paint);
    };

    // Paint immediately with whatever is already there, so a panel that mounts mid-session is not
    // blank until the next packet. A paused game would otherwise leave it empty indefinitely.
    schedule(liveStore.getState().snapshot);
    const unsubscribe = liveStore.subscribe((state) => state.snapshot, schedule);

    return () => {
      unsubscribe();
      if (frame !== null) cancelAnimationFrame(frame);
    };
  }, []);
}
