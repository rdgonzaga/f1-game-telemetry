"""The `/ws/live` feed: snapshots of `LiveState` at 30 Hz, plus session and lap events as they happen.

Every tick encodes one snapshot and hands the same text to every client. Each client sends from its own task (the
WebSocket endpoint) and only ever holds the newest snapshot, so a slow client skips frames instead of holding up the
others or UDP intake. Events queue and are never skipped.

Messages are JSON objects with a `type`:
- `hello`: on connect, with the open `session` or null.
- `snapshot`: `connected`, `packet_format`, `player_index`, `packets_per_second`, then the latest packet of each
  kind (`session`, `lap`, `telemetry`, `status`, `damage`, `telemetry2`) as an object, or null until one arrives,
  and `delta` (`best_lap` and `seconds` against the session's best lap), null until there is one to compare with.
- `session_started`, `lap_completed` (with `lap`), `lap_reopened` (with `lap_number`), `session_ended` (with
  `reason`): each carries the whole `session` summary in the saved `session.json` shape, so a client just replaces
  what it holds.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from collections.abc import Callable
from typing import NamedTuple

from f1telemetry.compare import LapReference
from f1telemetry.lap_data import LapData
from f1telemetry.live import PACKET_SLOTS, LiveState
from f1telemetry.store import Json, SessionRecorder, best_lap_number, lap_summary
from f1telemetry.tracker import Lap, LapCompleted, LapReopened, SessionClosed, SessionOpened, TrackerEvent

SNAPSHOT_HZ = 30
SLOTS = tuple(PACKET_SLOTS.values())
# Most floats are float32, which print as 0.30000001192092896; three decimals is finer than any gauge shows.
FLOAT_DIGITS = 3


def encode(message: Json) -> str:
    return json.dumps(message, separators=(",", ":"))


def _fields(payload: NamedTuple | None) -> Json | None:
    if payload is None:
        return None
    return {
        name: round(value, FLOAT_DIGITS) if type(value) is float else value
        for name, value in zip(payload._fields, payload, strict=True)
    }


def snapshot(state: LiveState, connected: bool, delta: Json | None = None) -> Json:
    message: Json = {
        "type": "snapshot",
        "connected": connected,
        "packet_format": state.packet_format,
        "player_index": state.player_index,
        "packets_per_second": state.packets_per_second,
    }
    for slot in SLOTS:
        message[slot] = _fields(getattr(state, slot))
    message["delta"] = delta
    return message


class BestLapDelta:
    """The gap to the session's best lap at the car's current distance.

    The reference is rebuilt only when the best lap changes, which is at most once per completed lap; looking the
    gap up is then an array index, cheap enough for every snapshot. A flashback that reopens the best lap drops it,
    since the tracker takes it back out of the session.
    """

    __slots__ = ("_lap", "reference")

    def __init__(self) -> None:
        self.reference: LapReference | None = None
        self._lap: Lap | None = None  # the lap the reference was built from, to notice a re-driven lap number

    def on_event(self, event: TrackerEvent) -> None:
        if isinstance(event, SessionOpened | SessionClosed):
            self.reference, self._lap = None, None
        elif isinstance(event, LapCompleted | LapReopened):
            self._rebuild(event.session.laps)

    def _rebuild(self, laps: list[Lap]) -> None:
        number = best_lap_number(laps)  # None when no lap counts yet, which no lap number matches
        best = next((lap for lap in laps if lap.number == number), None)
        # By identity: a lap re-driven after a flashback keeps its number but is a different lap.
        if best is self._lap:
            return
        self._lap = best
        if best is None:
            self.reference = None
        else:
            self.reference = LapReference.build(best.number, best.samples.lap_distance, best.samples.lap_time_ms)

    def value(self, lap: LapData | None) -> Json | None:
        """`best_lap` and `seconds` (positive = slower than the best lap), or None where there is nothing to compare."""
        reference = self.reference
        if reference is None or lap is None or lap.lap_distance < 0:
            return None
        reference_ms = reference.time_at(lap.lap_distance)
        if reference_ms is None:
            return None
        return {
            "best_lap": reference.number,
            "seconds": round((lap.current_lap_time_ms - reference_ms) / 1000, FLOAT_DIGITS),
        }


class FeedClient:
    """One connected dashboard: queued events and the newest snapshot, waiting to be sent."""

    __slots__ = ("_events", "_snapshot", "_wake")

    def __init__(self) -> None:
        self._events: deque[str] = deque()
        self._snapshot: str | None = None
        self._wake = asyncio.Event()

    def push_event(self, message: str) -> None:
        self._events.append(message)
        self._wake.set()

    def offer_snapshot(self, message: str) -> None:
        """Replace any snapshot not yet sent: only the newest is worth sending."""
        self._snapshot = message
        self._wake.set()

    async def next_messages(self) -> list[str]:
        """Wait for something to send; events come first, in order, then the snapshot."""
        await self._wake.wait()
        self._wake.clear()
        messages = list(self._events)
        self._events.clear()
        if self._snapshot is not None:
            messages.append(self._snapshot)
            self._snapshot = None
        return messages


class LiveFeed:
    """Fans live state and tracker events out to clients. Call `on_event` after the recorder has seen the event."""

    def __init__(
        self,
        state: LiveState,
        recorder: SessionRecorder,
        clock: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        self.state = state
        self.recorder = recorder
        self.delta = BestLapDelta()
        self._clock = clock
        self.clients: set[FeedClient] = set()
        self._has_clients = asyncio.Event()
        self._session: Json | None = None  # the open session's summary, for clients that connect mid-session
        # What the last snapshot showed; an unchanged picture isn't sent again (the game sends nothing while paused).
        self._sent_packets = 0  # matches a fresh LiveState, so an idle start sends nothing twice
        self._sent_connected = False

    def join(self) -> FeedClient:
        client = FeedClient()
        client.push_event(encode({"type": "hello", "session": self._session}))
        # Right away, not at the next change: the game may be paused.
        client.offer_snapshot(encode(self._snapshot()))
        self.clients.add(client)
        self._has_clients.set()
        return client

    def leave(self, client: FeedClient) -> None:
        self.clients.discard(client)
        if not self.clients:
            self._has_clients.clear()

    def on_event(self, event: TrackerEvent) -> None:
        self.delta.on_event(event)
        document = self.recorder.document
        message: Json
        if isinstance(event, SessionOpened):
            message = {"type": "session_started", "session": document}
        elif isinstance(event, LapCompleted):
            message = {"type": "lap_completed", "lap": lap_summary(event.lap), "session": document}
        elif isinstance(event, LapReopened):
            message = {"type": "lap_reopened", "lap_number": event.lap.number, "session": document}
        elif isinstance(event, SessionClosed):
            message = {"type": "session_ended", "reason": event.reason, "session": document}
        self._session = None if isinstance(event, SessionClosed) else document
        if self.clients:
            text = encode(message)
            for client in self.clients:
                client.push_event(text)

    def tick(self) -> None:
        """Send a snapshot to every client if anything changed since the last one."""
        if not self.clients:
            return
        connected = self.state.connected(self._clock())
        if self.state.packets_seen == self._sent_packets and connected == self._sent_connected:
            return
        self._sent_packets = self.state.packets_seen
        self._sent_connected = connected
        text = encode(self._snapshot(connected))
        for client in self.clients:
            client.offer_snapshot(text)

    def _snapshot(self, connected: bool | None = None) -> Json:
        if connected is None:
            connected = self.state.connected(self._clock())
        return snapshot(self.state, connected, self.delta.value(self.state.lap))

    async def run(self) -> None:
        """Tick at `SNAPSHOT_HZ` while any client is connected; sleeps without waking while none is."""
        loop = asyncio.get_running_loop()
        period = 1 / SNAPSHOT_HZ
        next_tick = loop.time()
        while True:
            if not self.clients:
                await self._has_clients.wait()
                next_tick = loop.time()
            self.tick()
            # Scheduled from the previous tick, not from now, so the rate holds even with a coarse timer.
            next_tick += period
            delay = next_tick - loop.time()
            if delay < -period:
                # Fell well behind (a stall); start again from now instead of sending a burst to catch up.
                next_tick = loop.time()
                delay = 0
            await asyncio.sleep(max(delay, 0))
