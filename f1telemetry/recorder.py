"""Record raw game UDP packets to an `.f1raw` file, for replaying and testing without the game.

`record` owns the UDP port (the `f1telemetry record` command); `RawSink` takes packets from the app's listener, so
a race can be watched on the dashboard and recorded at once.
"""

from __future__ import annotations

import logging
import queue
import socket
import threading
import time
from datetime import datetime
from pathlib import Path

from f1telemetry.rawfile import MAX_DATAGRAM, RawWriter

log = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 20777
# Short timeout keeps the loop responsive to stop requests; Windows won't interrupt a blocking recv.
POLL_TIMEOUT_S = 0.2
# A longer silence (menus, loading) is closed up to this in the file, so a replay doesn't sit through it.
MAX_GAP_NS = 1_000_000_000


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


class RawSink:
    """Keeps every datagram the app receives in a new `.f1raw` file in `folder`, created on the first packet.

    `add` runs on the event loop for every packet, so it only stamps the time and queues; a thread does the writing.
    """

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.path: Path | None = None
        self._queue: queue.SimpleQueue[tuple[int, bytes] | None] = queue.SimpleQueue()
        self._thread: threading.Thread | None = None
        self._failed = False
        self._clock = time.perf_counter_ns  # monotonic_ns ticks every 15.6 ms on Windows; replay needs better
        self._last = 0
        self._shift = 0  # start time plus the silence cut out so far

    def add(self, data: bytes) -> None:
        if self._failed:
            return
        now = self._clock()
        if self._thread is None:
            self._shift = now
            self.path = self.folder / f"{datetime.now():%Y%m%d-%H%M%S}.f1raw"
            self._thread = threading.Thread(target=self._write, args=(self.path,), name="raw-recording", daemon=True)
            self._thread.start()
            log.info("Recording raw packets to %s", self.path)
        elif now - self._last > MAX_GAP_NS:
            self._shift += now - self._last - MAX_GAP_NS
        self._last = now
        self._queue.put((now - self._shift, data))

    def close(self) -> None:
        """Write what is queued and close the file. Blocks, so async callers run it in a thread."""
        if self._thread is not None:
            self._queue.put(None)
            self._thread.join()
            self._thread = None

    def _write(self, path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with RawWriter(path) as writer:
                while (record := self._queue.get()) is not None:
                    writer.write(*record)
        except OSError as error:
            # Disk full or the folder gone: stop queueing rather than hold every packet in memory.
            self._failed = True
            log.error("Raw recording stopped, %s: %s", path, error)
