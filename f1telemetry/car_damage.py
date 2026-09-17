"""CarDamage (packet 10): tyre wear and damage for the player car. Same 46-byte car slot in 2025 and 2026.

Layout cross-checked with volodymyr-fed/F1Game.UDP v25.1.1 and v26.0.0. Tyre arrays are ordered RL, RR, FL, FR.
"""

from __future__ import annotations

import struct
from typing import NamedTuple

from f1telemetry.packets import PacketDispatcher, PacketHeader, PacketId, player_car_offset

CAR_SIZE = 46
# Stops after engineDamage; the unread tail is per-component engine wear and blown/seized flags.
CAR_DAMAGE = struct.Struct("<4f4B4B4B6B??BB")


class CarDamage(NamedTuple):
    tyre_wear_rl: float  # percent
    tyre_wear_rr: float
    tyre_wear_fl: float
    tyre_wear_fr: float
    tyre_damage_rl: int  # percent
    tyre_damage_rr: int
    tyre_damage_fl: int
    tyre_damage_fr: int
    brake_damage_rl: int  # percent
    brake_damage_rr: int
    brake_damage_fl: int
    brake_damage_fr: int
    tyre_blisters_rl: int  # percent
    tyre_blisters_rr: int
    tyre_blisters_fl: int
    tyre_blisters_fr: int
    front_left_wing_damage: int  # percent
    front_right_wing_damage: int
    rear_wing_damage: int
    floor_damage: int
    diffuser_damage: int
    sidepod_damage: int
    drs_fault: bool
    ers_fault: bool
    gearbox_damage: int  # percent
    engine_damage: int  # percent


def parse_car_damage(header: PacketHeader, data: bytes) -> CarDamage | None:
    offset = player_car_offset(header, CAR_SIZE)
    if offset is None:
        return None
    return CarDamage._make(CAR_DAMAGE.unpack_from(data, offset))


def register(dispatcher: PacketDispatcher) -> None:
    dispatcher.register(PacketId.CAR_DAMAGE, parse_car_damage)
