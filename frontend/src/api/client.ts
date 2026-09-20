/**
 * Where the API lives, and a typed fetch for the REST half.
 *
 * In a build the dashboard is served by the app itself, so the API is the same origin and the base is empty.
 * In development Vite serves the page on 5173 and the API answers on 20778; `app.py` allows that origin by
 * name, which is why the dev port is fixed in `vite.config.ts`.
 *
 * The live feed is a WebSocket and is not fetched here; #22 owns it. `liveSocketUrl` is the one thing it needs
 * from this module, so the two halves cannot disagree about where the backend is.
 */
import type { CompareResult, LapDocument, SessionSummary, SetupInfo } from "./types";

const DEV_API_PORT = 20778;

export const apiBase: string = import.meta.env.DEV ? `http://localhost:${DEV_API_PORT}` : "";

export function liveSocketUrl(): string {
  if (import.meta.env.DEV) return `ws://localhost:${DEV_API_PORT}/ws/live`;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/live`;
}

/** A failed request, carrying the status so a caller can tell "no such lap" from "the backend is not there". */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, { signal });
  if (!response.ok) {
    // FastAPI puts the reason in `detail`; a proxy or a dead backend will not, so fall back to the status.
    const detail = await response
      .json()
      .then((body: unknown) =>
        typeof body === "object" && body !== null && "detail" in body ? String(body.detail) : null,
      )
      .catch(() => null);
    throw new ApiError(response.status, detail ?? `${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

export const api = {
  setup: (signal?: AbortSignal) => getJson<SetupInfo>("/api/setup", signal),

  sessions: (signal?: AbortSignal) => getJson<SessionSummary[]>("/api/sessions", signal),

  session: (sessionId: string, signal?: AbortSignal) =>
    getJson<SessionSummary>(`/api/sessions/${encodeURIComponent(sessionId)}`, signal),

  lap: (sessionId: string, number: number, signal?: AbortSignal) =>
    getJson<LapDocument>(`/api/sessions/${encodeURIComponent(sessionId)}/laps/${number}`, signal),

  compare: (a: { session: string; lap: number }, b: { session: string; lap: number }, signal?: AbortSignal) => {
    const query = new URLSearchParams({
      session_a: a.session,
      lap_a: String(a.lap),
      session_b: b.session,
      lap_b: String(b.lap),
    });
    return getJson<CompareResult>(`/api/compare?${query.toString()}`, signal);
  },
};
