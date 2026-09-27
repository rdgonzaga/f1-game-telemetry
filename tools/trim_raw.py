"""Cut time windows out of an `.f1raw` recording, keeping only the packets the parsers use.

Usage: uv run python tools/trim_raw.py recordings/x.f1raw tests/fixtures/y.f1raw --start 100 --end 102
Repeat `--start`/`--end` to join several windows, e.g. both sides of a save and reload minutes apart.
"""

from __future__ import annotations

import argparse
import sys
from itertools import pairwise
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from f1telemetry.packets import HEADER, PACKET_ID_OFFSET, PacketId
from f1telemetry.rawfile import RawWriter, read_records

KEEP_IDS = frozenset(
    {
        PacketId.MOTION,
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


# Time left between two windows in the output, so a replay doesn't sit through the minutes cut out between them.
WINDOW_GAP_NS = 1_000_000_000


def trim(src: Path, dst: Path, windows: list[tuple[float, float]]) -> int:
    """Write packets inside the `(start_s, end_s)` windows to `dst`, rebased to 0 with the gaps between windows
    closed up to `WINDOW_GAP_NS`; returns the packet count. Windows must be in order and not overlap."""
    bounds = [(int(start * 1e9), int(end * 1e9)) for start, end in windows]
    shift: int | None = None  # subtracted from source time; grows at each window to close the gap
    last_out = -WINDOW_GAP_NS
    window = 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    with RawWriter(dst) as writer:
        for t_ns, data in read_records(src):
            while window < len(bounds) and t_ns > bounds[window][1]:
                window += 1
                shift = None
            if window == len(bounds):
                break
            if t_ns < bounds[window][0]:
                continue
            if len(data) < HEADER.size or data[PACKET_ID_OFFSET] not in KEEP_IDS:
                continue
            if shift is None:
                shift = t_ns - (last_out + WINDOW_GAP_NS)
            last_out = t_ns - shift
            writer.write(last_out, data)
        return writer.count


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("src", type=Path)
    parser.add_argument("dst", type=Path)
    parser.add_argument(
        "--start", type=float, action="append", required=True, help="window start, seconds from recording start"
    )
    parser.add_argument(
        "--end", type=float, action="append", required=True, help="window end, seconds from recording start"
    )
    args = parser.parse_args(argv)
    if len(args.start) != len(args.end):
        parser.error("give one --end for each --start")
    windows = list(zip(args.start, args.end, strict=True))
    if any(end < start for start, end in windows):
        parser.error("--end must be >= --start")
    if any(later[0] <= earlier[1] for earlier, later in pairwise(windows)):
        parser.error("windows must be in order and not overlap")
    count = trim(args.src, args.dst, windows)
    print(f"Wrote {count} packets ({args.dst.stat().st_size} bytes) to {args.dst}")


if __name__ == "__main__":
    main()
