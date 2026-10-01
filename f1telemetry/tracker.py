"""Session and lap tracking: splits the parsed packet stream into sessions and laps, and undoes flashbacks.

Rules come from real F1 25 recordings (see docs/udp-spec.md):
- A session opens on the first Session packet of a new `sessionUID`. Skipped sessions get a UID but only send
  events, so a UID alone isn't a session. UID 0 (menus) is ignored.
- A session closes on SEND or a UID change. There is no idle timeout: the game sends nothing while paused, often for
  minutes, so silence doesn't mean the session is over. Call `close()` on shutdown.
- Loading a mid-session save looks like quitting and starting again: SEND, then a new UID. The new UID's first
  Session packet makes it a candidate: same track, session type and lap count, with `sessionTime` rewound to the save
  point but not to 0, which is where a restarted race starts. Its first LapData decides: a load puts the car on the
  lap and at the distance driven at that `sessionTime`, which a save from another race would not. The closed session
  then resumes and rewinds like a flashback.
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
from dataclasses import dataclass, field, fields, replace

from f1telemetry.car_damage import CarDamage
from f1telemetry.car_status import CarStatus
from f1telemetry.car_telemetry import CarTelemetry
from f1telemetry.event import Flashback, SessionEnded
from f1telemetry.lap_data import LapData
from f1telemetry.motion import Motion
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
# A loaded save puts the car within 0.2 m of where it was driven at that sessionTime (three Brazil loads).
LOAD_DISTANCE_TOLERANCE_M = 10.0


@dataclass(slots=True)
class LapSamples:
    """One row per CarTelemetry packet, stored as columns so a lap can be saved and charted without reshaping.

    Status, damage and motion arrive at their own rates, so each row holds the latest of those seen, or 0 before the
    first one.
    """

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
    tyre_compound: array[int] = field(default_factory=lambda: array("B"))  # visual compound id
    tyre_inner_temperature_rl: array[int] = field(default_factory=lambda: array("H"))
    tyre_inner_temperature_rr: array[int] = field(default_factory=lambda: array("H"))
    tyre_inner_temperature_fl: array[int] = field(default_factory=lambda: array("H"))
    tyre_inner_temperature_fr: array[int] = field(default_factory=lambda: array("H"))
    tyre_wear_rl: array[float] = field(default_factory=lambda: array("f"))
    tyre_wear_rr: array[float] = field(default_factory=lambda: array("f"))
    tyre_wear_fl: array[float] = field(default_factory=lambda: array("f"))
    tyre_wear_fr: array[float] = field(default_factory=lambda: array("f"))
    fuel_in_tank: array[float] = field(default_factory=lambda: array("f"))
    ers_store_mj: array[float] = field(default_factory=lambda: array("f"))
    world_x: array[float] = field(default_factory=lambda: array("f"))
    world_z: array[float] = field(default_factory=lambda: array("f"))

    def __len__(self) -> int:
        return len(self.session_time)

    def columns(self) -> tuple[array[float] | array[int], ...]:
        return tuple(getattr(self, column.name) for column in fields(self))

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
        return replace(self, **{column.name: getattr(self, column.name)[:] for column in fields(self)})


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
    # Caught on the way round: LapData resets them to 0 at the line, before the lap can be closed.
    sector1_ms: int = 0
    sector2_ms: int = 0
    samples: LapSamples = field(default_factory=LapSamples)

    @property
    def sector_times_ms(self) -> tuple[int, int, int]:
        """Sectors 1-3; sector 3 only once the lap is closed with both others seen, else 0."""
        s1, s2 = self.sector1_ms, self.sector2_ms
        s3 = self.lap_time_ms - s1 - s2 if self.lap_time_ms and s1 and s2 else 0
        return s1, s2, s3

    def reopened(self) -> Lap:
        """A copy to keep driving after a flashback, leaving the completed lap as it was reported."""
        return Lap(
            self.number,
            self.start_session_time,
            invalid=self.invalid,
            start_distance=self.start_distance,
            end_distance=self.end_distance,
            sector1_ms=self.sector1_ms,
            sector2_ms=self.sector2_ms,
            samples=self.samples.copy(),
        )

    def restart(self, session_time: float) -> None:
        self.start_session_time = session_time
        self.start_distance = None
        self.sector1_ms = self.sector2_ms = 0
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


@dataclass(frozen=True, slots=True)
class SessionResumed:
    """A save was loaded, so the session closed by the SEND before it goes on under a new UID."""

    session: TrackedSession


@dataclass(frozen=True, slots=True)
class _Ended:
    """A session closed by SEND, kept in case a load of a save from it follows."""

    session: TrackedSession
    lap: Lap | None  # the lap in progress at SEND, which a load may take up again
    session_time: float  # of the SEND


@dataclass(frozen=True, slots=True)
class _Pending:
    """A new UID whose Session packet looks like a load of the ended session; its first LapData decides."""

    uid: int
    packet_format: int
    player_index: int
    info: Session
    session_time: float


type TrackerEvent = SessionOpened | LapCompleted | LapReopened | SessionClosed | SessionResumed


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
        # The latest of each, held for every telemetry sample until the next arrives.
        self._status: CarStatus | None = None
        self._damage: CarDamage | None = None
        self._motion: Motion | None = None
        self._ended: _Ended | None = None
        self._pending: _Pending | None = None

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
            pending = self._pending
            if pending is not None and pending.uid == uid:
                if packet_id != PacketId.LAP_DATA:
                    return
                if self._matches_save(data, pending.session_time):  # type: ignore[arg-type]
                    self._resume(uid, pending.session_time)
                else:
                    self._open(uid, pending.packet_format, pending.player_index, pending.info)
            elif packet_id == PacketId.SESSION and isinstance(data, Session):
                if self._is_load(data, header.session_time):
                    self._pending = _Pending(
                        uid, header.packet_format, header.player_car_index, data, header.session_time
                    )
                else:
                    self._open(uid, header.packet_format, header.player_car_index, data)
                return
            else:
                return
        if packet_id == PacketId.CAR_TELEMETRY:
            self._sample(header.session_time, data)  # type: ignore[arg-type]
        elif packet_id == PacketId.LAP_DATA:
            self._on_lap_data(header.session_time, data)  # type: ignore[arg-type]
        elif packet_id == PacketId.MOTION:
            self._motion = data  # type: ignore[assignment]
        elif packet_id == PacketId.CAR_STATUS:
            self._status = data  # type: ignore[assignment]
        elif packet_id == PacketId.CAR_DAMAGE:
            self._damage = data  # type: ignore[assignment]
        elif packet_id == PacketId.EVENT:
            if isinstance(data, Flashback):
                self._rewind(data.session_time)
            elif isinstance(data, SessionEnded):
                self._close("ended", header.session_time)
        elif packet_id == PacketId.SESSION_HISTORY:
            self._history = data.lap_times_ms  # type: ignore[attr-defined]

    def close(self, reason: str = "shutdown") -> None:
        """Close the open session, if any, dropping its unfinished lap."""
        if self.session is not None:
            self._close(reason)

    def _open(self, uid: int, packet_format: int, player_index: int, info: Session) -> None:
        self.session = TrackedSession(uid, packet_format, player_index, info)
        self._ended = None
        self._pending = None
        self.lap = None
        self._lap_data = None
        self._closed_lap_number = None
        self._last_lap_time_ms = None
        self._history = ()
        self.on_event(SessionOpened(self.session))

    def _close(self, reason: str, session_time: float | None = None) -> None:
        session = self.session
        assert session is not None
        lap = self.lap
        if lap is not None and lap.number <= len(self._history) and self._history[lap.number - 1]:
            self._complete(lap, self._history[lap.number - 1], self._lap_data_time)
            lap = None
        # Only SEND can come before a load; a UID change without it is a new session (a career strategy restart).
        self._ended = _Ended(session, lap, session_time) if session_time is not None else None
        self._closed_uids.add(session.uid)
        self.session = None
        self.lap = None
        self._lap_data = None
        self.on_event(SessionClosed(session, reason))

    def _is_load(self, info: Session, session_time: float) -> bool:
        ended = self._ended
        if ended is None:
            return False
        before = ended.session.info
        return (
            (info.track_id, info.session_type, info.total_laps)
            == (before.track_id, before.session_type, before.total_laps)
            # A restarted race starts again at exactly 0; a save is somewhere before the moment it was left.
            and 0 < session_time < ended.session_time
        )

    def _matches_save(self, lap_data: LapData, session_time: float) -> bool:
        """True when the car is on the lap, and between the distances, driven either side of `session_time`."""
        ended = self._ended
        assert ended is not None
        laps = ended.session.laps if ended.lap is None else [*ended.session.laps, ended.lap]
        lap = next((lap for lap in reversed(laps) if lap.start_session_time <= session_time), None)
        if lap is None or lap.number != lap_data.current_lap_num:
            return False
        if lap.end_session_time and session_time > lap.end_session_time:
            return False  # the gap after a lap closed at the flag
        times = lap.samples.session_time
        distances = lap.samples.lap_distance
        i = bisect_left(times, session_time)
        distance = lap_data.lap_distance
        if i > 0 and distance < distances[i - 1] - LOAD_DISTANCE_TOLERANCE_M:
            return False
        return i == len(times) or distance <= distances[i] + LOAD_DISTANCE_TOLERANCE_M

    def _resume(self, uid: int, session_time: float) -> None:
        ended = self._ended
        assert ended is not None
        self._ended = None
        self._pending = None
        session = self.session = ended.session
        session.uid = uid
        self.lap = ended.lap
        self._lap_data = None
        self._closed_lap_number = None
        self._last_lap_time_ms = None
        self.on_event(SessionResumed(session))
        self._rewind(session_time)

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
            if lap_data.sector1_time_ms:
                lap.sector1_ms = lap_data.sector1_time_ms
            if lap_data.sector2_time_ms:
                lap.sector2_ms = lap_data.sector2_time_ms
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
        samples.tyre_inner_temperature_rl.append(telemetry.tyre_inner_temperature_rl)
        samples.tyre_inner_temperature_rr.append(telemetry.tyre_inner_temperature_rr)
        samples.tyre_inner_temperature_fl.append(telemetry.tyre_inner_temperature_fl)
        samples.tyre_inner_temperature_fr.append(telemetry.tyre_inner_temperature_fr)
        status = self._status
        samples.tyre_compound.append(status.visual_tyre_compound if status else 0)
        samples.fuel_in_tank.append(status.fuel_in_tank if status else 0.0)
        samples.ers_store_mj.append(status.ers_store_energy / 1e6 if status else 0.0)
        damage = self._damage
        samples.tyre_wear_rl.append(damage.tyre_wear_rl if damage else 0.0)
        samples.tyre_wear_rr.append(damage.tyre_wear_rr if damage else 0.0)
        samples.tyre_wear_fl.append(damage.tyre_wear_fl if damage else 0.0)
        samples.tyre_wear_fr.append(damage.tyre_wear_fr if damage else 0.0)
        motion = self._motion
        samples.world_x.append(motion.world_x if motion else 0.0)
        samples.world_z.append(motion.world_z if motion else 0.0)
