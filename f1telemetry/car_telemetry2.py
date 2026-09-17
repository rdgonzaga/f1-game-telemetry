"""CarTelemetry2 (packet 16): active aero and overtake mode state, format 2026 only.

Layout cross-checked with volodymyr-fed/F1Game.UDP v26.0.0.
"""

from __future__ import annotations

import struct
from enum import IntEnum
from typing import NamedTuple

from f1telemetry.packets import FORMATS, HEADER, PacketDispatcher, PacketHeader, PacketId

CAR_TELEMETRY_2 = struct.Struct("<B?H??H??")
FORMAT = 2026


class ActiveAeroMode(IntEnum):
    CORNER = 0
    STRAIGHT = 1


class CarTelemetry2(NamedTuple):
    active_aero_mode: int
    active_aero_available: bool
    active_aero_activation_distance: int
    overtake_available: bool
    overtake_active: bool
    overtake_activation_distance: int
    regulations_2026_applicable: bool
    is_driving_wrong_way: bool


def parse_car_telemetry2(header: PacketHeader, data: bytes) -> CarTelemetry2 | None:
    """Decode the player car's entry; None when there is no player car (e.g. spectating)."""
    index = header.player_car_index
    if index >= FORMATS[FORMAT].max_cars:
        return None
    return CarTelemetry2._make(CAR_TELEMETRY_2.unpack_from(data, HEADER.size + index * CAR_TELEMETRY_2.size))


def register(dispatcher: PacketDispatcher) -> None:
    dispatcher.register(PacketId.CAR_TELEMETRY_2, parse_car_telemetry2, formats=[FORMAT])
