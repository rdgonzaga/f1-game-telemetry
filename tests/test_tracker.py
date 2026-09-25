"""Session and lap tracking, driven by packets built from real fixture payloads plus the fixtures themselves."""

from __future__ import annotations

from pathlib import Path

from f1telemetry.car_telemetry import CarTelemetry
from f1telemetry.event import SESSION_ENDED, Flashback
from f1telemetry.lap_data import LapData
from f1telemetry.packets import Packet, PacketHeader, PacketId
from f1telemetry.parsers import make_dispatcher
from f1telemetry.rawfile import read_records
from f1telemetry.session import Session
from f1telemetry.session_history import SessionHistory
from f1telemetry.tracker import (
    LapCompleted,
    LapReopened,
    SessionClosed,
    SessionOpened,
    SessionTracker,
    TrackerEvent,
)

FIXTURES = Path(__file__).parent / "fixtures"
UID = 0x1234
TRACK_LENGTH = 5000


def fixture_packets(name: str) -> list[Packet]:
    dispatcher = make_dispatcher()
    packets = (dispatcher.parse(data) for _, data in read_records(FIXTURES / f"{name}.f1raw"))
    return [packet for packet in packets if packet is not None]


def first_payload[T](packets: list[Packet], kind: type[T]) -> T:
    for packet in packets:
        if isinstance(packet.data, kind):
            return packet.data
    raise LookupError(kind.__name__)


TEMPLATES = fixture_packets("race-2026-monza-finish")
HEADER: PacketHeader = TEMPLATES[0].header
SESSION = first_payload(TEMPLATES, Session)._replace(track_length=TRACK_LENGTH)
LAP = first_payload(TEMPLATES, LapData)
TELEMETRY = first_payload(TEMPLATES, CarTelemetry)


class Game:
    """Sends packets the way the game does: one LapData and one CarTelemetry per frame."""

    def __init__(self) -> None:
        self.events: list[TrackerEvent] = []
        self.tracker = SessionTracker(self.events.append)
        self.uid = UID
        self.time = 0.0
        self.last_lap_time_ms = 0

    def send(self, packet_id: PacketId, data: object, uid: int | None = None) -> None:
        header = HEADER._replace(
            packet_id=packet_id, session_uid=self.uid if uid is None else uid, session_time=self.time
        )
        self.tracker.update(Packet(header, data))

    def start(self) -> None:
        self.send(PacketId.SESSION, SESSION)

    def frame(
        self,
        lap: int,
        distance: float,
        lap_time_ms: int,
        *,
        status: int = 4,
        invalid: bool = False,
    ) -> None:
        self.time += 0.5
        lap_data = LAP._replace(
            current_lap_num=lap,
            lap_distance=distance,
            current_lap_time_ms=lap_time_ms,
            last_lap_time_ms=self.last_lap_time_ms,
            driver_status=status,
            current_lap_invalid=invalid,
        )
        self.send(PacketId.LAP_DATA, lap_data)
        self.send(PacketId.CAR_TELEMETRY, TELEMETRY)

    def drive_lap(self, lap: int, lap_time_ms: int = 90_000, steps: int = 10) -> None:
        """Frames covering the whole track on lap `lap`."""
        for i in range(steps):
            share = i / steps
            self.frame(lap, TRACK_LENGTH * share, int(lap_time_ms * share))

    def cross_line(self, next_lap: int, lap_time_ms: int) -> None:
        self.last_lap_time_ms = lap_time_ms
        self.frame(next_lap, 1.0, 10)

    def flashback(self, to_time: float) -> None:
        self.send(PacketId.EVENT, Flashback(0, to_time))
        self.time = to_time

    def of_type[T](self, kind: type[T]) -> list[T]:
        return [event for event in self.events if isinstance(event, kind)]


