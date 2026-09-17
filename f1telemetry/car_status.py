"""CarStatus (packet 7): fuel, tyre compound and ERS state for the player car.

Layouts cross-checked with volodymyr-fed/F1Game.UDP v25.1.1 (format 2025) and v26.0.0 (format 2026).
Format 2026 inserts ersHarvestLimitPerLap before ersDeployedThisLap, so each car slot is 59 bytes instead of 55.
"""

from __future__ import annotations

import struct
from typing import NamedTuple

from f1telemetry.packets import PacketDispatcher, PacketHeader, PacketId, player_car_offset

CAR_SIZES = {2025: 55, 2026: 59}
# Shared by both formats: tractionControl through ersHarvestedThisLapMGUH.
CAR_STATUS = struct.Struct("<BBBB?fffHHB?HBBBbfffBff")
ERS_TAIL_OFFSET = CAR_STATUS.size
ERS_TAIL_2025 = struct.Struct("<f")  # ersDeployedThisLap
ERS_TAIL_2026 = struct.Struct("<ff")  # ersHarvestLimitPerLap, ersDeployedThisLap


class CarStatus(NamedTuple):
    traction_control: int
    anti_lock_brakes: bool
    fuel_mix: int  # 0 lean, 1 standard, 2 rich, 3 max
    front_brake_bias: int  # percent
    pit_limiter: bool
    fuel_in_tank: float  # kg
    fuel_capacity: float  # kg
    fuel_remaining_laps: float
    max_rpm: int
    idle_rpm: int
    max_gears: int
    drs_allowed: bool
    drs_activation_distance: int  # metres, 0 when not available
    actual_tyre_compound: int
    visual_tyre_compound: int
    tyres_age_laps: int
    fia_flag: int  # -1 unknown, 0 none, 1 green, 2 blue, 3 yellow
    engine_power_ice: float  # watts
    engine_power_mguk: float  # watts
    ers_store_energy: float  # joules
    ers_deploy_mode: int  # see names.ers_deploy_mode_name; mode 3 differs by format
    ers_harvested_this_lap_mguk: float  # joules
    ers_harvested_this_lap_mguh: float  # joules
    ers_deployed_this_lap: float  # joules
    ers_harvest_limit_per_lap: float | None  # joules; format 2026 only


def parse_car_status(header: PacketHeader, data: bytes) -> CarStatus | None:
    fmt = header.packet_format
    offset = player_car_offset(header, CAR_SIZES[fmt])
    if offset is None:
        return None
    (
        traction_control,
        anti_lock_brakes,
        fuel_mix,
        front_brake_bias,
        pit_limiter,
        fuel_in_tank,
        fuel_capacity,
        fuel_remaining_laps,
        max_rpm,
        idle_rpm,
        max_gears,
        drs_allowed,
        drs_activation_distance,
        actual_tyre_compound,
        visual_tyre_compound,
        tyres_age_laps,
        fia_flag,
        engine_power_ice,
        engine_power_mguk,
        ers_store_energy,
        ers_deploy_mode,
        harvested_mguk,
        harvested_mguh,
    ) = CAR_STATUS.unpack_from(data, offset)
    harvest_limit: float | None = None
    if fmt >= 2026:
        harvest_limit, deployed = ERS_TAIL_2026.unpack_from(data, offset + ERS_TAIL_OFFSET)
    else:
        (deployed,) = ERS_TAIL_2025.unpack_from(data, offset + ERS_TAIL_OFFSET)
    return CarStatus(
        traction_control,
        bool(anti_lock_brakes),
        fuel_mix,
        front_brake_bias,
        pit_limiter,
        fuel_in_tank,
        fuel_capacity,
        fuel_remaining_laps,
        max_rpm,
        idle_rpm,
        max_gears,
        drs_allowed,
        drs_activation_distance,
        actual_tyre_compound,
        visual_tyre_compound,
        tyres_age_laps,
        fia_flag,
        engine_power_ice,
        engine_power_mguk,
        ers_store_energy,
        ers_deploy_mode,
        harvested_mguk,
        harvested_mguh,
        deployed,
        harvest_limit,
    )


def register(dispatcher: PacketDispatcher) -> None:
    dispatcher.register(PacketId.CAR_STATUS, parse_car_status)
