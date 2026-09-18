"""Local session store: one folder per session with a `session.json` summary and a columnar JSON file per lap.

    <data dir>/sessions/20260918-231502_jeddah_race/session.json
    <data dir>/sessions/20260918-231502_jeddah_race/laps/lap_03.json

`SessionRecorder` turns tracker events into writes on a single background thread, so disk I/O never blocks the
event loop and writes land in order. Each file is written to a temporary name and renamed into place, so a crash
never leaves half a file. `SessionStore` lists, loads and deletes what was saved; its methods block, so async
callers run them in a thread.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sys
from collections.abc import Callable
from concurrent.futures import Executor, Future, ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

from f1telemetry.names import formula_name, session_type_name, track_name
from f1telemetry.tracker import (
    Lap,
    LapCompleted,
    LapReopened,
    SessionClosed,
    SessionOpened,
    TrackedSession,
    TrackerEvent,
)

log = logging.getLogger(__name__)

FILE_VERSION = 1
SESSION_FILE = "session.json"
LAPS_DIR = "laps"
# Folder names are the session ids the API takes, so anything else is refused before it touches the disk.
SESSION_ID = re.compile(r"^\d{8}-\d{6}_[a-z0-9-]+_[a-z0-9-]+(-\d+)?$")

type Json = dict[str, Any]


def default_data_dir() -> Path:
    """`%LOCALAPPDATA%\\F1Telemetry` on Windows, the XDG data directory elsewhere."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "F1Telemetry"
    xdg = os.environ.get("XDG_DATA_HOME")
    return (Path(xdg) if xdg else Path.home() / ".local" / "share") / "f1telemetry"


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "unknown"


def lap_file_name(number: int) -> str:
    return f"lap_{number:02d}.json"


def lap_summary(lap: Lap) -> Json:
    return {
        "number": lap.number,
        "lap_time_ms": lap.lap_time_ms,
        "invalid": lap.invalid,
        "partial": lap.partial,
        "samples": len(lap.samples),
    }


def best_lap_number(laps: list[Lap]) -> int | None:
    """Fastest lap that is valid and complete; None when there is none."""
    counted = [lap for lap in laps if not lap.invalid and not lap.partial and lap.lap_time_ms > 0]
    return min(counted, key=lambda lap: lap.lap_time_ms).number if counted else None


def session_document(
    session_id: str,
    session: TrackedSession,
    started_at: datetime,
    ended_at: datetime | None = None,
    end_reason: str | None = None,
) -> Json:
    info = session.info
    return {
        "version": FILE_VERSION,
        "id": session_id,
        "uid": f"{session.uid:016x}",
        "started_at": started_at.isoformat(timespec="seconds"),
        "ended_at": ended_at.isoformat(timespec="seconds") if ended_at else None,
        "end_reason": end_reason,
        "packet_format": session.packet_format,
        "player_index": session.player_index,
        "track": {"id": info.track_id, "name": track_name(info.track_id), "length": info.track_length},
        "session_type": {"id": info.session_type, "name": session_type_name(info.session_type)},
        "formula": {"id": info.formula, "name": formula_name(info.formula)},
        "total_laps": info.total_laps,
        "best_lap": best_lap_number(session.laps),
        "laps": [lap_summary(lap) for lap in session.laps],
    }


def _rounded(values: Any, digits: int) -> list[float]:
    # Samples are float32, so without rounding 0.3 comes out as 0.30000001192092896 and files triple in size.
    return [round(value, digits) for value in values]


def lap_document(lap: Lap) -> Json:
    samples = lap.samples
    return {
        "version": FILE_VERSION,
        **lap_summary(lap),
        "columns": {
            "session_time": _rounded(samples.session_time, 3),  # seconds
            "lap_distance": _rounded(samples.lap_distance, 1),  # metres
            "lap_time_ms": samples.lap_time_ms.tolist(),
            "speed": samples.speed.tolist(),  # km/h
            "throttle": _rounded(samples.throttle, 3),  # 0-1
            "brake": _rounded(samples.brake, 3),  # 0-1
            "steer": _rounded(samples.steer, 3),  # -1 left to 1 right
            "gear": samples.gear.tolist(),
            "engine_rpm": samples.engine_rpm.tolist(),
            "drs": samples.drs.tolist(),
        },
    }


def base_session_id(session: TrackedSession, started_at: datetime) -> str:
    info = session.info
    track, session_type = slug(track_name(info.track_id)), slug(session_type_name(info.session_type))
    return f"{started_at:%Y%m%d-%H%M%S}_{track}_{session_type}"


def write_json_atomic(path: Path, document: Json) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8") as file:
        json.dump(document, file, separators=(",", ":"))
    os.replace(temp, path)