def test_uid_zero_and_event_only_uids_are_ignored() -> None:
    game = Game()
    game.send(PacketId.SESSION, SESSION, uid=0)
    # Skipped sessions get a UID but only send events.
    game.send(PacketId.EVENT, None, uid=0x999)
    game.send(PacketId.LAP_DATA, LAP, uid=0x999)

    assert game.events == []
    assert game.tracker.session is None


def test_new_uid_closes_the_session_without_a_send_event() -> None:
    game = Game()
    game.start()
    game.drive_lap(1)

    # Restarting from the menu gives a new UID and no SEND.
    game.uid = 0x5678
    game.start()

    [closed] = game.of_type(SessionClosed)
    assert (closed.session.uid, closed.reason) == (UID, "new session")
    assert closed.session.laps == []
    assert [opened.session.uid for opened in game.of_type(SessionOpened)] == [UID, 0x5678]


def test_stray_packet_from_an_older_session_is_ignored() -> None:
    game = Game()
    for uid in (UID, 0x5678):
        game.uid = uid
        game.start()
        game.send(PacketId.EVENT, SESSION_ENDED)
    game.uid = 0x9ABC
    game.start()
    game.drive_lap(1)

    # A late packet from the first session, after two more have opened.
    game.send(PacketId.SESSION, SESSION, uid=UID)

    assert [type(event) for event in game.events] == [SessionOpened, SessionClosed] * 2 + [SessionOpened]
    assert game.tracker.session is not None and game.tracker.session.uid == 0x9ABC


def test_lap_closes_when_the_lap_number_increments() -> None:
    game = Game()
    game.start()
    game.drive_lap(1)
    game.frame(1, 4990.0, 89_900, invalid=True)
    game.cross_line(2, 90_123)

    [completed] = game.of_type(LapCompleted)
    lap = completed.lap
    assert (lap.number, lap.lap_time_ms, lap.invalid, lap.partial) == (1, 90_123, True, False)
    assert len(lap.samples) == 11
    assert game.tracker.lap is not None and game.tracker.lap.number == 2


def test_invalid_flag_follows_the_game_when_a_flashback_clears_it() -> None:
    game = Game()
    game.start()
    game.drive_lap(1)
    game.frame(1, 4990.0, 89_900, invalid=True)
    game.flashback(game.time - 1)
    game.frame(1, 4980.0, 89_800, invalid=False)
    game.cross_line(2, 90_000)

    assert game.of_type(LapCompleted)[0].lap.invalid is False


def test_chained_flashbacks_keep_rewinding() -> None:
    game = Game()
    game.start()
    game.drive_lap(1)
    lap = game.tracker.lap
    assert lap is not None
    times = list(lap.samples.session_time)

    game.flashback(times[6] - 0.1)
    game.flashback(times[5] - 0.1)
    game.flashback(times[3] - 0.1)

    assert list(lap.samples.session_time) == times[:3]


def test_flashback_over_the_line_reopens_the_completed_lap() -> None:
    game = Game()
    game.start()
    game.drive_lap(6)
    lap_six = game.tracker.lap
    game.cross_line(7, 96_959)
    game.frame(7, 50.0, 800)

    game.flashback(game.time - 2.0)

    [reopened] = game.of_type(LapReopened)
    # A copy: the lap already reported as completed keeps its data.
    assert reopened.lap is not lap_six
    assert reopened.lap.number == 6
    assert game.tracker.lap is reopened.lap
    assert game.tracker.session is not None and game.tracker.session.laps == []

    game.last_lap_time_ms = 95_852
    game.frame(6, 4990.0, 97_000)
    game.cross_line(7, 97_495)

    completed = game.of_type(LapCompleted)
    assert [event.lap.lap_time_ms for event in completed] == [96_959, 97_495]
    assert game.tracker.session.laps == [reopened.lap]


