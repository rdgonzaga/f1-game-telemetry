"""Motion (packet 0): the player car's world position. Only the first three floats of the car slot are read.

The slot is 60 bytes in 2025 and 54 in 2026 (packet size less the header, over 22 and 24 cars). Position leads the
slot in both: at the same lap distance the parsed positions agree lap to lap within a few metres in both formats.
"""

from __future__ import annotations

import struct
from typing import NamedTuple

from f1telemetry.packets import PacketDispatcher, PacketHeader, PacketId, player_car_offset

CAR_SIZES = {2025: 60, 2026: 54}
POSITION = struct.Struct("<3f")


class Motion(NamedTuple):
    world_x: float  # metres
    world_y: float  # metres, height
    world_z: float  # metres


def parse_motion(header: PacketHeader, data: bytes) -> Motion | None:
    offset = player_car_offset(header, CAR_SIZES[header.packet_format])
    if offset is None:
        return None
    return Motion._make(POSITION.unpack_from(data, offset))


def register(dispatcher: PacketDispatcher) -> None:
    dispatcher.register(PacketId.MOTION, parse_motion)
