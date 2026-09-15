"""Packet header parsing and format-aware dispatch for F1 25 UDP formats 2025 and 2026.

Layouts cross-checked with volodymyr-fed/F1Game.UDP v25.1.1 (format 2025) and v26.0.0 (format 2026).
"""

from __future__ import annotations

import logging
import struct
from collections.abc import Callable, Iterable
from enum import IntEnum
from typing import NamedTuple

log = logging.getLogger(__name__)

HEADER = struct.Struct("<HBBBBBQfIIBB")
PACKET_ID_OFFSET = 6


class PacketId(IntEnum):
    MOTION = 0
    SESSION = 1
    LAP_DATA = 2
    EVENT = 3
    PARTICIPANTS = 4
    CAR_SETUPS = 5
    CAR_TELEMETRY = 6
    CAR_STATUS = 7
    FINAL_CLASSIFICATION = 8
    LOBBY_INFO = 9
    CAR_DAMAGE = 10
    SESSION_HISTORY = 11
    TYRE_SETS = 12
    MOTION_EX = 13
    TIME_TRIAL = 14
    LAP_POSITIONS = 15
    CAR_TELEMETRY_2 = 16


class PacketHeader(NamedTuple):
    packet_format: int
    game_year: int
    game_major_version: int
    game_minor_version: int
    packet_version: int
    packet_id: int
    session_uid: int
    session_time: float
    frame_identifier: int
    overall_frame_identifier: int
    player_car_index: int
    secondary_player_car_index: int


class FormatSpec(NamedTuple):
    max_cars: int
    packet_sizes: dict[int, int]


FORMATS: dict[int, FormatSpec] = {
    2025: FormatSpec(
        max_cars=22,
        packet_sizes={
            PacketId.MOTION: 1349,
            PacketId.SESSION: 753,
            PacketId.LAP_DATA: 1285,
            PacketId.EVENT: 45,
            PacketId.PARTICIPANTS: 1284,
            PacketId.CAR_SETUPS: 1133,
            PacketId.CAR_TELEMETRY: 1352,
            PacketId.CAR_STATUS: 1239,
            PacketId.FINAL_CLASSIFICATION: 1042,
            PacketId.LOBBY_INFO: 954,
            PacketId.CAR_DAMAGE: 1041,
            PacketId.SESSION_HISTORY: 1460,
            PacketId.TYRE_SETS: 231,
            PacketId.MOTION_EX: 273,
            PacketId.TIME_TRIAL: 101,
            PacketId.LAP_POSITIONS: 1131,
        },
    ),
    2026: FormatSpec(
        max_cars=24,
        packet_sizes={
            PacketId.MOTION: 1325,
            PacketId.SESSION: 926,
            PacketId.LAP_DATA: 1399,
            PacketId.EVENT: 45,
            PacketId.PARTICIPANTS: 1470,
            PacketId.CAR_SETUPS: 1233,
            PacketId.CAR_TELEMETRY: 1448,
            PacketId.CAR_STATUS: 1445,
            PacketId.FINAL_CLASSIFICATION: 1134,
            PacketId.LOBBY_INFO: 1062,
            PacketId.CAR_DAMAGE: 1133,
            PacketId.SESSION_HISTORY: 1460,
            PacketId.TYRE_SETS: 231,
            PacketId.MOTION_EX: 273,
            PacketId.TIME_TRIAL: 104,
            PacketId.LAP_POSITIONS: 1231,
            PacketId.CAR_TELEMETRY_2: 269,
        },
    ),
}

type Parser = Callable[[PacketHeader, bytes], object]


class Packet(NamedTuple):
    header: PacketHeader
    data: object


class PacketDispatcher:
    """Routes raw datagrams to parsers registered per packet format and packet id."""

    def __init__(self) -> None:
        self._routes: dict[int, dict[int, tuple[Parser, int]]] = {fmt: {} for fmt in FORMATS}
        self._warned: set[tuple[object, ...]] = set()

    def register(self, packet_id: PacketId, parser: Parser, formats: Iterable[int] | None = None) -> None:
        """Register `parser` for `packet_id`; by default for every format that defines that packet."""
        if formats is None:
            targets = [fmt for fmt, spec in FORMATS.items() if packet_id in spec.packet_sizes]
        else:
            targets = list(formats)
            for fmt in targets:
                if fmt not in FORMATS or packet_id not in FORMATS[fmt].packet_sizes:
                    raise ValueError(f"packet {packet_id.name} does not exist in format {fmt}")
        for fmt in targets:
            self._routes[fmt][packet_id] = (parser, FORMATS[fmt].packet_sizes[packet_id])

    def parse(self, data: bytes) -> Packet | None:
        """Return a parsed packet, or None for unused, unknown or malformed datagrams."""
        size = len(data)
        if size < HEADER.size:
            self._warn_once(("short",), "dropping %d-byte datagram shorter than the packet header", size)
            return None

        fmt = data[0] | data[1] << 8
        routes = self._routes.get(fmt)
        if routes is None:
            self._warn_once(
                ("format", fmt), "ignoring unsupported packet format %d (set UDP Format to 2025 or 2026)", fmt
            )
            return None

        route = routes.get(data[PACKET_ID_OFFSET])
        if route is None:
            return None

        parser, expected = route
        if size != expected:
            packet_id = data[PACKET_ID_OFFSET]
            self._warn_once(
                ("size", fmt, packet_id),
                "dropping format %d packet %d: expected %d bytes, got %d",
                fmt,
                packet_id,
                expected,
                size,
            )
            return None

        header = PacketHeader._make(HEADER.unpack_from(data))
        return Packet(header, parser(header, data))

    def _warn_once(self, key: tuple[object, ...], message: str, *args: object) -> None:
        if key not in self._warned:
            self._warned.add(key)
            log.warning(message, *args)
