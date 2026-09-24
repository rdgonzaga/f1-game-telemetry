"""LiveState merging and the asyncio listener, driven by the committed real-game fixtures."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from f1telemetry.car_damage import CarDamage
from f1telemetry.car_status import CarStatus
from f1telemetry.car_telemetry import CarTelemetry
from f1telemetry.car_telemetry2 import CarTelemetry2
from f1telemetry.lap_data import LapData
from f1telemetry.listener import TelemetryProtocol
from f1telemetry.live import CONNECTED_TIMEOUT_NS, NS_PER_SECOND, LiveState
from f1telemetry.packets import PACKET_ID_OFFSET, Packet, PacketId
from f1telemetry.rawfile import read_records
from f1telemetry.session import Session
from f1telemetry.tracker import SessionTracker

FIXTURES = Path(__file__).parent / "fixtures"
ADDR = ("127.0.0.1", 20777)
SESSION_UID_OFFSET = 7  # after format u16, year, major, minor, packet version and packet id


def datagrams(name: str) -> list[bytes]:
    return [data for _, data in read_records(FIXTURES / f"{name}.f1raw")]


def feed(state: LiveState, packets: list[bytes]) -> None:
    protocol = TelemetryProtocol(state)
    for data in packets:
        protocol.datagram_received(data, ADDR)


def first_of(packets: list[bytes], packet_id: PacketId) -> bytes:
    return next(data for data in packets if data[PACKET_ID_OFFSET] == packet_id)


def test_2026_fixture_fills_every_slot() -> None:
    packets = datagrams("race-2026-monza-finish")
    state = LiveState()
    feed(state, packets)

    assert isinstance(state.session, Session)
    assert isinstance(state.lap, LapData)
    assert isinstance(state.telemetry, CarTelemetry)
    assert isinstance(state.status, CarStatus)
    assert isinstance(state.damage, CarDamage)
    assert isinstance(state.telemetry2, CarTelemetry2)
    assert (state.packet_format, state.player_index) == (2026, 21)
    assert state.packets_seen == len(packets)
    # The last values of the finish fixture: the flag has fallen.
    assert state.lap.last_lap_time_ms == 83561
    assert state.lap.result_status == 3


def test_missing_player_car_keeps_the_previous_value() -> None:
    packets = datagrams("race-2026-monza-finish")
    state = LiveState()
    feed(state, packets)
    stored = state.telemetry

    # Player index past the car count means no player slot, so the parser yields a packet with no payload.
    spectating = bytearray(first_of(packets, PacketId.CAR_TELEMETRY))
    spectating[27] = 255
    feed(state, [bytes(spectating)])

    assert state.telemetry is stored
    assert state.player_index == 255


def test_new_session_uid_clears_stored_packets() -> None:
    state = LiveState()
    feed(state, datagrams("f2-2026-sakhir-pit"))
    f2_uid = state.session_uid
    assert state.status is not None

    monza = datagrams("race-2026-monza-finish")
    feed(state, [first_of(monza, PacketId.CAR_TELEMETRY)])

    assert state.session_uid != f2_uid
    assert state.telemetry is not None
    assert state.session is None
    assert state.lap is None
    assert state.status is None
    assert state.damage is None
    assert state.telemetry2 is None


def test_uid_zero_packets_keep_the_stored_packets() -> None:
    packets = datagrams("race-2026-monza-finish")
    state = LiveState()
    # The fixture already ends with the UID-0 SessionHistory burst sent before SEND.
    feed(state, packets)
    uid, telemetry = state.session_uid, state.telemetry
    assert telemetry is not None

    menu = bytearray(first_of(packets, PacketId.CAR_TELEMETRY))
    menu[SESSION_UID_OFFSET : SESSION_UID_OFFSET + 8] = bytes(8)
    feed(state, [bytes(menu)])

    assert (state.session_uid, state.telemetry) == (uid, telemetry)
    assert state.packets_seen == len(packets) + 1


def test_error_while_handling_a_packet_is_logged_once(caplog: pytest.LogCaptureFixture) -> None:
    class Broken(SessionTracker):
        def update(self, packet: Packet) -> None:
            raise RuntimeError("tracker bug")

    state = LiveState()
    protocol = TelemetryProtocol(state, tracker=Broken())
    packets = datagrams("race-2026-monza-finish")[:50]
    with caplog.at_level(logging.ERROR):
        for data in packets:
            protocol.datagram_received(data, ADDR)

    assert protocol.errors > 1
    assert len([r for r in caplog.records if "still listening" in r.message]) == 1
    # Live state keeps updating: the error came after it.
    assert state.telemetry is not None and state.packets_seen == 50


def test_connection_status_expires_after_a_second() -> None:
    state = LiveState()
    assert not state.connected(now_ns=5 * NS_PER_SECOND)

    state.note_datagram(5 * NS_PER_SECOND)
    assert state.connected(5 * NS_PER_SECOND)
    assert state.connected(5 * NS_PER_SECOND + CONNECTED_TIMEOUT_NS - 1)
    assert not state.connected(5 * NS_PER_SECOND + CONNECTED_TIMEOUT_NS)


def test_packets_per_second_reports_the_previous_second() -> None:
    state = LiveState()
    start = 10 * NS_PER_SECOND
    for i in range(60):
        state.note_datagram(start + i * NS_PER_SECOND // 60)
    # Still inside the first second, so no full second has been measured yet.
    assert state.packets_per_second == 0

    state.note_datagram(start + NS_PER_SECOND)
    assert state.packets_per_second == 60


def test_unusable_datagrams_are_dropped_but_still_count() -> None:
    state = LiveState()
    feed(state, [b"", b"\x00" * 29, b"\xe9\x07" + b"\x00" * 27])

    assert state.packets_seen == 3
    assert (state.session, state.lap, state.telemetry, state.status, state.damage, state.telemetry2) == (None,) * 6
    assert state.session_uid is None
