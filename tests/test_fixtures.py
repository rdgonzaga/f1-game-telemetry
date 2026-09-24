"""Decode the committed real-game recordings in tests/fixtures and check values seen in the game.

See tests/fixtures/README.md for where each fixture was cut from.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from f1telemetry.car_damage import CarDamage
from f1telemetry.car_status import CarStatus
from f1telemetry.car_telemetry import CarTelemetry
from f1telemetry.car_telemetry2 import CarTelemetry2
from f1telemetry.event import Flashback, SessionEnded
from f1telemetry.lap_data import LapData
from f1telemetry.names import formula_name, session_type_name, track_name, visual_tyre_compound_name
from f1telemetry.packets import Packet, PacketId
from f1telemetry.parsers import make_dispatcher
from f1telemetry.rawfile import read_records
from f1telemetry.session import Session

FIXTURES = Path(__file__).parent / "fixtures"
MAX_FIXTURE_BYTES = 300_000

# name: (packet format, player car index)
EXPECTED = {
    "race-2025-melbourne-lap": (2025, 19),
    "tt-2026-monza-flashback": (2026, 0),
    "race-2026-monza-finish": (2026, 21),
    "f2-2026-sakhir-pit": (2026, 21),
}


def decode(name: str) -> list[tuple[int, Packet]]:
    dispatcher = make_dispatcher()
    packets = []
    for t_ns, data in read_records(FIXTURES / f"{name}.f1raw"):
        packet = dispatcher.parse(data)
        assert packet is not None, f"packet {data[6]} at {t_ns} ns was dropped"
        packets.append((t_ns, packet))
    return packets


def of_type[T](packets: list[tuple[int, Packet]], kind: type[T]) -> list[T]:
    return [packet.data for _, packet in packets if isinstance(packet.data, kind)]


@pytest.mark.parametrize("name", EXPECTED)
def test_fixture_decodes_fully(name: str) -> None:
    packet_format, player = EXPECTED[name]
    path = FIXTURES / f"{name}.f1raw"
    assert path.stat().st_size < MAX_FIXTURE_BYTES

    packets = decode(name)
    times = [t for t, _ in packets]
    assert times[0] == 0
    assert times == sorted(times)
    headers = [packet.header for _, packet in packets]
    assert {h.packet_format for h in headers} == {packet_format}
    assert {h.player_car_index for h in headers} == {player}
    # UID 0 only on the SessionHistory the game sends just before SEND.
    assert len({h.session_uid for h in headers} - {0}) == 1
    for kind in (Session, LapData, CarTelemetry, CarStatus, CarDamage):
        assert of_type(packets, kind), f"no {kind.__name__} packets"
    assert bool(of_type(packets, CarTelemetry2)) == (packet_format == 2026)


def test_2025_race_steady_slice() -> None:
    packets = decode("race-2025-melbourne-lap")
    sessions = of_type(packets, Session)
    s = sessions[0]
    assert (track_name(s.track_id), session_type_name(s.session_type), formula_name(s.formula)) == (
        "Melbourne",
        "Race",
        "F1 Modern",
    )
    assert (s.total_laps, s.track_length) == (5, 5276)
    assert s.active_aero_track_status is None

    # One second of flat-out driving at the game's 60 Hz rate, no dropped frames.
    lap_packets = [p for _, p in packets if isinstance(p.data, LapData)]
    frames = [p.header.frame_identifier for p in lap_packets]
    assert frames == list(range(3137, 3197))
    laps = of_type(packets, LapData)
    distances = [lap.lap_distance for lap in laps]
    assert distances == sorted(distances)
    assert distances[0] == pytest.approx(2541.63, abs=0.01)
    assert distances[-1] == pytest.approx(2622.74, abs=0.01)
    assert {(lap.current_lap_num, lap.sector, lap.car_position, lap.driver_status) for lap in laps} == {(1, 1, 5, 4)}
    assert laps[0].sector1_time_ms == 35365

    telemetry = of_type(packets, CarTelemetry)
    assert {t.gear for t in telemetry} == {8}
    assert all(295 <= t.speed <= 299 for t in telemetry)

    status = of_type(packets, CarStatus)[0]
    assert visual_tyre_compound_name(status.visual_tyre_compound) == "Soft"
    assert status.ers_harvest_limit_per_lap is None
    assert status.ers_store_energy == pytest.approx(2_840_172.25)
    assert of_type(packets, CarDamage)[0].front_right_wing_damage == 31


def test_2026_time_trial_flashback_and_invalid_lap() -> None:
    packets = decode("tt-2026-monza-flashback")
    s = of_type(packets, Session)[0]
    assert (session_type_name(s.session_type), track_name(s.track_id), formula_name(s.formula)) == (
        "Time Trial",
        "Monza",
        "F1 26",
    )
    assert s.track_length == 5798
    assert len(s.active_aero_zones_full) == 4
    # Monza's first full active aero zone wraps the start/finish line.
    start, end = s.active_aero_zones_full[0]
    assert start > end

    flashback_header, flashback = next((p.header, p.data) for _, p in packets if isinstance(p.data, Flashback))
    assert flashback.frame_identifier == 44229
    assert flashback.session_time == pytest.approx(762.521, abs=0.001)
    # Frame ids rewind to the flashback target once the game resumes.
    lap_headers = [p.header for _, p in packets if isinstance(p.data, LapData)]
    assert flashback_header.frame_identifier == 45129
    assert lap_headers[0].frame_identifier == 44229
    assert lap_headers[0].overall_frame_identifier == 45129

    laps = of_type(packets, LapData)
    assert (laps[0].current_lap_num, laps[0].last_lap_time_ms, laps[0].current_lap_invalid) == (3, 82607, False)
    assert laps[-1].current_lap_invalid
    assert {lap.driver_status for lap in laps} == {1}

    # Time Trial freezes tyre temperatures and the ERS store.
    assert {t.tyre_surface_temperature_fl for t in of_type(packets, CarTelemetry)} == {89}
    assert {st.ers_store_energy for st in of_type(packets, CarStatus)} == {4_000_000.0}
    assert all(t2.regulations_2026_applicable for t2 in of_type(packets, CarTelemetry2))


def test_2026_race_finish_changes_last_lap_time_not_lap_number() -> None:
    packets = decode("race-2026-monza-finish")
    s = of_type(packets, Session)[0]
    assert (track_name(s.track_id), session_type_name(s.session_type), s.total_laps) == ("Monza", "Race", 3)

    laps = of_type(packets, LapData)
    first, last = laps[0], laps[-1]
    assert (first.current_lap_num, first.last_lap_time_ms, first.result_status) == (3, 103822, 2)
    assert (last.current_lap_num, last.last_lap_time_ms, last.result_status) == (3, 83561, 3)
    assert last.lap_distance == pytest.approx(3.23, abs=0.01)

    events = [p for _, p in packets if p.header.packet_id == PacketId.EVENT and p.data is not None]
    assert events[-1].data == SessionEnded()
    assert events[-1].header.frame_identifier == 0
    assert of_type(packets, Session)[-1].game_paused

    status = of_type(packets, CarStatus)[-1]
    assert status.ers_harvest_limit_per_lap == 6_000_000.0
    assert status.tyres_age_laps == 2


def test_2026_f2_pit_stop_compound_change() -> None:
    packets = decode("f2-2026-sakhir-pit")
    s = of_type(packets, Session)[0]
    assert (track_name(s.track_id), session_type_name(s.session_type), formula_name(s.formula)) == (
        "Sakhir",
        "Race 2",
        "F2",
    )
    assert s.track_length == 5408
    # The Session packet lists active aero zones even for F2; CarTelemetry2 says the 2026 rules don't apply.
    assert len(s.active_aero_zones_full) == 4
    assert not any(t2.regulations_2026_applicable for t2 in of_type(packets, CarTelemetry2))

    assert {(lap.pit_status, lap.driver_status, lap.num_pit_stops) for lap in of_type(packets, LapData)} == {(2, 2, 0)}

    status = of_type(packets, CarStatus)
    tyres = [(st.visual_tyre_compound, st.actual_tyre_compound, st.tyres_age_laps) for st in status]
    assert tyres[0] == (20, 12, 1)
    assert tyres[-1] == (22, 14, 0)
    assert visual_tyre_compound_name(tyres[0][0]) == "F2 Soft"
    assert visual_tyre_compound_name(tyres[-1][0]) == "F2 Hard"
    assert all(st.pit_limiter for st in status)
    assert {(st.max_rpm, st.ers_store_energy, st.ers_harvest_limit_per_lap) for st in status} == {(8750, 0.0, 0.0)}

    # New tyres come on cold.
    telemetry = of_type(packets, CarTelemetry)
    assert telemetry[0].tyre_surface_temperature_fl == 72
    assert telemetry[-1].tyre_surface_temperature_fl == 32
