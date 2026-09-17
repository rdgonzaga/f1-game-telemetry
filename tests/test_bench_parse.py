from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from bench_parse import DEFAULT_BUDGET_US, FIXTURES, bench, load, packet_name
from f1telemetry.packets import PacketId

PARSED_IDS = {
    PacketId.SESSION,
    PacketId.LAP_DATA,
    PacketId.EVENT,
    PacketId.CAR_TELEMETRY,
    PacketId.CAR_STATUS,
    PacketId.CAR_DAMAGE,
    PacketId.CAR_TELEMETRY_2,
}


def test_bench_times_every_packet_type_within_budget() -> None:
    timings = bench(load(sorted(FIXTURES.glob("*.f1raw"))), rounds=1)
    assert {t.packet_id for t in timings} == PARSED_IDS
    assert all(t.packets > 0 for t in timings)
    # Generous headroom over the measured ~2.7 us so a slow CI runner doesn't fail the suite.
    assert all(t.best_ns / 1000 < DEFAULT_BUDGET_US for t in timings)


def test_bench_rejects_zero_rounds() -> None:
    with pytest.raises(ValueError):
        bench({}, rounds=0)


def test_packet_name_labels_unknown_ids() -> None:
    assert packet_name(PacketId.CAR_TELEMETRY_2) == "CAR_TELEMETRY_2"
    assert packet_name(99) == "UNKNOWN_99"
