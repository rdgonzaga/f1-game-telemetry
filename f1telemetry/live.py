"""The merged live picture of the player car: the latest data from each packet type the parsers handle.

Kept grouped per packet type rather than flattened, so nothing is rebuilt per packet; the API flattens for the
wire. Callers pass the current `time.monotonic_ns()` in, so tests can drive freshness without sleeping.
"""

from __future__ import annotations

from f1telemetry.car_damage import CarDamage
from f1telemetry.car_status import CarStatus
from f1telemetry.car_telemetry import CarTelemetry
from f1telemetry.car_telemetry2 import CarTelemetry2
from f1telemetry.lap_data import LapData
from f1telemetry.packets import Packet, PacketId
from f1telemetry.session import Session

NS_PER_SECOND = 1_000_000_000
# ~60 packets a second are expected at the game's default rate, so a second of silence means paused or stopped.
CONNECTED_TIMEOUT_NS = NS_PER_SECOND

# Packet id -> attribute holding its latest payload. Events are not stored; session and lap tracking consumes them.
PACKET_SLOTS: dict[int, str] = {
    PacketId.SESSION: "session",
    PacketId.LAP_DATA: "lap",
    PacketId.CAR_TELEMETRY: "telemetry",
    PacketId.CAR_STATUS: "status",
    PacketId.CAR_DAMAGE: "damage",
    PacketId.CAR_TELEMETRY_2: "telemetry2",
}


class LiveState:
    __slots__ = (
        "_rate_count",
        "_rate_started_ns",
        "damage",
        "lap",
        "last_packet_ns",
        "packet_format",
        "packets_per_second",
        "packets_seen",
        "player_index",
        "session",
        "session_uid",
        "status",
        "telemetry",
        "telemetry2",
    )

    def __init__(self) -> None:
        self.session_uid: int | None = None
        self.packet_format: int | None = None
        self.player_index: int | None = None
        self.last_packet_ns: int | None = None
        self.packets_seen = 0
        self.packets_per_second = 0
        self._rate_started_ns: int | None = None
        self._rate_count = 0
        self.clear_packets()

    def clear_packets(self) -> None:
        """Forget the stored packets, keeping the counters."""
        self.session: Session | None = None
        self.lap: LapData | None = None
        self.telemetry: CarTelemetry | None = None
        self.status: CarStatus | None = None
        self.damage: CarDamage | None = None
        self.telemetry2: CarTelemetry2 | None = None

    def note_datagram(self, now_ns: int) -> None:
        """Record that a datagram arrived, parsed or not, so connection status tracks the socket and not the parsers."""
        self.last_packet_ns = now_ns
        self.packets_seen += 1
        if self._rate_started_ns is None or now_ns - self._rate_started_ns >= NS_PER_SECOND:
            self.packets_per_second = self._rate_count
            self._rate_started_ns = now_ns
            self._rate_count = 1
        else:
            self._rate_count += 1

    def update(self, packet: Packet) -> None:
        """Store a parsed packet's payload. A payload of None (no player car) only updates the header fields."""
        header = packet.header
        if header.session_uid != self.session_uid:
            # A new session, or a switch between UDP format 2025 and 2026, must not be read as a mix of both.
            self.session_uid = header.session_uid
            self.clear_packets()
        self.packet_format = header.packet_format
        self.player_index = header.player_car_index
        if packet.data is None:
            return
        slot = PACKET_SLOTS.get(header.packet_id)
        if slot is not None:
            setattr(self, slot, packet.data)

    def connected(self, now_ns: int) -> bool:
        """True while a datagram arrived within the last second."""
        return self.last_packet_ns is not None and now_ns - self.last_packet_ns < CONNECTED_TIMEOUT_NS
