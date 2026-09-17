"""Session (packet 1): track, session type, formula and weather, plus 2026 active aero zones.

Layouts cross-checked with volodymyr-fed/F1Game.UDP v25.1.1 (format 2025) and v26.0.0 (format 2026).
The first 753 bytes are identical in both formats; 2026 appends active aero, DRS zone and assist data.
"""

from __future__ import annotations

import struct
from typing import NamedTuple

from f1telemetry.packets import FORMATS, HEADER, PacketDispatcher, PacketHeader, PacketId

SESSION_INFO = struct.Struct("<BbbBHBbBHHB??")
SECTOR_STARTS = struct.Struct("<ff")
# Sector starts are the last field of the 2025 packet; 2026 appends active aero data after them.
AERO_STATUS_OFFSET = FORMATS[2025].packet_sizes[PacketId.SESSION]
SECTOR_STARTS_OFFSET = AERO_STATUS_OFFSET - SECTOR_STARTS.size

MAX_ACTIVE_AERO_ZONES = 8
AERO_STATUS = struct.Struct("<BB")
AERO_ZONES = struct.Struct(f"<{MAX_ACTIVE_AERO_ZONES * 2}f")
AERO_ZONES_FULL_OFFSET = AERO_STATUS_OFFSET + AERO_STATUS.size
AERO_ZONES_PARTIAL_COUNT_OFFSET = AERO_ZONES_FULL_OFFSET + AERO_ZONES.size
AERO_ZONES_PARTIAL_OFFSET = AERO_ZONES_PARTIAL_COUNT_OFFSET + 1

type Zone = tuple[float, float]


class Session(NamedTuple):
    weather: int
    track_temperature: int
    air_temperature: int
    total_laps: int
    track_length: int
    session_type: int
    track_id: int
    formula: int
    session_time_left: int
    session_duration: int
    pit_speed_limit: int
    game_paused: bool
    is_spectating: bool
    sector2_lap_distance_start: float
    sector3_lap_distance_start: float
    # Format 2026 only; None / empty in 2025. Zone bounds are fractions of the lap.
    active_aero_track_status: int | None
    active_aero_zones_full: tuple[Zone, ...]
    active_aero_zones_partial: tuple[Zone, ...]


def _zones(data: bytes, offset: int, count: int) -> tuple[Zone, ...]:
    values = AERO_ZONES.unpack_from(data, offset)
    count = min(count, MAX_ACTIVE_AERO_ZONES)
    return tuple((values[2 * i], values[2 * i + 1]) for i in range(count))


def parse_session(header: PacketHeader, data: bytes) -> Session:
    (
        weather,
        track_temperature,
        air_temperature,
        total_laps,
        track_length,
        session_type,
        track_id,
        formula,
        session_time_left,
        session_duration,
        pit_speed_limit,
        game_paused,
        is_spectating,
    ) = SESSION_INFO.unpack_from(data, HEADER.size)
    sector2, sector3 = SECTOR_STARTS.unpack_from(data, SECTOR_STARTS_OFFSET)
    status: int | None = None
    full: tuple[Zone, ...] = ()
    partial: tuple[Zone, ...] = ()
    if header.packet_format >= 2026:
        status, full_count = AERO_STATUS.unpack_from(data, AERO_STATUS_OFFSET)
        full = _zones(data, AERO_ZONES_FULL_OFFSET, full_count)
        partial = _zones(data, AERO_ZONES_PARTIAL_OFFSET, data[AERO_ZONES_PARTIAL_COUNT_OFFSET])
    return Session(
        weather,
        track_temperature,
        air_temperature,
        total_laps,
        track_length,
        session_type,
        track_id,
        formula,
        session_time_left,
        session_duration,
        pit_speed_limit,
        game_paused,
        is_spectating,
        sector2,
        sector3,
        status,
        full,
        partial,
    )


def register(dispatcher: PacketDispatcher) -> None:
    dispatcher.register(PacketId.SESSION, parse_session)
