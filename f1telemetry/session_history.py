"""SessionHistory (packet 11): the player car's lap times so far. Same 1460-byte layout in 2025 and 2026.

The game sends one car per packet in rotation, about once a second each, so only the player's packets are decoded.
Its last one for a session arrives with `sessionUID` 0 just before SEND and holds the final lap's time, which a
low UDP send rate can miss in LapData.

Layout cross-checked with volodymyr-fed/F1Game.UDP v25.1.1 and v26.0.0.
"""

from __future__ import annotations

import struct
from typing import NamedTuple

from f1telemetry.packets import HEADER, PacketDispatcher, PacketHeader, PacketId

# carIdx, numLaps; the rest of the 7-byte prefix is tyre stint count and best-lap/sector lap numbers.
PREFIX = struct.Struct("<BB")
LAPS_OFFSET = HEADER.size + 7
# lapTimeInMS; the unread 10 bytes are sector times and the lap valid flags.
LAP = struct.Struct("<I10x")
MAX_LAPS = 100


class SessionHistory(NamedTuple):
    lap_times_ms: tuple[int, ...]  # index 0 is lap 1; 0 while a lap is unfinished


def parse_session_history(header: PacketHeader, data: bytes) -> SessionHistory | None:
    """Decode the player car's lap times; None for every other car."""
    car_index, num_laps = PREFIX.unpack_from(data, HEADER.size)
    if car_index != header.player_car_index:
        return None
    unpack = LAP.unpack_from
    return SessionHistory(tuple(unpack(data, LAPS_OFFSET + i * LAP.size)[0] for i in range(min(num_laps, MAX_LAPS))))


def register(dispatcher: PacketDispatcher) -> None:
    dispatcher.register(PacketId.SESSION_HISTORY, parse_session_history)
