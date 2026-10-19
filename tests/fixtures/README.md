# Fixtures

Real F1 25 v1.26 recordings, cut with `tools/trim_raw.py` to the packets the parsers use, at full game rate (60 Hz).
`race-2026-monza-finish` was cut again once SessionHistory was parsed, so it holds the final lap time sent before SEND.
Timestamps are rebased to 0, so they replay with `f1telemetry replay`. A fixture cut from several windows has the
gaps between them closed to 1 s.

| Fixture | Content | Cut from |
|---|---|---|
| `race-2025-melbourne-lap.f1raw` | Format 2025, Melbourne race, 1 s flat out on lap 1 | `race-2025.f1raw --start 60.0 --end 61.0` |
| `tt-2026-monza-flashback.f1raw` | Format 2026, Monza Time Trial, flashback then invalid lap | `tt-2026.f1raw --start 226.3 --end 228.6` |
| `race-2026-monza-finish.f1raw` | Format 2026, Monza race, chequered flag and session end | `race-2026.f1raw --start 321.0 --end 322.2` |
| `f2-2026-sakhir-pit.f1raw` | Format 2026, Sakhir F2 race, pit stop Soft to Hard | `f2-2026.f1raw --start 207.2 --end 208.0` |
| `race-2026-interlagos-reload.f1raw` | Format 2026, Interlagos race, one save loaded three times | `brazil-full-wet-race-2026.f1raw`, 8 windows: `--start 1110.97 --end 1111.06 --start 1185.0 --end 1185.1 --start 1358.80 --end 1358.81 --start 1366.25 --end 1366.27 --start 1370.34 --end 1370.35 --start 1375.75 --end 1375.76 --start 1467.32 --end 1467.34 --start 1471.95 --end 1472.15` |
| `race-2026-jeddah-restart.f1raw` | Format 2026, Jeddah career race restarted after `SEND` | `career-weekend-2026.f1raw --start 3891.25 --end 3891.72 --start 3892.44 --end 3892.6` |
| `race-2026-spa-wet-flashback.f1raw` | Format 2026, Spa race on inters in a storm, two flashbacks back over the line into lap 6 | `spa-wet-race-2026.f1raw`, 5 windows: `--start 1591.95 --end 1592.1 --start 1614.45 --end 1614.55 --start 1616.3 --end 1616.4 --start 1617.98 --end 1618.05 --start 1621.05 --end 1621.15` |
| `race-2026-spa-red-flag.f1raw` | Format 2026, Spa race in a storm, safety car then red flag on lap 1, then the race resumed | `spa-wet-race-2026.f1raw`, 5 windows: `--start 35.44 --end 35.455 --start 35.785 --end 35.80 --start 36.125 --end 36.14 --start 36.935 --end 36.95 --start 47.31 --end 47.325` |

Keep each fixture under 300 KB (`tests/test_fixtures.py` checks this).
