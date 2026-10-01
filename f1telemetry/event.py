"""Event (packet 3): the event codes session and lap tracking need. Same 45-byte layout in 2025 and 2026.

Layout cross-checked with volodymyr-fed/F1Game.UDP v25.1.1 and v26.0.0.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import NamedTuple

from f1telemetry.packets import HEADER, PacketDispatcher, PacketHeader, PacketId

CODE_OFFSET = HEADER.size
DETAILS_OFFSET = CODE_OFFSET + 4
FASTEST_LAP = struct.Struct("<Bf")
FLASHBACK = struct.Struct("<If")
SAFETY_CAR = struct.Struct("<BB")
SAFETY_CAR_RESUME_RACE = 3  # event type; the others are 0 deployed, 1 returning, 2 returned


# Plain classes, not empty NamedTuples: an empty tuple is falsy, which would break `if event:` checks.
@dataclass(frozen=True, slots=True)
class SessionStarted:
    pass


@dataclass(frozen=True, slots=True)
class SessionEnded:
    pass


class FastestLap(NamedTuple):
    vehicle_index: int
    lap_time: float


class Flashback(NamedTuple):
    frame_identifier: int
    session_time: float


@dataclass(frozen=True, slots=True)
class RedFlag:
    pass


class SafetyCar(NamedTuple):
    safety_car_type: int  # 0 none, 1 full, 2 virtual, 3 formation lap
    event_type: int  # 0 deployed, 1 returning, 2 returned, 3 resume race


type Event = SessionStarted | SessionEnded | FastestLap | Flashback | RedFlag | SafetyCar

SESSION_STARTED = SessionStarted()
SESSION_ENDED = SessionEnded()
RED_FLAG = RedFlag()


def parse_event(header: PacketHeader, data: bytes) -> Event | None:
    """Decode SSTA, SEND, FTLP, FLBK, SCAR and RDFL; every other event code returns None."""
    code = data[CODE_OFFSET:DETAILS_OFFSET]
    if code == b"FLBK":
        return Flashback._make(FLASHBACK.unpack_from(data, DETAILS_OFFSET))
    if code == b"FTLP":
        return FastestLap._make(FASTEST_LAP.unpack_from(data, DETAILS_OFFSET))
    if code == b"SSTA":
        return SESSION_STARTED
    if code == b"SEND":
        return SESSION_ENDED
    if code == b"SCAR":
        return SafetyCar._make(SAFETY_CAR.unpack_from(data, DETAILS_OFFSET))
    if code == b"RDFL":
        return RED_FLAG
    return None


def register(dispatcher: PacketDispatcher) -> None:
    dispatcher.register(PacketId.EVENT, parse_event)
