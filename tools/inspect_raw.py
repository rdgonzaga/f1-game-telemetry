"""Summarise an `.f1raw` recording: packet sizes, sessions, events, player timeline and value ranges.

Usage: uv run python tools/inspect_raw.py recordings/x.f1raw [--start 100] [--end 160] [--all-events]
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from f1telemetry import event
from f1telemetry.car_damage import CarDamage
from f1telemetry.car_status import CarStatus
from f1telemetry.car_telemetry import CarTelemetry
from f1telemetry.car_telemetry2 import CarTelemetry2
from f1telemetry.lap_data import LapData
from f1telemetry.names import formula_name, session_type_name, track_name, visual_tyre_compound_name
from f1telemetry.packets import FORMATS, HEADER, PACKET_ID_OFFSET, PacketId
from f1telemetry.parsers import make_dispatcher
from f1telemetry.rawfile import read_records
from f1telemetry.session import Session

# BUTN fires several times a second while buttons are held; hidden unless --all-events.
NOISY_EVENTS = {b"BUTN"}


class Range:
    def __init__(self) -> None:
        self.low = float("inf")
        self.high = float("-inf")

    def add(self, value: float) -> None:
        self.low = min(self.low, value)
        self.high = max(self.high, value)

    def __str__(self) -> str:
        if self.low > self.high:
            return "-"
        return f"{self.low:g} .. {self.high:g}"


def fmt_lap_time(ms: int) -> str:
    return f"{ms // 60_000}:{ms % 60_000 / 1000:06.3f}"


def inspect(
    path: Path,
    start_s: float | None = None,
    end_s: float | None = None,
    all_events: bool = False,
    out: Callable[[str], object] = print,
) -> None:
    dispatcher = make_dispatcher()
    counts: Counter[tuple[int, int]] = Counter()
    bad_sizes: Counter[tuple[int, int, int]] = Counter()
    versions: set[tuple[int, int, int, int]] = set()
    sessions: dict[int, tuple[float, int, Session]] = {}
    timeline: list[str] = []
    last_state: dict[str, object] = {}
    range_names = ("speed", "rpm", "gear", "throttle", "brake", "engine temp", "tyre surface temp", "fuel kg")
    ranges = {name: Range() for name in (*range_names, "ers store MJ", "tyre wear %")}
    first_t = last_t = None
    total = 0

    def change(t: float, key: str, value: object, label: str) -> None:
        if last_state.get(key, ...) != value:
            if key in last_state:
                timeline.append(f"{t:8.1f}s  {label}")
            last_state[key] = value

    for t_ns, data in read_records(path):
        t = t_ns / 1e9
        if (start_s is not None and t < start_s) or (end_s is not None and t > end_s):
            continue
        total += 1
        first_t = t if first_t is None else first_t
        last_t = t
        if len(data) < HEADER.size:
            bad_sizes[(0, -1, len(data))] += 1
            continue
        fmt = data[0] | data[1] << 8
        packet_id = data[PACKET_ID_OFFSET]
        counts[(fmt, packet_id)] += 1
        spec = FORMATS.get(fmt)
        expected = spec.packet_sizes.get(packet_id) if spec else None
        if expected is not None and expected != len(data):
            bad_sizes[(fmt, packet_id, len(data))] += 1

        packet = dispatcher.parse(data)
        if packet is None:
            continue
        header, parsed = packet
        versions.add((header.packet_format, header.game_year, header.game_major_version, header.game_minor_version))
        player = f"idx {header.player_car_index}"

        if isinstance(parsed, Session):
            if header.session_uid not in sessions:
                sessions[header.session_uid] = (t, header.player_car_index, parsed)
            change(t, "paused", parsed.game_paused, f"game paused {parsed.game_paused}")
        elif packet_id == PacketId.EVENT:
            code = data[event.CODE_OFFSET : event.DETAILS_OFFSET]
            if all_events or code not in NOISY_EVENTS:
                detail = f" {parsed}" if parsed is not None else ""
                timeline.append(f"{t:8.1f}s  event {code.decode(errors='replace')}{detail}")
        elif isinstance(parsed, LapData):
            change(t, "lap", parsed.current_lap_num, f"lap {parsed.current_lap_num} ({player})")
            change(t, "last lap", parsed.last_lap_time_ms, f"last lap time {fmt_lap_time(parsed.last_lap_time_ms)}")
            change(t, "invalid", parsed.current_lap_invalid, f"lap invalid {parsed.current_lap_invalid}")
            change(t, "pit", parsed.pit_status, f"pit status {parsed.pit_status}")
            change(t, "driver", parsed.driver_status, f"driver status {parsed.driver_status}")
            change(t, "stops", parsed.num_pit_stops, f"pit stops {parsed.num_pit_stops}")
            change(t, "result", parsed.result_status, f"result status {parsed.result_status}")
        elif isinstance(parsed, CarTelemetry):
            ranges["speed"].add(parsed.speed)
            ranges["rpm"].add(parsed.engine_rpm)
            ranges["gear"].add(parsed.gear)
            ranges["throttle"].add(round(parsed.throttle, 2))
            ranges["brake"].add(round(parsed.brake, 2))
            ranges["engine temp"].add(parsed.engine_temperature)
            for temp in parsed[13:17]:
                ranges["tyre surface temp"].add(temp)
        elif isinstance(parsed, CarStatus):
            ranges["fuel kg"].add(round(parsed.fuel_in_tank, 2))
            ranges["ers store MJ"].add(round(parsed.ers_store_energy / 1e6, 2))
            compound = visual_tyre_compound_name(parsed.visual_tyre_compound)
            change(
                t, "compound", parsed.visual_tyre_compound, f"tyres {compound} (actual {parsed.actual_tyre_compound})"
            )
            change(t, "tyre age", parsed.tyres_age_laps, f"tyre age {parsed.tyres_age_laps} laps")
        elif isinstance(parsed, CarDamage):
            for wear in parsed[:4]:
                ranges["tyre wear %"].add(round(wear, 1))
            wings = (parsed.front_left_wing_damage, parsed.front_right_wing_damage, parsed.rear_wing_damage)
            change(t, "wings", wings, f"wing damage FL/FR/rear {wings}")
        elif isinstance(parsed, CarTelemetry2):
            change(t, "regs", parsed.regulations_2026_applicable, f"2026 regs {parsed.regulations_2026_applicable}")
            change(t, "wrong way", parsed.is_driving_wrong_way, f"wrong way {parsed.is_driving_wrong_way}")

    out(f"{path}: {total} packets, {first_t or 0:.1f}s .. {last_t or 0:.1f}s")
    for fmt, year, major, minor in sorted(versions):
        out(f"format {fmt}, game {year} v{major}.{minor:02d}")

    out("\npackets (format, id, count, expected size)")
    for (fmt, packet_id), count in sorted(counts.items()):
        name = PacketId(packet_id).name if packet_id in set(PacketId) else "?"
        expected = FORMATS[fmt].packet_sizes.get(packet_id) if fmt in FORMATS else None
        out(f"  {fmt} {packet_id:2d} {name:<22} {count:7d}  {expected}")
    out(f"size mismatches: {sum(bad_sizes.values())}")
    for (fmt, packet_id, size), count in sorted(bad_sizes.items()):
        out(f"  format {fmt} packet {packet_id}: {count} x {size} bytes")

    out("\nsessions")
    for uid, (t, index, s) in sessions.items():
        out(
            f"  {t:8.1f}s  uid {uid:#x}: {track_name(s.track_id)}, {session_type_name(s.session_type)}, "
            f"{formula_name(s.formula)}, {s.total_laps} laps, {s.track_length} m, player idx {index}"
        )
        if s.active_aero_track_status is not None:
            out(f"            aero status {s.active_aero_track_status}, full zones {s.active_aero_zones_full}")

    out("\ntimeline")
    for line in timeline:
        out(line)

    out("\nplayer value ranges")
    for name, value_range in ranges.items():
        out(f"  {name:<18} {value_range}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", type=Path)
    parser.add_argument("--start", type=float, help="skip packets before this many seconds")
    parser.add_argument("--end", type=float, help="skip packets after this many seconds")
    parser.add_argument("--all-events", action="store_true", help="include noisy events such as BUTN")
    args = parser.parse_args(argv)
    inspect(args.path, args.start, args.end, args.all_events)


if __name__ == "__main__":
    main()
