"""CarTelemetry, CarStatus, CarDamage and LapData against full car-slot layouts written from the spec.

The full layouts below are independent of the parsers' own structs, so a wrong offset or field order in a parser
fails here instead of agreeing with itself. Every non-player slot is filled with 0xAB junk.
"""

from __future__ import annotations

import struct

import pytest

from f1telemetry import car_damage, car_status, car_telemetry, lap_data
from f1telemetry.car_damage import CarDamage
from f1telemetry.car_status import CarStatus
from f1telemetry.car_telemetry import CarTelemetry
from f1telemetry.lap_data import LapData
from f1telemetry.packets import FORMATS, HEADER, PacketDispatcher, PacketHeader, PacketId

FULL_TELEMETRY = {2025: struct.Struct("<HfffBbH?BH4H4B4BH4f4B"), 2026: struct.Struct("<HfffBbH?BH4H4B4BB4f4B")}
FULL_STATUS = {2025: struct.Struct("<BBBB?fffHHB?HBBBbfffBfff?"), 2026: struct.Struct("<BBBB?fffHHB?HBBBbfffBffff?")}
FULL_DAMAGE = struct.Struct("<4f4B4B4B6B??8B??")
FULL_LAP = struct.Struct("<IIHBHBHBHBfffBBBBB?BBBBBBBB?HH?fB")
FORMATS_UNDER_TEST = [2025, 2026]


def make_dispatcher() -> PacketDispatcher:
    dispatcher = PacketDispatcher()
    for module in (car_telemetry, car_status, car_damage, lap_data):
        module.register(dispatcher)
    return dispatcher


def build_packet(
    packet_format: int, packet_id: PacketId, slot: struct.Struct, values: tuple[object, ...], player: int
) -> bytes:
    header = PacketHeader(packet_format, 25, 1, 15, 1, packet_id, 1, 3.0, 10, 10, player, 255)
    size = FORMATS[packet_format].packet_sizes[packet_id]
    data = bytearray(HEADER.pack(*header) + b"\xab" * (size - HEADER.size))
    if player < FORMATS[packet_format].max_cars:
        slot.pack_into(data, HEADER.size + player * slot.size, *values)
    return bytes(data)


def players(packet_format: int) -> list[int]:
    return [0, 7, FORMATS[packet_format].max_cars - 1]


@pytest.mark.parametrize("packet_format", FORMATS_UNDER_TEST)
def test_car_telemetry(packet_format: int) -> None:
    engine_temperature = 105
    raw = (
        *(287, 0.75, -0.25, 0.5, 10, 7, 11500, True, 80, 0xBEEF),
        *(500, 510, 520, 530, 90, 91, 92, 93, 100, 101, 102, 103),
        engine_temperature,
        *(22.5, 23.0, 23.5, 24.0, 0, 1, 2, 3),
    )
    expected = CarTelemetry(
        *(287, 0.75, -0.25, 0.5, 10, 7, 11500, True, 80),
        *(500, 510, 520, 530, 90, 91, 92, 93, 100, 101, 102, 103),
        engine_temperature,
        *(22.5, 23.0, 23.5, 24.0),
    )
    dispatcher = make_dispatcher()
    for player in players(packet_format):
        packet = dispatcher.parse(
            build_packet(packet_format, PacketId.CAR_TELEMETRY, FULL_TELEMETRY[packet_format], raw, player)
        )
        assert packet is not None
        assert packet.data == expected


@pytest.mark.parametrize("packet_format", FORMATS_UNDER_TEST)
def test_car_status(packet_format: int) -> None:
    head = (2, 1, 3, 56, False, 50.5, 110.0, 12.25, 13000, 4000, 8, True, 0, 18, 17, 3, -1)
    ers = (500000.0, 120000.0, 3000000.0, 3, 1000.5, 0.0)
    if packet_format == 2026:
        raw: tuple[object, ...] = (*head, *ers, 4000000.0, 2500.25, False)
        limit: float | None = 4000000.0
    else:
        raw = (*head, *ers, 2500.25, False)
        limit = None
    expected = CarStatus(
        2, True, 3, 56, False, 50.5, 110.0, 12.25, 13000, 4000, 8, True, 0, 18, 17, 3, -1, *ers, 2500.25, limit
    )
    dispatcher = make_dispatcher()
    for player in players(packet_format):
        packet = dispatcher.parse(
            build_packet(packet_format, PacketId.CAR_STATUS, FULL_STATUS[packet_format], raw, player)
        )
        assert packet is not None
        assert packet.data == expected


@pytest.mark.parametrize("packet_format", FORMATS_UNDER_TEST)
def test_car_damage(packet_format: int) -> None:
    # wear x4, tyre/brake damage and blisters x12, wing/floor/diffuser/sidepod x6, DRS/ERS fault, gearbox, engine
    parsed = (10.5, 11.5, 12.5, 13.5, *range(1, 13), 13, 14, 15, 16, 17, 18, True, False, 19, 20)
    # unread tail: six engine component wear bytes, engine blown, engine seized
    raw = (*parsed, 21, 22, 23, 24, 25, 26, False, True)
    dispatcher = make_dispatcher()
    for player in players(packet_format):
        packet = dispatcher.parse(build_packet(packet_format, PacketId.CAR_DAMAGE, FULL_DAMAGE, raw, player))
        assert packet is not None
        assert packet.data == CarDamage(*parsed)


@pytest.mark.parametrize("packet_format", FORMATS_UNDER_TEST)
def test_lap_data_combines_minutes_and_millis(packet_format: int) -> None:
    tail = (1234.5, 5678.25, 0.0, 3, 4, 0, 1, 2, True, 5, 3, 2, 0, 1, 7, 1, 2)
    raw = (92345, 45000, 30500, 1, 25250, 0, 1500, 0, 65000, 2, *tail, True, 100, 200, False, 320.5, 2)
    expected = LapData(92345, 45000, 90500, 25250, 1500, 185000, *tail)
    dispatcher = make_dispatcher()
    for player in players(packet_format):
        packet = dispatcher.parse(build_packet(packet_format, PacketId.LAP_DATA, FULL_LAP, raw, player))
        assert packet is not None
        assert packet.data == expected
