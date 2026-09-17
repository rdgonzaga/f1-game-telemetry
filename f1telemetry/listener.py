"""asyncio UDP listener that parses game packets into a `LiveState` on the running event loop."""

from __future__ import annotations

import asyncio
import logging
import socket
import time

from f1telemetry.live import LiveState
from f1telemetry.packets import PacketDispatcher
from f1telemetry.parsers import make_dispatcher

log = logging.getLogger(__name__)

DEFAULT_UDP_HOST = "127.0.0.1"
DEFAULT_UDP_PORT = 20777
# The game bursts a frame's packets at once; a big receive buffer keeps the kernel from dropping them.
RECV_BUFFER_BYTES = 1 << 20


class TelemetryProtocol(asyncio.DatagramProtocol):
    """Parses each datagram and merges it into `state`; unusable datagrams only count towards connection status."""

    def __init__(self, state: LiveState, dispatcher: PacketDispatcher | None = None) -> None:
        self.state = state
        # Bound once: this runs for every packet at 60 Hz.
        self._parse = (dispatcher or make_dispatcher()).parse
        self._clock = time.monotonic_ns
        self._warned = False

    def datagram_received(self, data: bytes, addr: object) -> None:
        self.state.note_datagram(self._clock())
        packet = self._parse(data)
        if packet is not None:
            self.state.update(packet)

    def error_received(self, exc: Exception) -> None:
        # Windows reports ICMP port-unreachable on UDP sockets; nothing to do but keep listening.
        if not self._warned:
            self._warned = True
            log.warning("UDP socket error, still listening: %s", exc)


async def open_listener(
    state: LiveState,
    host: str = DEFAULT_UDP_HOST,
    port: int = DEFAULT_UDP_PORT,
    dispatcher: PacketDispatcher | None = None,
) -> asyncio.DatagramTransport:
    """Bind a listener on the running loop; the caller closes the returned transport."""
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: TelemetryProtocol(state, dispatcher), local_addr=(host, port)
    )
    sock = transport.get_extra_info("socket")
    if sock is not None:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, RECV_BUFFER_BYTES)
    return transport
