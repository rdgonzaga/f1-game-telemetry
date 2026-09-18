"""Record raw game UDP packets to an `.f1raw` file, for replaying and testing without the game."""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

from f1telemetry.rawfile import MAX_DATAGRAM, RawWriter

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 20777
# Short timeout keeps the loop responsive to stop requests; Windows won't interrupt a blocking recv.
POLL_TIMEOUT_S = 0.2


def record(
    out: Path,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    stop: threading.Event | None = None,
    ready: threading.Event | None = None,
    overwrite: bool = False,
) -> int:
    """Record until `stop` is set or KeyboardInterrupt; returns the packet count.

    Raises FileExistsError rather than replacing an earlier recording, unless `overwrite` is set.
    """
    if out.exists() and not overwrite:
        raise FileExistsError(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with (
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock,
        RawWriter(out) as writer,
    ):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)
        sock.bind((host, port))
        sock.settimeout(POLL_TIMEOUT_S)
        if ready is not None:
            ready.set()

        recv = sock.recv
        clock = time.perf_counter_ns
        start: int | None = None
        try:
            while stop is None or not stop.is_set():
                try:
                    data = recv(MAX_DATAGRAM)
                except TimeoutError:
                    continue
                now = clock()
                if start is None:
                    start = now
                writer.write(now - start, data)
        except KeyboardInterrupt:
            pass
        return writer.count
