"""Replay an `.f1raw` recording to a UDP port with its original timing, standing in for the game."""

from __future__ import annotations

import socket
import time
from pathlib import Path

from f1telemetry.rawfile import read_records

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 20777


def replay(path: Path, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, speed: float = 1.0) -> int:
    """Send every datagram at `t / speed` after start; returns the packet count."""
    if speed <= 0:
        raise ValueError("speed must be > 0")
    count = 0
    clock = time.perf_counter_ns
    sleep = time.sleep
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect((host, port))
        send = sock.send
        start = clock()
        for t_ns, data in read_records(path):
            delay_ns = start + int(t_ns / speed) - clock()
            if delay_ns > 0:
                sleep(delay_ns / 1e9)
            try:  # noqa: SIM105 - plain try/except avoids a context manager per packet
                send(data)
            except ConnectionRefusedError:
                # Windows reports ICMP port-unreachable from earlier sends; nobody listening is fine.
                pass
            count += 1
    return count
