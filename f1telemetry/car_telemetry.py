"""CarTelemetry (packet 6): speed, inputs, RPM and tyre/brake temperatures for the player car.

Layouts cross-checked with volodymyr-fed/F1Game.UDP v25.1.1 (format 2025) and v26.0.0 (format 2026).
Format 2026 shrinks engineTemperature from u16 to u8, so each car slot is 59 bytes instead of 60.
Tyre arrays are ordered RL, RR, FL, FR.
"""

from __future__ import annotations

import struct
from typing import NamedTuple

from f1telemetry.packets import PacketDispatcher, PacketHeader, PacketId, player_car_offset

# The unread tail of each slot is the 4-byte surface type array; the 2 skipped bytes are revLightsBitValue.
CAR_SIZES = {2025: 60, 2026: 59}
CAR_TELEMETRY = {
    2025: struct.Struct("<HfffBbH?Bxx4H4B4BH4f"),
    2026: struct.Struct("<HfffBbH?Bxx4H4B4BB4f"),
}


class CarTelemetry(NamedTuple):
    speed: int  # km/h
    throttle: float  # 0.0-1.0
    steer: float  # -1.0 (full left) to 1.0 (full right)
    brake: float  # 0.0-1.0
    clutch: int  # 0-100
    gear: int  # -1 reverse, 0 neutral, 1-8
    engine_rpm: int
    drs: bool
    rev_lights_percent: int
    brake_temperature_rl: int  # celsius
    brake_temperature_rr: int
    brake_temperature_fl: int
    brake_temperature_fr: int
    tyre_surface_temperature_rl: int  # celsius
    tyre_surface_temperature_rr: int
    tyre_surface_temperature_fl: int
    tyre_surface_temperature_fr: int
    tyre_inner_temperature_rl: int  # celsius
    tyre_inner_temperature_rr: int
    tyre_inner_temperature_fl: int
    tyre_inner_temperature_fr: int
    engine_temperature: int  # celsius
    tyre_pressure_rl: float  # PSI
    tyre_pressure_rr: float
    tyre_pressure_fl: float
    tyre_pressure_fr: float


def parse_car_telemetry(header: PacketHeader, data: bytes) -> CarTelemetry | None:
    offset = player_car_offset(header, CAR_SIZES[header.packet_format])
    if offset is None:
        return None
    return CarTelemetry._make(CAR_TELEMETRY[header.packet_format].unpack_from(data, offset))


def register(dispatcher: PacketDispatcher) -> None:
    dispatcher.register(PacketId.CAR_TELEMETRY, parse_car_telemetry)
