"""Session store: recorder writes from tracker events, and listing, loading and deleting saved sessions."""

from __future__ import annotations

import json
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
    best_lap_number,
    default_data_dir,
    lap_document,
    write_json_atomic,
)
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


def make_lap(number: int, lap_time_ms: int, *, invalid: bool = False, partial: bool = False) -> Lap:
    lap = Lap(number, 10.0, lap_time_ms=lap_time_ms, invalid=invalid, partial=partial)
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


def test_real_finish_is_saved_off_the_calling_thread(tmp_path: Path) -> None:
    rec, store, executor = recorder(tmp_path)
    tracker = SessionTracker(rec.on_event)
    for packet in fixture_packets("race-2026-monza-finish"):
        tracker.update(packet)

    # Every write is still queued for the writer thread.
    assert not store.root.exists()
    executor.run()

    [saved] = store.list_sessions()
    assert saved["id"] == "20260918-231502_monza_race"
    assert (saved["track"]["name"], saved["session_type"]["name"], saved["formula"]["name"]) == (
        "Monza",
        "Race",
        "F1 26",
    )
    assert (saved["end_reason"], saved["ended_at"]) == ("ended", "2026-09-18T23:15:02")
    assert [(lap["number"], lap["lap_time_ms"], lap["partial"]) for lap in saved["laps"]] == [(3, 83561, True)]
    # The only lap joined mid-way, so there is no best lap.
    assert saved["best_lap"] is None

    lap = store.load_lap(saved["id"], 3)
    columns = lap["columns"]
    assert {len(column) for column in columns.values()} == {saved["laps"][0]["samples"]}
    assert columns["lap_time_ms"][-1] <= 83561


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


def test_nothing_is_written_before_the_first_lap(tmp_path: Path) -> None:
    rec, store, executor = recorder(tmp_path)
    session = make_session()
    rec.on_event(SessionOpened(session))
    rec.on_event(SessionClosed(session, "new session"))

    # A crash any time before the first lap would leave nothing on disk either.
    assert executor.queue == []
    assert store.list_sessions() == []


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


def test_active_session_id_follows_the_open_session(tmp_path: Path) -> None:
    rec, _, _ = recorder(tmp_path)
    session = make_session()
    assert rec.active_session_id is None

    rec.on_event(SessionOpened(session))
    assert rec.active_session_id == "20260918-231502_monza_race"

    rec.on_event(SessionClosed(session, "ended"))
    assert rec.active_session_id is None


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


def test_list_is_newest_first_and_skips_unreadable_folders(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    for session_id in ("20260101-120000_monza_race", "20260301-120000_jeddah_race"):
        write_json_atomic(store.root / session_id / "session.json", {"id": session_id})
    (store.root / "20260201-120000_broken_race").mkdir()
    (store.root / "notes").mkdir()

    assert [s["id"] for s in store.list_sessions()] == ["20260301-120000_jeddah_race", "20260101-120000_monza_race"]
    assert SessionStore(tmp_path / "missing").list_sessions() == []


def test_load_and_delete(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    session_id = "20260101-120000_monza_race"
    write_json_atomic(store.root / session_id / "session.json", {"id": session_id})

    assert store.load_session(session_id) == {"id": session_id}
    with pytest.raises(KeyError):
        store.load_lap(session_id, 1)

    store.delete_session(session_id)
    assert not (store.root / session_id).exists()
    with pytest.raises(KeyError):
        store.load_session(session_id)
    with pytest.raises(KeyError):
        store.delete_session(session_id)


@pytest.mark.parametrize("session_id", ["..", "../../etc", "20260101-120000_monza_race/../x", "", "a b"])
def test_ids_outside_the_naming_scheme_are_refused(tmp_path: Path, session_id: str) -> None:
    store = SessionStore(tmp_path)
    for call in (store.load_session, store.delete_session, lambda i: store.load_lap(i, 1)):
        with pytest.raises(KeyError):
            call(session_id)


def test_atomic_write_replaces_the_file_and_leaves_no_temp(tmp_path: Path) -> None:
    path = tmp_path / "a" / "session.json"
    write_json_atomic(path, {"n": 1})
    write_json_atomic(path, {"n": 2})

    assert json.loads(path.read_text(encoding="utf-8")) == {"n": 2}
    assert [p.name for p in path.parent.iterdir()] == ["session.json"]


def test_lap_document_rounds_float32_noise() -> None:
    columns = lap_document(make_lap(1, 90_000))["columns"]

    assert columns["throttle"] == [0.3, 0.3, 0.3]
    assert columns["steer"] == [-0.1, -0.1, -0.1]
    assert columns["lap_distance"] == [0.0, 100.0, 200.0]
    assert columns["session_time"] == [10.0, 10.017, 10.033]


def test_best_lap_skips_invalid_and_partial_laps() -> None:
    laps = [
        make_lap(1, 85_000, partial=True),
        make_lap(2, 86_000, invalid=True),
        make_lap(3, 90_000),
        make_lap(4, 89_000),
    ]
    assert best_lap_number(laps) == 4
    assert best_lap_number(laps[:2]) is None


def test_default_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert default_data_dir() == tmp_path / "F1Telemetry"

    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert default_data_dir() == tmp_path / "xdg" / "f1telemetry"
