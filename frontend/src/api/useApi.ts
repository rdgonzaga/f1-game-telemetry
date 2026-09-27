import { useEffect, useState } from "react";

import { ApiError } from "./client";

export type Loaded<T> =
  | { state: "loading" }
  | { state: "ready"; data: T }
  | { state: "missing" } // a 404: the thing asked for isn't there
  | { state: "failed"; message: string };

/**
 * One REST request per change of `key`, aborted if the view goes away first.
 *
 * For the saved-session views, which load once and don't change underneath the reader. Live data comes over
 * the WebSocket instead.
 */
export function useApi<T>(key: string, load: (signal: AbortSignal) => Promise<T>): Loaded<T> {
  const [result, setResult] = useState<{ key: string; loaded: Loaded<T> } | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal).then(
      (data) => setResult({ key, loaded: { state: "ready", data } }),
      (error: unknown) => {
        if (controller.signal.aborted) return;
        const loaded: Loaded<T> =
          error instanceof ApiError && error.status === 404
            ? { state: "missing" }
            : { state: "failed", message: error instanceof Error ? error.message : String(error) };
        setResult({ key, loaded });
      },
    );
    return () => controller.abort();
    // `load` is a fresh closure every render; `key` is what says the request changed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  // A result for an earlier key is stale the moment the key changes, so it reads as loading, not as that data.
  return result?.key === key ? result.loaded : { state: "loading" };
}
