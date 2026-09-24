"""Lap comparison: the 5 m grid, aligned traces, the delta trace, minisectors and the live delta reference."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from f1telemetry.compare import DISTANCE_STEP, MINISECTORS, LapReference, compare_laps, resample
from f1telemetry.packets import Packet
from f1telemetry.parsers import make_dispatcher
from f1telemetry.rawfile import read_records
from f1telemetry.store import lap_document
from f1telemetry.tracker import SessionTracker

FIXTURES = Path(__file__).parent / "fixtures"

type Json = dict[str, Any]


def steady_lap(number: int, speed_ms: float, start: float = 0.0, end: float = 1000.0, samples: int = 201) -> Json:
    """A lap driven at a constant speed, so its time at any distance is known exactly."""
    step = (end - start) / (samples - 1)
    distance = [start + step * i for i in range(samples)]
    return {
        "number": number,
        "lap_time_ms": round(end / speed_ms * 1000),
        "invalid": False,
        "partial": False,
        "samples": samples,
        "columns": {
            "lap_distance": distance,
            "lap_time_ms": [round(d / speed_ms * 1000) for d in distance],
            "speed": [round(speed_ms * 3.6)] * samples,
            "throttle": [1.0] * samples,
            "brake": [0.0] * samples,
            "steer": [0.0] * samples,
        },
    }


def fixture_lap(name: str) -> Json:
    """The completed lap from a fixture recording, in the shape the store saves."""
    tracker = SessionTracker()
    laps = []
    tracker.on_event = lambda event: laps.append(event.lap) if hasattr(event, "lap") else None
    dispatcher = make_dispatcher()
    for _, data in read_records(FIXTURES / f"{name}.f1raw"):
        packet: Packet | None = dispatcher.parse(data)
        if packet is not None:
            tracker.update(packet)
    tracker.close()
    return lap_document(laps[0])


def test_compare_aligns_both_laps_on_a_five_metre_grid() -> None:
    result = compare_laps(steady_lap(1, 50.0), steady_lap(2, 40.0))

    assert result["step"] == DISTANCE_STEP
    assert result["distance"][:3] == [0.0, 5.0, 10.0]
    assert result["distance"][-1] == 1000.0
    points = len(result["distance"])
    for lap in result["laps"]:
        assert all(len(column) == points for column in lap["columns"].values())
    assert len(result["delta"]) == points


def test_delta_is_how_much_time_the_second_lap_has_lost_at_each_point() -> None:
    result = compare_laps(steady_lap(1, 50.0), steady_lap(2, 40.0))

    for distance, delta in zip(result["distance"], result["delta"], strict=True):
        expected = distance / 40.0 - distance / 50.0
        assert delta == pytest.approx(expected, abs=0.002)
    assert result["delta"][0] == 0.0


def test_minisectors_split_the_compared_distance_into_equal_gains() -> None:
    result = compare_laps(steady_lap(1, 50.0), steady_lap(2, 40.0))

    minisectors = result["minisectors"]
    assert len(minisectors) == MINISECTORS
    assert (minisectors[0]["start"], minisectors[-1]["end"]) == (0.0, 1000.0)
    assert all(m["end"] > m["start"] for m in minisectors)
    # Constant speeds: every minisector loses the same time, and together they make up the final delta.
    assert all(m["delta"] == pytest.approx(minisectors[0]["delta"], abs=0.002) for m in minisectors)
    assert sum(m["delta"] for m in minisectors) == pytest.approx(result["delta"][-1], abs=0.01)


def test_the_grid_covers_only_the_distance_both_laps_drove() -> None:
    result = compare_laps(steady_lap(1, 50.0, start=203.0), steady_lap(2, 40.0, end=797.0))

    assert (result["distance"][0], result["distance"][-1]) == (205.0, 795.0)
    assert result["minisectors"][0]["start"] == 205.0
    assert result["minisectors"][-1]["end"] == 795.0


def test_values_between_samples_are_interpolated() -> None:
    lap = steady_lap(1, 50.0, samples=3)  # samples every 500 m
    lap["columns"]["speed"] = [100, 200, 300]

    columns = resample(lap["columns"]["lap_distance"], {"speed": lap["columns"]["speed"]}, [0.0, 250.0, 750.0])

    assert columns["speed"] == pytest.approx([100.0, 150.0, 250.0])


def test_samples_that_do_not_move_forward_are_skipped() -> None:
    distance = [0.0, 10.0, 5.0, 20.0]  # a stray sample from before a flashback

    columns = resample(distance, {"speed": [100.0, 200.0, 999.0, 300.0]}, [0.0, 10.0, 15.0, 20.0])

    assert columns["speed"] == pytest.approx([100.0, 200.0, 250.0, 300.0])


def test_laps_with_no_distance_in_common_are_refused() -> None:
    with pytest.raises(ValueError, match="no distance in common"):
        compare_laps(steady_lap(1, 50.0, start=0.0, end=400.0), steady_lap(2, 40.0, start=600.0, end=1000.0))


def test_a_lap_compared_with_itself_has_no_delta_anywhere() -> None:
    lap = fixture_lap("race-2026-monza-finish")

    result = compare_laps(lap, lap)

    assert result["distance"] == pytest.approx([5765.0, 5770.0, 5775.0, 5780.0, 5785.0, 5790.0, 5795.0])
    assert set(result["delta"]) == {0.0}
    assert {m["delta"] for m in result["minisectors"]} == {0.0}
    assert result["laps"][0]["columns"]["speed"] == result["laps"][1]["columns"]["speed"]


def test_a_lap_shorter_than_the_minisector_count_gets_one_per_grid_step() -> None:
    # The fixture covers the last 35 m of a lap: six 5 m steps, so six minisectors instead of 25.
    result = compare_laps(fixture_lap("race-2026-monza-finish"), fixture_lap("race-2026-monza-finish"))

    assert len(result["minisectors"]) == len(result["distance"]) - 1 < MINISECTORS
    assert [m["start"] for m in result["minisectors"]] == result["distance"][:-1]


def test_a_reference_gives_the_best_lap_time_at_a_distance() -> None:
    lap = steady_lap(1, 50.0)
    reference = LapReference.build(1, lap["columns"]["lap_distance"], lap["columns"]["lap_time_ms"])

    assert reference is not None
    assert reference.number == 1
    assert reference.time_at(500.0) == pytest.approx(10_000, abs=5)
    assert reference.time_at(502.5) == pytest.approx(10_050, abs=5)


def test_a_lap_too_short_to_resample_has_no_reference() -> None:
    assert LapReference.build(1, [10.0, 12.0], [100, 120]) is None
    assert LapReference.build(1, [], []) is None


def test_building_a_reference_from_a_full_lap_stays_off_the_frame_budget() -> None:
    samples = 6000  # a 100 s lap at 60 Hz
    distance = [i * 5800 / samples for i in range(samples)]
    times = [round(d / 55 * 1000) for d in distance]

    start = time.perf_counter()
    reference = LapReference.build(3, distance, times)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert reference is not None
    # It runs once per completed lap on the event loop; the measured cost is ~1 ms.
    assert elapsed_ms < 50
