"""Live feed: snapshot contents, sending only on change, slow clients, and tracker events in order."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from concurrent.futures import Executor, Future
from datetime import datetime
from pathlib import Path
from typing import Any

from f1telemetry.live import LiveState
from f1telemetry.live_feed import FeedClient, LiveFeed, snapshot
from f1telemetry.packets import Packet
from f1telemetry.parsers import make_dispatcher
from f1telemetry.rawfile import read_records
from f1telemetry.store import SessionRecorder, SessionStore
from f1telemetry.tracker import SessionTracker

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


def test_snapshot_before_any_packet_has_every_slot_empty() -> None:
    message = snapshot(LiveState(), connected=False)
    assert message == {
        "type": "snapshot",
        "connected": False,
        "packet_format": None,
        "player_index": None,
        "packets_per_second": 0,
        "session": None,
        "lap": None,
        "telemetry": None,
        "status": None,
        "damage": None,
        "telemetry2": None,
    }


def test_snapshot_flattens_each_packet_and_rounds_float32_noise(tmp_path: Path) -> None:
    live_feed, tracker, _ = feed(tmp_path)
    feed_packets(live_feed, tracker, fixture_packets("race-2026-monza-finish"))

    message = snapshot(live_feed.state, connected=True)
    assert (message["packet_format"], message["player_index"]) == (2026, 21)
    assert message["telemetry"]["gear"] in range(-1, 9)
    assert message["status"]["ers_harvest_limit_per_lap"] is not None
    assert message["telemetry2"]["regulations_2026_applicable"] is True
    floats = [
        v for slot in ("lap", "telemetry", "status", "damage") for v in message[slot].values() if type(v) is float
    ]
    assert floats and all(round(value, 3) == value for value in floats)


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


def test_tracker_events_carry_the_session_summary(tmp_path: Path) -> None:
    live_feed, tracker, _ = feed(tmp_path)
    client = live_feed.join()
    drain(client)
    feed_packets(live_feed, tracker, fixture_packets("race-2026-monza-finish"))

    started, completed, ended = [m for m in drain(client) if m["type"] != "snapshot"]
    session_id = "20260918-231502_monza_race"
    assert started["session"]["id"] == session_id
    assert (started["session"]["track"]["name"], started["session"]["laps"]) == ("Monza", [])
    assert (completed["lap"]["number"], completed["lap"]["lap_time_ms"]) == (3, 83561)
    assert [lap["number"] for lap in completed["session"]["laps"]] == [3]
    assert (ended["reason"], ended["session"]["end_reason"], ended["session"]["id"]) == ("ended", "ended", session_id)


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


def test_leaving_stops_the_feed_for_that_client(tmp_path: Path) -> None:
    live_feed, tracker, _ = feed(tmp_path)
    staying, leaving = live_feed.join(), live_feed.join()
    drain(staying)
    drain(leaving)
    live_feed.leave(leaving)

    feed_packets(live_feed, tracker, fixture_packets("race-2026-monza-finish")[:100])
    live_feed.tick()

    assert drain(leaving) == []
    assert [m["type"] for m in drain(staying)] == ["session_started", "snapshot"]
    assert live_feed.clients == {staying}
