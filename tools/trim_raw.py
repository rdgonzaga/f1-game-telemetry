"""Cut a time window out of an `.f1raw` recording, keeping only the packets the parsers use.

Usage: uv run python tools/trim_raw.py recordings/x.f1raw tests/fixtures/y.f1raw --start 100 --end 102
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from f1telemetry.packets import HEADER, PACKET_ID_OFFSET, PacketId
from f1telemetry.rawfile import RawWriter, read_records

KEEP_IDS = frozenset(
    {
        PacketId.SESSION,
        PacketId.LAP_DATA,
        PacketId.EVENT,
        PacketId.CAR_TELEMETRY,
        PacketId.CAR_STATUS,
        PacketId.CAR_DAMAGE,
        PacketId.CAR_TELEMETRY_2,
        PacketId.SESSION_HISTORY,
    }
)


def trim(src: Path, dst: Path, start_s: float, end_s: float) -> int:
    """Write packets with `start_s <= t <= end_s` to `dst`, timestamps rebased to 0; returns the packet count."""
    start_ns, end_ns = int(start_s * 1e9), int(end_s * 1e9)
    base: int | None = None
    dst.parent.mkdir(parents=True, exist_ok=True)
    with RawWriter(dst) as writer:
        for t_ns, data in read_records(src):
            if t_ns < start_ns:
                continue
            if t_ns > end_ns:
                break
            if len(data) < HEADER.size or data[PACKET_ID_OFFSET] not in KEEP_IDS:
                continue
            if base is None:
                base = t_ns
            writer.write(t_ns - base, data)
        return writer.count


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("src", type=Path)
    parser.add_argument("dst", type=Path)
    parser.add_argument("--start", type=float, required=True, help="window start, seconds from recording start")
    parser.add_argument("--end", type=float, required=True, help="window end, seconds from recording start")
    args = parser.parse_args(argv)
    if args.end < args.start:
        parser.error("--end must be >= --start")
    count = trim(args.src, args.dst, args.start, args.end)
    print(f"Wrote {count} packets ({args.dst.stat().st_size} bytes) to {args.dst}")


if __name__ == "__main__":
    main()
