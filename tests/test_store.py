"""Session store: recorder writes from tracker events, and listing, loading and deleting saved sessions."""

from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import Executor, Future
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from f1telemetry.packets import Packet
from f1telemetry.parsers import make_dispatcher
from f1telemetry.rawfile import read_records
from f1telemetry.session import Session
from f1telemetry.store import (
    SessionRecorder,
    SessionStore,
    write_json_atomic,
)
from f1telemetry.tracker import (
    Lap,
    LapCompleted,
    LapReopened,
    SessionClosed,
    SessionOpened,
    TrackedSession,
)

FIXTURES = Path(__file__).parent / "fixtures"
STARTED = datetime(2026, 9, 18, 23, 15, 2)


class QueuedExecutor(Executor):
    """Holds submitted writes until `run()`, so tests can see that nothing touches the disk on the caller's thread."""

    def __init__(self) -> None:
        self.queue: list[tuple[Future[Any], Callable[..., Any], tuple[Any, ...]]] = []

    def submit(self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Future[Any]:
        future: Future[Any] = Future()
        self.queue.append((future, fn, args))
        return future

    def run(self) -> None:
        while self.queue:
            future, fn, args = self.queue.pop(0)
            future.set_result(fn(*args))


def fixture_packets(name: str) -> list[Packet]:
    dispatcher = make_dispatcher()
    packets = (dispatcher.parse(data) for _, data in read_records(FIXTURES / f"{name}.f1raw"))
    return [packet for packet in packets if packet is not None]


SESSION_INFO = next(p.data for p in fixture_packets("race-2026-monza-finish") if isinstance(p.data, Session))


def make_session(uid: int = 0xABC) -> TrackedSession:
    return TrackedSession(uid, 2026, 21, SESSION_INFO)


def make_lap(number: int, lap_time_ms: int) -> Lap:
    lap = Lap(number, 10.0, lap_time_ms=lap_time_ms)
    samples = lap.samples
    for i in range(3):
        samples.session_time.append(10.0 + i / 60)
        samples.lap_distance.append(100.0 * i)
        samples.lap_time_ms.append(16 * i)
        samples.speed.append(250 + i)
        samples.throttle.append(0.3)
        samples.brake.append(0.0)
        samples.steer.append(-0.1)
        samples.gear.append(7)
        samples.engine_rpm.append(11_000)
        samples.drs.append(1)
    return lap


def recorder(tmp_path: Path) -> tuple[SessionRecorder, SessionStore, QueuedExecutor]:
    store = SessionStore(tmp_path)
    executor = QueuedExecutor()
    return SessionRecorder(store, executor, clock=lambda: STARTED), store, executor


def test_recorder_writes_on_a_background_thread(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    threads: set[int] = set()

    def spy(path: Path, document: dict[str, Any]) -> None:
        threads.add(threading.get_ident())
        write_json_atomic(path, document)

    monkeypatch.setattr("f1telemetry.store.write_json_atomic", spy)
    store = SessionStore(tmp_path)
    rec = SessionRecorder(store, clock=lambda: STARTED)
    session = make_session()
    rec.on_event(SessionOpened(session))
    session.laps.append(make_lap(1, 90_000))
    rec.on_event(LapCompleted(session, session.laps[0]))
    rec.on_event(SessionClosed(session, "ended"))
    rec.close()

    assert threads and threading.get_ident() not in threads
    assert store.load_session("20260918-231502_monza_race")["laps"][0]["lap_time_ms"] == 90_000


def test_reopened_lap_is_removed_until_it_completes_again(tmp_path: Path) -> None:
    rec, store, executor = recorder(tmp_path)
    session = make_session()
    rec.on_event(SessionOpened(session))
    first = make_lap(6, 96_959)
    session.laps.append(first)
    rec.on_event(LapCompleted(session, first))
    executor.run()
    session_id = store.list_sessions()[0]["id"]
    assert store.load_lap(session_id, 6)["lap_time_ms"] == 96_959

    session.laps.pop()
    rec.on_event(LapReopened(session, first.reopened()))
    executor.run()
    assert store.load_session(session_id)["laps"] == []
    with pytest.raises(KeyError):
        store.load_lap(session_id, 6)

    again = make_lap(6, 97_495)
    session.laps.append(again)
    rec.on_event(LapCompleted(session, again))
    executor.run()
    assert store.load_lap(session_id, 6)["lap_time_ms"] == 97_495


def test_session_whose_only_lap_was_undone_is_removed(tmp_path: Path) -> None:
    rec, store, executor = recorder(tmp_path)
    session = make_session()
    rec.on_event(SessionOpened(session))
    lap = make_lap(1, 90_000)
    session.laps.append(lap)
    rec.on_event(LapCompleted(session, lap))
    session.laps.pop()
    rec.on_event(LapReopened(session, lap.reopened()))
    rec.on_event(SessionClosed(session, "shutdown"))
    executor.run()

    assert store.list_sessions() == []
    assert list(store.root.iterdir()) == []


def test_sessions_opened_in_the_same_second_get_distinct_ids(tmp_path: Path) -> None:
    rec, store, executor = recorder(tmp_path)
    for uid in (1, 2):
        session = make_session(uid)
        session.laps.append(make_lap(1, 90_000))
        rec.on_event(SessionOpened(session))
        rec.on_event(LapCompleted(session, session.laps[0]))
        rec.on_event(SessionClosed(session, "ended"))
    executor.run()

    assert [s["id"] for s in store.list_sessions()] == [
        "20260918-231502_monza_race-2",
        "20260918-231502_monza_race",
    ]


def test_list_skips_unreadable_folders(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    write_json_atomic(store.root / "20260101-120000_monza_race" / "session.json", {"id": "20260101-120000_monza_race"})
    (store.root / "20260201-120000_broken_race").mkdir()
    (store.root / "notes").mkdir()

    assert [s["id"] for s in store.list_sessions()] == ["20260101-120000_monza_race"]


@pytest.mark.parametrize("session_id", ["..", "../../etc", "20260101-120000_monza_race/../x", "", "a b"])
def test_ids_outside_the_naming_scheme_are_refused(tmp_path: Path, session_id: str) -> None:
    store = SessionStore(tmp_path)
    for call in (store.load_session, store.delete_session, lambda i: store.load_lap(i, 1)):
        with pytest.raises(KeyError):
            call(session_id)


def test_recorder_document_follows_the_session(tmp_path: Path) -> None:
    rec, _, executor = recorder(tmp_path)
    session = make_session()
    assert rec.document is None

    rec.on_event(SessionOpened(session))
    assert rec.document is not None
    assert (rec.document["id"], rec.document["laps"], rec.document["ended_at"]) == (
        "20260918-231502_monza_race",
        [],
        None,
    )

    lap = make_lap(1, 90_000)
    session.laps.append(lap)
    rec.on_event(LapCompleted(session, lap))
    assert [lap["number"] for lap in rec.document["laps"]] == [1]

    session.laps.pop()
    rec.on_event(LapReopened(session, lap.reopened()))
    assert rec.document["laps"] == []

    rec.on_event(SessionClosed(session, "shutdown"))
    # Kept after the close, now with its end, even though nothing is saved for a session without laps.
    assert (rec.document["end_reason"], rec.document["ended_at"]) == ("shutdown", "2026-09-18T23:15:02")
    executor.run()
    assert SessionStore(tmp_path).list_sessions() == []


def test_delete_waits_for_writes_still_pending(tmp_path: Path) -> None:
    rec, store, executor = recorder(tmp_path)
    session = make_session()
    rec.on_event(SessionOpened(session))
    session.laps.append(make_lap(1, 90_000))
    rec.on_event(LapCompleted(session, session.laps[0]))
    rec.on_event(SessionClosed(session, "ended"))

    # The session's files are still queued; deleting now must not have them written back afterwards.
    deleted = rec.delete("20260918-231502_monza_race")
    executor.run()

    assert deleted.done() and deleted.exception() is None
    assert store.list_sessions() == []
    assert list(store.root.iterdir()) == []
