"""Comparing laps: resampling onto a fixed distance grid, the delta trace, minisectors and the live delta reference.

Laps are sampled in time, so two laps never line up: the same metre of track comes at a different sample index in
each. Everything here first puts a lap on a `DISTANCE_STEP` grid, after which two laps can be subtracted point by
point. `compare_laps` does that for two saved laps; `LapReference` does it once for the session's best lap so the
live feed can look up its time at the car's distance 30 times a second without searching.

No disk and no packet parsing, so both the API and the live feed can use it.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

DISTANCE_STEP = 5.0  # metres
MINISECTORS = 25
# The traces a comparison returns alongside the delta; `lap_time_ms` is resampled too, to build the delta itself.
TRACE_COLUMNS = ("speed", "throttle", "brake", "steer")
TIME_COLUMN = "lap_time_ms"
DIGITS = 3

type Json = dict[str, Any]
type Column = Sequence[float]


def _rising(distance: Column) -> list[int]:
    """Indices whose distance moves forward. A lap keeps its samples across a flashback rewind, so a few can repeat."""
    keep: list[int] = []
    furthest = -math.inf
    for index, value in enumerate(distance):
        if value > furthest:
            keep.append(index)
            furthest = value
    return keep


def _bounds(distance: Column) -> tuple[float, float] | None:
    """The distance the lap actually covers, or None when it has too few samples to interpolate."""
    keep = _rising(distance)
    if len(keep) < 2:
        return None
    return distance[keep[0]], distance[keep[-1]]


def distance_grid(start: float, end: float, step: float = DISTANCE_STEP) -> list[float]:
    """Every multiple of `step` from `start` to `end`. Built from the first point, so the spacing can't drift."""
    first = math.ceil(start / step) * step
    count = math.floor((end - first) / step) + 1 if end >= first else 0
    return [round(first + step * index, DIGITS) for index in range(count)]


def resample(distance: Column, columns: Mapping[str, Column], points: Sequence[float]) -> dict[str, list[float]]:
    """Linearly interpolate each column onto `points`, walking the samples once. `points` must rise, like `distance`."""
    keep = _rising(distance)
    if len(keep) < 2:
        raise ValueError("a lap needs at least two samples that move forward")
    result: dict[str, list[float]] = {name: [] for name in columns}
    last = len(keep) - 2  # index of the last usable segment
    segment = 0
    for point in points:
        while segment < last and distance[keep[segment + 1]] < point:
            segment += 1
        low, high = keep[segment], keep[segment + 1]
        span = distance[high] - distance[low]
        share = (point - distance[low]) / span if span else 0.0
        for name, values in columns.items():
            start_value = values[low]
            result[name].append(start_value + (values[high] - start_value) * share)
    return result


def _minisectors(points: Sequence[float], delta: Sequence[float]) -> list[Json]:
    """Time gained or lost inside each slice, so the values are independent instead of a running total."""
    count = min(MINISECTORS, len(points) - 1)
    edges = [round(index * (len(points) - 1) / count) for index in range(count + 1)]
    return [
        {
            "start": points[edges[index]],
            "end": points[edges[index + 1]],
            "delta": round(delta[edges[index + 1]] - delta[edges[index]], DIGITS),
        }
        for index in range(count)
    ]


def _trace(lap: Json, points: Sequence[float]) -> tuple[Json, list[float]]:
    """A lap's summary with its resampled traces, plus its lap time at each point in milliseconds."""
    columns = lap["columns"]
    wanted = {name: columns[name] for name in (*TRACE_COLUMNS, TIME_COLUMN) if name in columns}
    resampled = resample(columns["lap_distance"], wanted, points)
    times = resampled.pop(TIME_COLUMN)
    block = {
        "number": lap["number"],
        "lap_time_ms": lap["lap_time_ms"],
        "invalid": lap["invalid"],
        "partial": lap["partial"],
        "columns": {name: [round(value, DIGITS) for value in values] for name, values in resampled.items()},
    }
    return block, times


def compare_laps(lap_a: Json, lap_b: Json, step: float = DISTANCE_STEP) -> Json:
    """Both laps on one distance grid, with the delta trace and minisector gains.

    `delta` is how much time lap B has taken more than lap A at each point, in seconds, so positive means B is
    slower. It is not shifted to start at zero: two laps joined at different distances keep the gap they had.
    Raises ValueError when the laps share no distance to compare over.
    """
    bounds_a = _bounds(lap_a["columns"]["lap_distance"])
    bounds_b = _bounds(lap_b["columns"]["lap_distance"])
    if bounds_a is None or bounds_b is None:
        raise ValueError("a lap needs at least two samples that move forward")
    points = distance_grid(max(bounds_a[0], bounds_b[0]), min(bounds_a[1], bounds_b[1]), step)
    if len(points) < 2:
        raise ValueError("the laps have no distance in common")
    block_a, times_a = _trace(lap_a, points)
    block_b, times_b = _trace(lap_b, points)
    delta = [round((b - a) / 1000, DIGITS) for a, b in zip(times_a, times_b, strict=True)]
    return {
        "step": step,
        "distance": list(points),
        "laps": [block_a, block_b],
        "delta": delta,
        "minisectors": _minisectors(points, delta),
    }


@dataclass(frozen=True, slots=True)
class LapReference:
    """A lap's time at every grid point, so the live delta is an array lookup instead of a search."""

    number: int
    start: float
    step: float
    times_ms: list[float]

    @classmethod
    def build(
        cls, number: int, distance: Column, lap_time_ms: Column, step: float = DISTANCE_STEP
    ) -> LapReference | None:
        """None when the lap is too short to resample."""
        bounds = _bounds(distance)
        if bounds is None:
            return None
        points = distance_grid(bounds[0], bounds[1], step)
        if len(points) < 2:
            return None
        times = resample(distance, {TIME_COLUMN: lap_time_ms}, points)[TIME_COLUMN]
        return cls(number, points[0], step, times)

    def time_at(self, distance: float) -> float | None:
        """The reference lap's time in milliseconds at this distance, or None where the lap doesn't reach."""
        offset = (distance - self.start) / self.step
        last = len(self.times_ms) - 1
        if offset < 0 or offset > last:
            return None
        index = int(offset)
        if index >= last:
            return self.times_ms[last]
        return self.times_ms[index] + (self.times_ms[index + 1] - self.times_ms[index]) * (offset - index)
