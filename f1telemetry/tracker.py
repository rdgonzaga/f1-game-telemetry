"""Session and lap tracking: splits the parsed packet stream into sessions and laps, and undoes flashbacks.

Rules come from real F1 25 recordings (see docs/udp-spec.md):
- A session opens on the first Session packet of a new `sessionUID`. Skipped sessions get a UID but only send
  events, so a UID alone isn't a session. UID 0 (menus) is ignored.
- A session closes on SEND or a UID change. There is no idle timeout: the game sends nothing while paused, often for
  minutes, so silence doesn't mean the session is over. Call `close()` on shutdown.
- A lap closes when `currentLapNum` increments, or when `lastLapTimeInMS` changes without it (the chequered flag).
  The flag comes about 0.1 s before SEND, which a 20 Hz or slower send rate can miss in LapData, so a lap still open
  when the session closes takes its time from the player's SessionHistory if that lists it as finished.
- A flashback rewinds `sessionTime` to its target, so samples after the target are dropped, and a lap that closed
  after the target is reopened as a copy: a completed lap never changes once reported, so it can be saved off the
  event loop. The game can resume slightly before the target, so any sample that doesn't move forward in time also
  drops the samples it overlaps.
- Out-lap samples are dropped when a flying lap starts, since practice and qualifying keep the lap number across
  the out lap. A Time Trial restart keeps the lap number too: it resets the lap timer and puts the car on a run-up
  whose distance wraps at the line, and both drop the samples as well. Samples in the garage or before the start
  line (negative lap distance) are not kept.
"""

from __future__ import annotations

from array import array
from bisect import bisect_left
from collections.abc import Callable
from dataclasses import dataclass, field

from f1telemetry.car_telemetry import CarTelemetry
from f1telemetry.event import Flashback, SessionEnded
from f1telemetry.lap_data import LapData
from f1telemetry.packets import Packet, PacketId
from f1telemetry.session import Session
from f1telemetry.session_history import SessionHistory

DRIVER_GARAGE = 0
DRIVER_FLYING_LAP = 1
DRIVER_OUT_LAP = 3
# A completed lap covering less than this share of the track (joined mid-lap, out lap) is flagged partial.
PARTIAL_LAP_SHARE = 0.5
# The lap timer jitters back a few ms now and then; a Time Trial restart takes it back to about zero.
LAP_RESTART_DROP_MS = 1000


@dataclass(slots=True)
class LapSamples:
    """One row per CarTelemetry packet, stored as columns so a lap can be saved and charted without reshaping."""

    session_time: array[float] = field(default_factory=lambda: array("d"))
    lap_distance: array[float] = field(default_factory=lambda: array("f"))
    lap_time_ms: array[int] = field(default_factory=lambda: array("I"))
    speed: array[int] = field(default_factory=lambda: array("H"))
    throttle: array[float] = field(default_factory=lambda: array("f"))
    brake: array[float] = field(default_factory=lambda: array("f"))
    steer: array[float] = field(default_factory=lambda: array("f"))
    gear: array[int] = field(default_factory=lambda: array("b"))
    engine_rpm: array[int] = field(default_factory=lambda: array("H"))
    drs: array[int] = field(default_factory=lambda: array("B"))

    def __len__(self) -> int:
        return len(self.session_time)

    def columns(self) -> tuple[array[float] | array[int], ...]:
        return (
            self.session_time,
            self.lap_distance,
            self.lap_time_ms,
            self.speed,
            self.throttle,
            self.brake,
            self.steer,
            self.gear,
            self.engine_rpm,
            self.drs,
        )

    def truncate_from(self, session_time: float) -> None:
        """Drop every sample at or after `session_time`. Times only rise within a lap once flashbacks are undone."""
        cut = bisect_left(self.session_time, session_time)
        if cut < len(self.session_time):
            for column in self.columns():
                del column[cut:]

    def clear(self) -> None:
        for column in self.columns():
            del column[:]

    def copy(self) -> LapSamples:
        return LapSamples(
            self.session_time[:],
            self.lap_distance[:],
            self.lap_time_ms[:],
            self.speed[:],
            self.throttle[:],
            self.brake[:],
            self.steer[:],
            self.gear[:],
            self.engine_rpm[:],
            self.drs[:],
        )


