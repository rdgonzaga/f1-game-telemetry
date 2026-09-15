"""Replay an `.f1raw` recording to a UDP port with original timing.

Usage: uv run python tools/replay_raw.py recordings/x.f1raw [--speed 2] [--host 127.0.0.1] [--port 20777]
"""

from __future__ import annotations

import argparse
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", type=Path)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--speed", type=float, default=1.0, help="playback multiplier (2 = twice as fast)")
    args = parser.parse_args(argv)

    if args.speed <= 0:
        parser.error("--speed must be > 0")

    print(f"Replaying {args.path} -> {args.host}:{args.port} at {args.speed}x (Ctrl+C to stop)")
    try:
        count = replay(args.path, args.host, args.port, args.speed)
    except KeyboardInterrupt:
        print("Stopped")
        return
    print(f"Sent {count} packets")


if __name__ == "__main__":
    main()
