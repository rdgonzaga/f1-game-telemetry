"""Live feed: sending only on change, slow clients, joining mid-session, and the live delta."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from concurrent.futures import Executor, Future
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from f1telemetry.lap_data import LapData
from f1telemetry.live import LiveState
from f1telemetry.live_feed import BestLapDelta, FeedClient, LiveFeed
from f1telemetry.packets import Packet
from f1telemetry.parsers import make_dispatcher
from f1telemetry.rawfile import read_records
from f1telemetry.session import Session
from f1telemetry.store import SessionRecorder, SessionStore
from f1telemetry.tracker import (
    Lap,
    LapCompleted,
    LapReopened,
    SessionClosed,
    SessionOpened,
    SessionTracker,
    TrackedSession,
)

FIXTURES = Path(__file__).parent / "fixtures"
NOW = 5_000_000_000
STARTED = datetime(2026, 9, 18, 23, 15, 2)


class NoWrites(Executor):
    """The feed only reads the recorder's summaries; what it would write doesn't matter here."""

    def submit(self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Future[Any]:
        future: Future[Any] = Future()
        future.set_result(None)
        return future


def fixture_packets(name: str) -> list[Packet]:
    dispatcher = make_dispatcher()
    packets = (dispatcher.parse(data) for _, data in read_records(FIXTURES / f"{name}.f1raw"))
    return [packet for packet in packets if packet is not None]


def drain(client: FeedClient) -> list[dict[str, Any]]:
    """What the client's sender would send now; empty when it would keep waiting."""
    if not client._wake.is_set():
        return []
    return [json.loads(message) for message in asyncio.run(client.next_messages())]


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> int:
        return self.now


def feed(tmp_path: Path) -> tuple[LiveFeed, SessionTracker, Clock]:
    """A feed wired like the app: tracker -> recorder -> feed, with nothing written."""
    clock = Clock()
    state = LiveState()
    recorder = SessionRecorder(SessionStore(tmp_path), NoWrites(), clock=lambda: STARTED)
    live_feed = LiveFeed(state, recorder, clock)

    def on_event(event: Any) -> None:
        recorder.on_event(event)
        live_feed.on_event(event)

    return live_feed, SessionTracker(on_event), clock


def feed_packets(live_feed: LiveFeed, tracker: SessionTracker, packets: list[Packet]) -> None:
    for packet in packets:
        live_feed.state.note_datagram(NOW)
        live_feed.state.update(packet)
        tracker.update(packet)


def test_a_snapshot_is_only_sent_when_something_changed(tmp_path: Path) -> None:
    live_feed, _, clock = feed(tmp_path)
    client = live_feed.join()
    hello, first = drain(client)
    assert (hello, first["connected"]) == ({"type": "hello", "session": None}, False)

    live_feed.tick()
    assert drain(client) == []

    live_feed.state.note_datagram(clock.now)
    live_feed.tick()
    [update] = drain(client)
    assert update["connected"] is True
    live_feed.tick()
    assert drain(client) == []

    # No more packets: the next change is the connection timing out.
    clock.now += 2_000_000_000
    live_feed.tick()
    [update] = drain(client)
    assert update["connected"] is False


def test_a_slow_client_gets_every_event_but_only_the_newest_snapshot(tmp_path: Path) -> None:
    live_feed, tracker, _ = feed(tmp_path)
    client = live_feed.join()
    drain(client)

    # Nothing is sent while the packets arrive, as if the client's socket were stuck.
    for packet in fixture_packets("race-2026-monza-finish"):
        feed_packets(live_feed, tracker, [packet])
        live_feed.tick()

    messages = drain(client)
    assert [m["type"] for m in messages] == ["session_started", "lap_completed", "session_ended", "snapshot"]
    assert messages[-1]["connected"] is True


def test_a_client_joining_mid_session_is_told_about_it(tmp_path: Path) -> None:
    live_feed, tracker, _ = feed(tmp_path)
    packets = fixture_packets("race-2026-monza-finish")
    feed_packets(live_feed, tracker, packets[:100])
    assert tracker.session is not None

    hello, first = drain(live_feed.join())
    assert hello["session"]["id"] == "20260918-231502_monza_race"
    assert first["type"] == "snapshot"

    feed_packets(live_feed, tracker, packets[100:])
    assert tracker.session is None
    hello, _ = drain(live_feed.join())
    assert hello["session"] is None


SESSION_INFO = next(p.data for p in fixture_packets("race-2026-monza-finish") if isinstance(p.data, Session))
LAP_DATA = next(p.data for p in fixture_packets("race-2026-monza-finish") if isinstance(p.data, LapData))


