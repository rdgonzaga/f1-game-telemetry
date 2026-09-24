"""SessionHistory parsing from hand-packed packets."""

from __future__ import annotations

import struct

import pytest

from f1telemetry.packets import FORMATS, HEADER, PacketHeader, PacketId
from f1telemetry.parsers import make_dispatcher
from f1telemetry.session_history import SessionHistory

PLAYER = 3


def packet(packet_format: int, car_index: int, lap_times: list[int]) -> bytes:
    header = HEADER.pack(
        *PacketHeader(packet_format, 25, 1, 26, 1, PacketId.SESSION_HISTORY, 1, 3.0, 10, 10, PLAYER, 255)
    )
    body = bytearray(FORMATS[packet_format].packet_sizes[PacketId.SESSION_HISTORY] - HEADER.size)
    struct.pack_into("<BBBBBBB", body, 0, car_index, len(lap_times), 1, 1, 1, 1, 1)
    for i, lap_time in enumerate(lap_times):
        # lapTimeInMS, then sector times and valid flags that must not leak into the lap time.
        struct.pack_into("<IHBHBHBB", body, 7 + i * 14, lap_time, 0xFFFF, 0xFF, 0xFFFF, 0xFF, 0xFFFF, 0xFF, 0x0F)
    return header + bytes(body)


@pytest.mark.parametrize("packet_format", [2025, 2026])
def test_player_lap_times_decode_in_both_formats(packet_format: int) -> None:
    parsed = make_dispatcher().parse(packet(packet_format, PLAYER, [91_359, 103_822, 0]))

    assert parsed is not None
    assert parsed.data == SessionHistory((91_359, 103_822, 0))


def test_other_cars_are_not_decoded() -> None:
    parsed = make_dispatcher().parse(packet(2026, PLAYER + 1, [90_000]))

    assert parsed is not None
    assert parsed.data is None
