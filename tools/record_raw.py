"""Record raw F1 game UDP packets to an `.f1raw` file.

Usage: uv run python tools/record_raw.py [--out recordings/x.f1raw] [--host 127.0.0.1] [--port 20777]
"""

from __future__ import annotations

import argparse
import signal
import socket
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
) -> int:
    """Record until `stop` is set or KeyboardInterrupt; returns the packet count."""
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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, help="output file (default: recordings/<timestamp>.f1raw)")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    out = args.out or Path("recordings") / f"{datetime.now():%Y%m%d-%H%M%S}.f1raw"
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, signal.default_int_handler)

    print(f"Recording {args.host}:{args.port} -> {out} (Ctrl+C to stop)")
    count = record(out, args.host, args.port)
    print(f"Saved {count} packets to {out}")


if __name__ == "__main__":
    main()
