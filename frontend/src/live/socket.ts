/**
 * The `/ws/live` connection: reconnects on its own, and decides when the game has gone quiet.
 *
 * Two things here are easy to get wrong.
 *
 * **The feed goes silent rather than repeating itself.** `LiveFeed.tick` sends nothing while the
 * picture is unchanged, so a paused game produces no traffic at all. The "no packets for Ns" badge
 * therefore has to come from a local clock; waiting for a message that says "still paused" would
 * wait forever.
 *
 * **Backoff resets on the first message, not on `open`.** A backend that accepts the socket and
 * immediately drops it would otherwise spin at one attempt per second forever. A message is proof
 * the connection actually works.
 */
import { liveSocketUrl } from "@/api/client";
import type { LiveMessage } from "@/api/types";
import { liveStore, reduce, type LiveStore } from "@/live/store";

/** Backoff, in ms: 1s doubling to a 10s ceiling, per #22. */
const BACKOFF_MIN_MS = 1000;
const BACKOFF_MAX_MS = 10_000;

/**
 * How long without a connected snapshot before "live" becomes "paused".
 *
 * The backend calls the game disconnected after 1 s of silence and sends a final snapshot saying so,
 * which is the normal path. This is the backstop for when that message never arrives, so it sits
 * above 1 s rather than racing it.
 */
const STALE_MS = 2000;

const TICK_MS = 500;

/** The slice of WebSocket this uses, so a test can hand it a fake without inventing a DOM. */
export interface SocketLike {
  onopen: (() => void) | null;
  onclose: (() => void) | null;
  onerror: (() => void) | null;
  onmessage: ((event: { data: string }) => void) | null;
  close(): void;
}

export interface LiveSocketOptions {
  url?: string;
  store?: LiveStore;
  createSocket?: (url: string) => SocketLike;
  now?: () => number;
}

export class LiveSocket {
  private readonly url: string;
  private readonly store: LiveStore;
  private readonly create: (url: string) => SocketLike;
  private readonly now: () => number;

  private socket: SocketLike | null = null;
  private retry: ReturnType<typeof setTimeout> | null = null;
  private ticker: ReturnType<typeof setInterval> | null = null;
  private backoff = BACKOFF_MIN_MS;
  private started = false;
  /** Set once a message arrives on the current socket, which is what resets the backoff. */
  private proven = false;

  constructor(options: LiveSocketOptions = {}) {
    this.url = options.url ?? liveSocketUrl();
    this.store = options.store ?? liveStore;
    this.create = options.createSocket ?? ((url) => new WebSocket(url) as unknown as SocketLike);
    this.now = options.now ?? (() => performance.now());
  }

  start(): void {
    if (this.started) return;
    this.started = true;
    this.ticker = setInterval(() => this.onTick(), TICK_MS);
    this.open();
  }

  stop(): void {
    this.started = false;
    if (this.retry !== null) clearTimeout(this.retry);
    if (this.ticker !== null) clearInterval(this.ticker);
    this.retry = this.ticker = null;
    this.detach();
    this.socket?.close();
    this.socket = null;
  }

  /** The delay the next reconnect would use. Exposed so a test can assert the schedule. */
  get nextDelayMs(): number {
    return this.backoff;
  }

  private open(): void {
    this.proven = false;
    const socket = this.create(this.url);
    this.socket = socket;
    socket.onmessage = (event) => this.onMessage(event.data);
    // A socket that errors also closes, so both paths land in the same place and must be idempotent.
    socket.onclose = () => this.onClose(socket);
    socket.onerror = () => this.onClose(socket);
  }

  private onMessage(data: string): void {
    if (!this.proven) {
      this.proven = true;
      this.backoff = BACKOFF_MIN_MS;
    }
    let message: LiveMessage;
    try {
      message = JSON.parse(data) as LiveMessage;
    } catch {
      // A malformed frame is not worth dropping the connection over; the next one is 33 ms away.
      return;
    }
    this.store.setState(reduce(this.store.getState(), message, this.now()));
  }

  private onClose(socket: SocketLike): void {
    // Late events from a socket we already replaced must not schedule a second reconnect.
    if (socket !== this.socket) return;
    this.detach();
    this.socket = null;
    // The last values stay on screen: what the game was doing when everything stopped is the one
    // thing worth keeping, and zeroing it would be a lie. Only the banner changes.
    this.store.setState({ status: "offline" });
    if (!this.started) return;
    this.retry = setTimeout(() => this.open(), this.backoff);
    this.backoff = Math.min(this.backoff * 2, BACKOFF_MAX_MS);
  }

  private detach(): void {
    if (!this.socket) return;
    this.socket.onmessage = this.socket.onclose = this.socket.onerror = this.socket.onopen = null;
  }

  private onTick(): void {
    const { status, lastPacketAt, staleSeconds } = this.store.getState();
    if (lastPacketAt === null || status === "offline") return;
    const elapsed = this.now() - lastPacketAt;
    const seconds = Math.floor(elapsed / 1000);
    const next: { staleSeconds?: number; status?: "paused" } = {};
    if (seconds !== staleSeconds) next.staleSeconds = seconds;
    if (status === "live" && elapsed > STALE_MS) next.status = "paused";
    if (next.staleSeconds !== undefined || next.status !== undefined) this.store.setState(next);
  }
}
