"""LapData (packet 2): lap timing, distance and validity for the player car. Same 57-byte car slot in 2025 and 2026.

Layout cross-checked with volodymyr-fed/F1Game.UDP v25.1.1 and v26.0.0.
"""

from __future__ import annotations

import struct
from typing import NamedTuple

from f1telemetry.packets import PacketDispatcher, PacketHeader, PacketId, player_car_offset

CAR_SIZE = 57
# Stops after resultStatus; the unread tail is pit lane timers and speed trap data.
LAP_DATA = struct.Struct("<IIHBHBHBHBfffBBBBB?BBBBBBBB")


class LapData(NamedTuple):
    last_lap_time_ms: int
    current_lap_time_ms: int
    sector1_time_ms: int
    sector2_time_ms: int
    delta_to_car_in_front_ms: int
    delta_to_race_leader_ms: int
    lap_distance: float  # metres; can be negative before crossing the line
    total_distance: float  # metres
    safety_car_delta: float  # seconds
    car_position: int
    current_lap_num: int
    pit_status: int  # 0 none, 1 pitting, 2 in pit area
    num_pit_stops: int
    sector: int  # 0 = sector 1
    current_lap_invalid: bool
    penalties: int  # seconds
    total_warnings: int
    corner_cutting_warnings: int
    unserved_drive_through_pens: int
    unserved_stop_go_pens: int
    grid_position: int
    driver_status: int  # 0 garage, 1 flying lap, 2 in lap, 3 out lap, 4 on track
    result_status: int


def parse_lap_data(header: PacketHeader, data: bytes) -> LapData | None:
    offset = player_car_offset(header, CAR_SIZE)
    if offset is None:
        return None
    (
        last_lap_time_ms,
        current_lap_time_ms,
        sector1_ms,
        sector1_minutes,
        sector2_ms,
        sector2_minutes,
        front_ms,
        front_minutes,
        leader_ms,
        leader_minutes,
        *rest,
    ) = LAP_DATA.unpack_from(data, offset)
    # The game splits these times into a u16 millisecond part and a u8 minutes part.
    return LapData(
        last_lap_time_ms,
        current_lap_time_ms,
        sector1_minutes * 60_000 + sector1_ms,
        sector2_minutes * 60_000 + sector2_ms,
        front_minutes * 60_000 + front_ms,
        leader_minutes * 60_000 + leader_ms,
        *rest,
    )


def register(dispatcher: PacketDispatcher) -> None:
    dispatcher.register(PacketId.LAP_DATA, parse_lap_data)
