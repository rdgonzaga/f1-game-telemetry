"""Benchmark packet parsing on `.f1raw` recordings and report the time per packet type.

Usage: uv run python tools/bench_parse.py [recordings/x.f1raw ...] [--rounds 5] [--budget-us 50]
With no paths, every fixture in tests/fixtures is used.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from f1telemetry.packets import HEADER, PACKET_ID_OFFSET, PacketId
from f1telemetry.parsers import make_dispatcher
from f1telemetry.rawfile import read_records

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
DEFAULT_BUDGET_US = 50.0


class Timing(NamedTuple):
    packet_id: int
    packets: int
    best_ns: float  # fastest round, nanoseconds per packet


def load(paths: list[Path]) -> dict[int, list[bytes]]:
    """Group datagrams by packet id, read up front so disk I/O stays out of the timings."""
    by_id: dict[int, list[bytes]] = defaultdict(list)
    for path in paths:
        for _, data in read_records(path):
            if len(data) >= HEADER.size:
                by_id[data[PACKET_ID_OFFSET]].append(data)
    return by_id


def bench(by_id: dict[int, list[bytes]], rounds: int = 5) -> list[Timing]:
    """Time `PacketDispatcher.parse` per packet id; packets the dispatcher drops are timed too."""
    if rounds < 1:
        raise ValueError("rounds must be >= 1")
    parse = make_dispatcher().parse
    clock = time.perf_counter_ns
    timings = []
    for packet_id, packets in sorted(by_id.items()):
        best = float("inf")
        for _ in range(rounds):
            start = clock()
            for data in packets:
                parse(data)
            best = min(best, (clock() - start) / len(packets))
        timings.append(Timing(packet_id, len(packets), best))
    return timings


def packet_name(packet_id: int) -> str:
    return PacketId(packet_id).name if packet_id in set(PacketId) else f"UNKNOWN_{packet_id}"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", type=Path, nargs="*")
    parser.add_argument("--rounds", type=int, default=5, help="passes per packet type; the fastest is reported")
    parser.add_argument("--budget-us", type=float, default=DEFAULT_BUDGET_US, help="fail above this per packet")
    args = parser.parse_args(argv)
    if args.rounds < 1:
        parser.error("--rounds must be >= 1")

    paths = args.paths or sorted(FIXTURES.glob("*.f1raw"))
    by_id = load(paths)
    timings = bench(by_id, args.rounds)
    total = sum(t.packets for t in timings)
    print(f"{total} packets from {len(paths)} file(s), best of {args.rounds} rounds\n")
    print(f"{'id':>3} {'packet':<22} {'count':>9} {'us/packet':>10}")
    for t in timings:
        print(f"{t.packet_id:>3} {packet_name(t.packet_id):<22} {t.packets:>9} {t.best_ns / 1000:>10.4f}")

    slowest = max(timings, key=lambda t: t.best_ns)
    print(
        f"\nslowest: {packet_name(slowest.packet_id)} at {slowest.best_ns / 1000:.4f} us (budget {args.budget_us} us)"
    )
    if slowest.best_ns / 1000 > args.budget_us:
        sys.exit(1)


if __name__ == "__main__":
    main()