@dataclass(slots=True)
class Lap:
    number: int
    start_session_time: float  # session time of the first kept sample
    end_session_time: float = 0.0
    lap_time_ms: int = 0  # the game's lastLapTimeInMS once the lap closes
    invalid: bool = False
    partial: bool = False
    start_distance: float | None = None  # first non-negative lap distance seen
    end_distance: float = 0.0
    samples: LapSamples = field(default_factory=LapSamples)

    def reopened(self) -> Lap:
        """A copy to keep driving after a flashback, leaving the completed lap as it was reported."""
        return Lap(
            self.number,
            self.start_session_time,
            invalid=self.invalid,
            start_distance=self.start_distance,
            end_distance=self.end_distance,
            samples=self.samples.copy(),
        )

    def restart(self, session_time: float) -> None:
        self.start_session_time = session_time
        self.start_distance = None
        self.samples.clear()


@dataclass(slots=True)
class TrackedSession:
    uid: int
    packet_format: int
    player_index: int
    info: Session  # the first Session packet: track, type, formula, track length
    laps: list[Lap] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SessionOpened:
    session: TrackedSession


@dataclass(frozen=True, slots=True)
class LapCompleted:
    session: TrackedSession
    lap: Lap


@dataclass(frozen=True, slots=True)
class LapReopened:
    """A flashback went back past the line, so a lap already reported as completed is being driven again."""

    session: TrackedSession
    lap: Lap


@dataclass(frozen=True, slots=True)
class SessionClosed:
    session: TrackedSession
    reason: str  # "ended" (SEND), "new session" (UID change) or "shutdown"


type TrackerEvent = SessionOpened | LapCompleted | LapReopened | SessionClosed


def _ignore(_: TrackerEvent) -> None:
    pass