def driving(distance: float, lap_time_ms: int) -> LapData:
    """The player car at a point on the lap, with everything else as the game last sent it."""
    return LAP_DATA._replace(lap_distance=distance, current_lap_time_ms=lap_time_ms)


def steady_lap(number: int, speed_ms: float, *, invalid: bool = False, partial: bool = False) -> Lap:
    """A lap driven at a constant speed over 1000 m, so its time at any distance is known exactly."""
    lap = Lap(number, 0.0, lap_time_ms=round(1000 / speed_ms * 1000), invalid=invalid, partial=partial)
    for index in range(101):
        distance = index * 10.0
        lap.samples.session_time.append(distance / speed_ms)
        lap.samples.lap_distance.append(distance)
        lap.samples.lap_time_ms.append(round(distance / speed_ms * 1000))
    return lap


def session_with(*laps: Lap) -> TrackedSession:
    return TrackedSession(0xABC, 2026, 21, SESSION_INFO, list(laps))


def test_there_is_no_delta_until_the_session_has_a_complete_valid_lap() -> None:
    delta = BestLapDelta()
    assert delta.value(driving(500.0, 10_000)) is None

    fast = steady_lap(1, 50.0, invalid=True)
    delta.on_event(LapCompleted(session_with(fast), fast))
    assert delta.value(driving(500.0, 10_000)) is None

    partial = steady_lap(2, 50.0, partial=True)
    delta.on_event(LapCompleted(session_with(partial), partial))
    assert delta.value(driving(500.0, 10_000)) is None


def test_the_delta_is_the_gap_to_the_session_best_at_the_car_s_distance() -> None:
    delta = BestLapDelta()
    best = steady_lap(1, 50.0)  # 10 s at the 500 m mark
    delta.on_event(LapCompleted(session_with(best), best))

    assert delta.value(driving(500.0, 10_000)) == {"best_lap": 1, "seconds": 0.0}
    assert delta.value(driving(500.0, 10_400)) == {"best_lap": 1, "seconds": 0.4}
    assert delta.value(driving(250.0, 4_750)) == {"best_lap": 1, "seconds": -0.25}


def test_a_quicker_lap_becomes_the_reference() -> None:
    delta = BestLapDelta()
    slow, quick = steady_lap(1, 40.0), steady_lap(2, 50.0)
    delta.on_event(LapCompleted(session_with(slow), slow))
    assert delta.value(driving(500.0, 12_500)) == {"best_lap": 1, "seconds": 0.0}

    delta.on_event(LapCompleted(session_with(slow, quick), quick))
    assert delta.value(driving(500.0, 12_500)) == {"best_lap": 2, "seconds": 2.5}


def test_reopening_the_best_lap_takes_it_back_as_the_reference() -> None:
    delta = BestLapDelta()
    best = steady_lap(1, 50.0)
    delta.on_event(LapCompleted(session_with(best), best))

    # A flashback past the line: the tracker pops the lap and reports it as open again.
    delta.on_event(LapReopened(session_with(), best))
    assert delta.value(driving(500.0, 10_400)) is None


def test_the_delta_stops_at_a_session_boundary() -> None:
    delta = BestLapDelta()
    best = steady_lap(1, 50.0)
    delta.on_event(LapCompleted(session_with(best), best))

    delta.on_event(SessionClosed(session_with(best), "ended"))
    assert delta.value(driving(500.0, 10_400)) is None

    delta.on_event(LapCompleted(session_with(best), best))
    delta.on_event(SessionOpened(session_with()))
    assert delta.value(driving(500.0, 10_400)) is None


def test_there_is_no_delta_where_the_reference_lap_does_not_reach() -> None:
    delta = BestLapDelta()
    best = steady_lap(1, 50.0)
    delta.on_event(LapCompleted(session_with(best), best))

    assert delta.value(driving(1500.0, 30_000)) is None  # a longer track than the reference covered
    assert delta.value(driving(-20.0, 0)) is None  # before the line


def test_the_snapshot_carries_the_delta(tmp_path: Path) -> None:
    live_feed, _, _ = feed(tmp_path)
    best = steady_lap(1, 50.0)
    live_feed.on_event(LapCompleted(session_with(best), best))
    live_feed.state.lap = driving(500.0, 10_400)

    [update] = [m for m in drain(live_feed.join()) if m["type"] == "snapshot"]
    assert update["delta"] == {"best_lap": 1, "seconds": 0.4}
    assert update["lap"]["lap_distance"] == pytest.approx(500.0)
