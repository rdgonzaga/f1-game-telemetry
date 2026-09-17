from __future__ import annotations

import logging

import pytest

from f1telemetry.car_telemetry2 import CAR_TELEMETRY_2, ActiveAeroMode, CarTelemetry2, register
from f1telemetry.packets import FORMATS, HEADER, PacketDispatcher, PacketHeader, PacketId


def make_header(packet_format: int = 2026, player: int = 5) -> PacketHeader:
    return PacketHeader(packet_format, 25, 1, 15, 1, PacketId.CAR_TELEMETRY_2, 1, 3.0, 10, 10, player, 255)


def make_packet(cars: dict[int, CarTelemetry2], packet_format: int = 2026, player: int = 5) -> bytes:
    body = bytearray(24 * CAR_TELEMETRY_2.size)
    for index, car in cars.items():
        CAR_TELEMETRY_2.pack_into(body, index * CAR_TELEMETRY_2.size, *car)
    return HEADER.pack(*make_header(packet_format, player)) + bytes(body)


PLAYER = CarTelemetry2(
    active_aero_mode=ActiveAeroMode.STRAIGHT,
    active_aero_available=True,
    active_aero_activation_distance=1234,
    overtake_available=True,
    overtake_active=False,
    overtake_activation_distance=65535,
    regulations_2026_applicable=True,
    is_driving_wrong_way=False,
)
RIVAL = CarTelemetry2(0, False, 7, False, True, 9, False, True)


def test_layout_is_10_bytes_per_car() -> None:
    assert CAR_TELEMETRY_2.size == 10
    assert FORMATS[2026].packet_sizes[PacketId.CAR_TELEMETRY_2] == HEADER.size + 24 * CAR_TELEMETRY_2.size


@pytest.mark.parametrize("player", [0, 5, 23])
def test_decodes_player_car_only(player: int) -> None:
    neighbours = {i: RIVAL for i in (player - 1, player + 1) if 0 <= i < 24}
    dispatcher = PacketDispatcher()
    register(dispatcher)
    packet = dispatcher.parse(make_packet({player: PLAYER, **neighbours}, player=player))
    assert packet is not None
    assert packet.data == PLAYER


def test_no_player_car_returns_none() -> None:
    dispatcher = PacketDispatcher()
    register(dispatcher)
    packet = dispatcher.parse(make_packet({}, player=255))
    assert packet is not None
    assert packet.data is None


def test_2025_format_is_ignored(caplog: pytest.LogCaptureFixture) -> None:
    dispatcher = PacketDispatcher()
    register(dispatcher)
    with caplog.at_level(logging.WARNING, logger="f1telemetry.packets"):
        assert dispatcher.parse(make_packet({5: PLAYER}, packet_format=2025)) is None
    assert caplog.records == []
