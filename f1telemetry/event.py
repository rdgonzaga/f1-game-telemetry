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


type Event = SessionStarted | SessionEnded | FastestLap | Flashback

SESSION_STARTED = SessionStarted()
SESSION_ENDED = SessionEnded()


def parse_event(header: PacketHeader, data: bytes) -> Event | None:
    """Decode SSTA, SEND, FTLP and FLBK; every other event code returns None."""
    code = data[CODE_OFFSET:DETAILS_OFFSET]
    if code == b"FLBK":
        return Flashback._make(FLASHBACK.unpack_from(data, DETAILS_OFFSET))
    if code == b"FTLP":
        return FastestLap._make(FASTEST_LAP.unpack_from(data, DETAILS_OFFSET))
    if code == b"SSTA":
        return SESSION_STARTED
    if code == b"SEND":
        return SESSION_ENDED
    return None


def register(dispatcher: PacketDispatcher) -> None:
    dispatcher.register(PacketId.EVENT, parse_event)