class SessionTracker:
    """Feed it every parsed packet in arrival order; it calls `on_event` as sessions and laps open and close."""

    def __init__(self, on_event: Callable[[TrackerEvent], None] = _ignore) -> None:
        self.on_event = on_event
        self.session: TrackedSession | None = None
        self.lap: Lap | None = None
        # Every closed UID, not just the last: a stray packet from any of them must not reopen it.
        self._closed_uids: set[int] = set()
        self._lap_data: LapData | None = None
        # Lap number of the lap closed at the flag; a new lap only opens once the game moves past it.
        self._closed_lap_number: int | None = None
        # None means resync: the next LapData sets it without closing a lap (session start, after a flashback).
        self._last_lap_time_ms: int | None = None
        self._lap_data_time = 0.0  # session time of `_lap_data`
        self._history: tuple[int, ...] = ()  # the player's lap times from the latest SessionHistory

    def update(self, packet: Packet) -> None:
        header = packet.header
        uid = header.session_uid
        if uid == 0 or uid in self._closed_uids:
            # A session's last SessionHistory, with the final lap time, comes with UID 0 just before SEND.
            if uid == 0 and self.session is not None and isinstance(packet.data, SessionHistory):
                self._history = packet.data.lap_times_ms
            return
        session = self.session
        if session is not None and uid != session.uid:
            self._close("new session")
            session = None
        data = packet.data
        if data is None:
            return
        packet_id = header.packet_id
        if session is None:
            if packet_id == PacketId.SESSION and isinstance(data, Session):
                self._open(uid, header.packet_format, header.player_car_index, data)
            return
        if packet_id == PacketId.CAR_TELEMETRY:
            self._sample(header.session_time, data)  # type: ignore[arg-type]
        elif packet_id == PacketId.LAP_DATA:
            self._on_lap_data(header.session_time, data)  # type: ignore[arg-type]
        elif packet_id == PacketId.EVENT:
            if isinstance(data, Flashback):
                self._rewind(data.session_time)
            elif isinstance(data, SessionEnded):
                self._close("ended")
        elif packet_id == PacketId.SESSION_HISTORY:
            self._history = data.lap_times_ms  # type: ignore[attr-defined]

    def close(self, reason: str = "shutdown") -> None:
        """Close the open session, if any, dropping its unfinished lap."""
        if self.session is not None:
            self._close(reason)

    def _open(self, uid: int, packet_format: int, player_index: int, info: Session) -> None:
        self.session = TrackedSession(uid, packet_format, player_index, info)
        self.lap = None
        self._lap_data = None
        self._closed_lap_number = None
        self._last_lap_time_ms = None
        self._history = ()
        self.on_event(SessionOpened(self.session))

    def _close(self, reason: str) -> None:
        session = self.session
        assert session is not None
        lap = self.lap
        if lap is not None and lap.number <= len(self._history) and self._history[lap.number - 1]:
            self._complete(lap, self._history[lap.number - 1], self._lap_data_time)
        self._closed_uids.add(session.uid)
        self.session = None
        self.lap = None
        self._lap_data = None
        self.on_event(SessionClosed(session, reason))

    def _on_lap_data(self, session_time: float, lap_data: LapData) -> None:
        lap = self.lap
        number = lap_data.current_lap_num
        last_lap_time_ms = lap_data.last_lap_time_ms
        if lap is None:
            if self._closed_lap_number is None or number > self._closed_lap_number:
                lap = self.lap = Lap(number, session_time)
                self._closed_lap_number = None
        elif number > lap.number:
            self._complete(lap, last_lap_time_ms, session_time)
            lap = self.lap = Lap(number, session_time)
        elif number < lap.number:
            # Back over the line without a FLBK event reaching us (dropped packet); rewind to this moment.
            self._rewind(session_time)
            lap = self.lap
        elif self._last_lap_time_ms is not None and last_lap_time_ms != self._last_lap_time_ms:
            # The chequered flag: the last lap time changes but the lap number doesn't.
            self._complete(lap, last_lap_time_ms, session_time)
            self._closed_lap_number = number
            lap = self.lap = None

        if lap is not None:
            previous = self._lap_data
            if previous is not None and self._restarts(previous, lap_data, session_time):
                lap.restart(session_time)
            distance = lap_data.lap_distance
            if distance >= 0:
                if lap.start_distance is None:
                    lap.start_distance = distance
                    lap.start_session_time = session_time
                lap.end_distance = distance
            lap.invalid = lap_data.current_lap_invalid
        self._lap_data = lap_data
        self._lap_data_time = session_time
        self._last_lap_time_ms = last_lap_time_ms

    def _restarts(self, previous: LapData, lap_data: LapData, session_time: float) -> bool:
        """True when the lap starts over under the same lap number, so the samples so far don't belong to it."""
        if lap_data.driver_status == DRIVER_FLYING_LAP and previous.driver_status in (DRIVER_GARAGE, DRIVER_OUT_LAP):
            return True  # out lap into flying lap
        if session_time < self._lap_data_time:
            return False  # a flashback: the lap timer and distance rewind with the session time
        if lap_data.current_lap_time_ms < previous.current_lap_time_ms - LAP_RESTART_DROP_MS:
            return True  # Time Trial restart
        session = self.session
        assert session is not None
        track_length = session.info.track_length
        # Across the line from a Time Trial restart's run-up; the lap number doesn't change.
        return track_length > 0 and previous.lap_distance - lap_data.lap_distance > PARTIAL_LAP_SHARE * track_length

    def _complete(self, lap: Lap, lap_time_ms: int, session_time: float) -> None:
        session = self.session
        assert session is not None
        lap.lap_time_ms = lap_time_ms
        lap.end_session_time = session_time
        covered = lap.end_distance - (lap.start_distance if lap.start_distance is not None else lap.end_distance)
        lap.partial = covered < PARTIAL_LAP_SHARE * session.info.track_length
        session.laps.append(lap)
        self.on_event(LapCompleted(session, lap))

    def _rewind(self, target_session_time: float) -> None:
        session = self.session
        assert session is not None
        lap = self.lap
        # Reopen laps that closed after the target; the lap that followed them never happened.
        while session.laps and session.laps[-1].end_session_time > target_session_time:
            lap = session.laps.pop().reopened()
            self._closed_lap_number = None
            self.on_event(LapReopened(session, lap))
        if lap is not None:
            lap.samples.truncate_from(target_session_time)
        self.lap = lap
        self._last_lap_time_ms = None
        # Lap times sent before the flashback may include laps it undid.
        self._history = ()

    def _sample(self, session_time: float, telemetry: CarTelemetry) -> None:
        lap = self.lap
        lap_data = self._lap_data
        if lap is None or lap_data is None or lap_data.driver_status == DRIVER_GARAGE or lap_data.lap_distance < 0:
            return
        samples = lap.samples
        times = samples.session_time
        if times and session_time <= times[-1]:
            samples.truncate_from(session_time)
        times.append(session_time)
        samples.lap_distance.append(lap_data.lap_distance)
        samples.lap_time_ms.append(lap_data.current_lap_time_ms)
        samples.speed.append(telemetry.speed)
        samples.throttle.append(telemetry.throttle)
        samples.brake.append(telemetry.brake)
        samples.steer.append(telemetry.steer)
        samples.gear.append(telemetry.gear)
        samples.engine_rpm.append(telemetry.engine_rpm)
        samples.drs.append(telemetry.drs)
