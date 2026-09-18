# Fixtures

Real F1 25 v1.26 recordings, cut with `tools/trim_raw.py` to the packets the parsers use, at full game rate (60 Hz).
`race-2026-monza-finish` was cut again once SessionHistory was parsed, so it holds the final lap time sent before SEND.
Timestamps are rebased to 0, so they replay with `f1telemetry replay`.

| Fixture | Content | Cut from |
|---|---|---|
| `race-2025-melbourne-lap.f1raw` | Format 2025, Melbourne race, 1 s flat out on lap 1 | `race-2025.f1raw --start 60.0 --end 61.0` |
| `tt-2026-monza-flashback.f1raw` | Format 2026, Monza Time Trial, flashback then invalid lap | `tt-2026.f1raw --start 226.3 --end 228.6` |
| `race-2026-monza-finish.f1raw` | Format 2026, Monza race, chequered flag and session end | `race-2026.f1raw --start 321.0 --end 322.2` |
| `f2-2026-sakhir-pit.f1raw` | Format 2026, Sakhir F2 race, pit stop Soft to Hard | `f2-2026.f1raw --start 207.2 --end 208.0` |

Keep each fixture under 300 KB (`tests/test_fixtures.py` checks this).