def test_lap_number_going_back_without_a_flashback_event_reopens_the_lap() -> None:
    game = Game()
    game.start()
    game.drive_lap(6)
    game.cross_line(7, 96_959)
    game.time -= 3.0
    game.frame(6, 4980.0, 96_000)

    assert len(game.of_type(LapReopened)) == 1
    assert game.tracker.lap is not None and game.tracker.lap.number == 6


def test_flying_lap_drops_the_out_lap_samples() -> None:
    game = Game()
    game.start()
    for i in range(5):
        game.frame(1, 3000.0 + i * 400, 0, status=3)
    game.frame(1, 1.0, 16, status=1)

    lap = game.tracker.lap
    assert lap is not None
    assert list(lap.samples.lap_distance) == [1.0]
    assert lap.start_distance == 1.0


def test_time_trial_restart_drops_the_aborted_attempt() -> None:
    game = Game()
    game.start()
    game.drive_lap(3, steps=6)
    # Restart: the timer goes back to zero and the car is put on a run-up before the line.
    game.frame(3, 3300.0, 0, status=1)
    game.frame(3, 4900.0, 0, status=1)

    lap = game.tracker.lap
    assert lap is not None
    assert list(lap.samples.lap_distance) == [3300.0, 4900.0]

    # Crossing the line from the run-up wraps the distance without a new lap number.
    game.frame(3, 5.0, 16, status=1)
    assert list(lap.samples.lap_distance) == [5.0]
    assert lap.start_distance == 5.0


def test_lap_timer_jitter_is_not_a_restart() -> None:
    game = Game()
    game.start()
    game.frame(1, 1000.0, 35_255)
    game.frame(1, 1010.0, 35_251)

    lap = game.tracker.lap
    assert lap is not None
    assert len(lap.samples) == 2


def test_samples_skip_the_garage_and_the_run_up_before_the_line() -> None:
    game = Game()
    game.start()
    game.frame(1, 100.0, 0, status=0)
    game.frame(1, -60.0, 0)
    game.frame(1, 5.0, 100)

    lap = game.tracker.lap
    assert lap is not None
    assert list(lap.samples.lap_distance) == [5.0]


def test_resuming_before_the_flashback_target_keeps_samples_in_order() -> None:
    game = Game()
    game.start()
    game.drive_lap(1)
    lap = game.tracker.lap
    assert lap is not None
    times = list(lap.samples.session_time)

    # The game resumes about a second before the target it announced.
    game.flashback(times[6])
    game.time = times[4] - 0.5
    game.frame(1, 2100.0, 36_000)

    assert list(lap.samples.session_time) == [*times[:4], times[4]]


def test_final_lap_comes_from_session_history_when_lap_data_misses_the_flag() -> None:
    """At 20 Hz the game sends only every third frame, so no LapData may carry the flag's new last lap time."""
    events: list[TrackerEvent] = []
    tracker = SessionTracker(events.append)
    for packet in TEMPLATES:
        if isinstance(packet.data, LapData) and packet.data.last_lap_time_ms == 83561:
            continue
        tracker.update(packet)

    [completed] = [event for event in events if isinstance(event, LapCompleted)]
    assert (completed.lap.number, completed.lap.lap_time_ms) == (3, 83561)
    assert isinstance(events[-1], SessionClosed)
    assert events[-1].session.laps == [completed.lap]


def test_session_history_only_completes_a_lap_it_lists_as_finished() -> None:
    game = Game()
    game.start()
    game.drive_lap(2)
    game.send(PacketId.SESSION_HISTORY, SessionHistory((91_000, 0)), uid=0)
    game.send(PacketId.EVENT, SESSION_ENDED)

    assert game.of_type(LapCompleted) == []


def test_flashback_forgets_session_history_it_may_have_undone() -> None:
    game = Game()
    game.start()
    game.drive_lap(2)
    game.send(PacketId.SESSION_HISTORY, SessionHistory((91_000, 92_000)))
    game.flashback(game.time - 1)
    game.tracker.close()

    assert game.of_type(LapCompleted) == []