class SessionStore:
    """Reads and deletes saved sessions. Every method touches the disk, so call them off the event loop."""

    def __init__(self, data_dir: Path) -> None:
        self.root = data_dir / "sessions"

    def session_dir(self, session_id: str) -> Path:
        if not SESSION_ID.match(session_id):
            raise KeyError(session_id)
        return self.root / session_id

    def list_sessions(self) -> list[Json]:
        """Saved session summaries, newest first. Unreadable folders are skipped."""
        if not self.root.is_dir():
            return []
        sessions = []
        for folder in sorted(self.root.iterdir(), reverse=True):
            if not SESSION_ID.match(folder.name):
                continue
            try:
                sessions.append(_read(folder / SESSION_FILE))
            except (OSError, ValueError):
                log.warning("skipping unreadable session %s", folder.name)
        return sessions

    def load_session(self, session_id: str) -> Json:
        """Raises KeyError when there is no such session."""
        return _read_or_key_error(self.session_dir(session_id) / SESSION_FILE, session_id)

    def load_lap(self, session_id: str, number: int) -> Json:
        """Raises KeyError when there is no such session or lap."""
        path = self.session_dir(session_id) / LAPS_DIR / lap_file_name(number)
        return _read_or_key_error(path, f"{session_id} lap {number}")

    def delete_session(self, session_id: str) -> None:
        """Raises KeyError when there is no such session."""
        folder = self.session_dir(session_id)
        if not folder.is_dir():
            raise KeyError(session_id)
        shutil.rmtree(folder)


def _read(path: Path) -> Json:
    with path.open(encoding="utf-8") as file:
        document: Json = json.load(file)
    return document


def _read_or_key_error(path: Path, what: str) -> Json:
    try:
        return _read(path)
    except FileNotFoundError:
        raise KeyError(what) from None


class SessionRecorder:
    """Saves what `SessionTracker` reports. Pass `on_event` as the tracker's callback; call `close()` on shutdown.

    Runs on the event loop and only builds small summaries there. Laps are handed to the writer thread as they are:
    the tracker never changes a completed lap, so the thread can read its samples safely. Nothing is written until a
    session's first lap completes, so a restart or a crash before then leaves nothing behind.
    """

    def __init__(
        self,
        store: SessionStore,
        executor: Executor | None = None,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.store = store
        self._executor = executor or ThreadPoolExecutor(max_workers=1, thread_name_prefix="session-store")
        self._clock = clock
        self._session_id: str | None = None
        self._written = False  # whether the current session has a folder on disk yet
        self._started_at = clock()
        # Ids are timestamped to the second, so only a restart within the same second can repeat one.
        self._used_ids: set[str] = set()

    def on_event(self, event: TrackerEvent) -> None:
        if isinstance(event, SessionOpened):
            self._started_at = self._clock()
            self._session_id = self._new_session_id(event.session)
            self._written = False
            return
        session_id = self._session_id
        if session_id is None:
            return
        folder = self.store.root / session_id
        if isinstance(event, LapCompleted):
            lap = event.lap
            self._submit(_write_lap, folder / LAPS_DIR / lap_file_name(lap.number), lap)
            self._save_session(event.session)
            self._written = True
        elif isinstance(event, LapReopened) and self._written:
            self._submit(_unlink, folder / LAPS_DIR / lap_file_name(event.lap.number))
            self._save_session(event.session)
        elif isinstance(event, SessionClosed):
            self._session_id = None
            if event.session.laps:
                self._save_session(event.session, session_id, self._clock(), event.reason)
            elif self._written:
                # Its only laps were undone by flashbacks, so there is nothing left to review.
                self._submit(_remove_dir, folder)

    @property
    def active_session_id(self) -> str | None:
        """The session being recorded, which must not be deleted while it is still being written."""
        return self._session_id

    def close(self) -> None:
        """Wait for pending writes to finish."""
        self._executor.shutdown(wait=True)

    def _new_session_id(self, session: TrackedSession) -> str:
        base = session_id = base_session_id(session, self._started_at)
        n = 1
        while session_id in self._used_ids:
            n += 1
            session_id = f"{base}-{n}"
        self._used_ids.add(session_id)
        return session_id

    def _save_session(
        self,
        session: TrackedSession,
        session_id: str | None = None,
        ended_at: datetime | None = None,
        end_reason: str | None = None,
    ) -> None:
        session_id = session_id or self._session_id
        assert session_id is not None
        document = session_document(session_id, session, self._started_at, ended_at, end_reason)
        self._submit(write_json_atomic, self.store.root / session_id / SESSION_FILE, document)

    def _submit(self, fn: Callable[..., object], *args: object) -> None:
        self._executor.submit(fn, *args).add_done_callback(_log_failure)


def _write_lap(path: Path, lap: Lap) -> None:
    # Built here on the writer thread: rounding thousands of samples would otherwise stall the event loop.
    write_json_atomic(path, lap_document(lap))


def _remove_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def _unlink(path: Path) -> None:
    path.unlink(missing_ok=True)


def _log_failure(future: Future[object]) -> None:
    error = future.exception()
    if error is not None:
        log.error("saving session data failed: %s", error, exc_info=error)
