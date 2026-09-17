# UDP Spec Notes

What this project relies on from the F1 25 telemetry output, so you don't have to read the whole EA spec.
Official spec (both formats, PDF linked from the post):
[EA SPORTS F1 25: 2026 Season Pack UDP Specification](https://forums.ea.com/blog/f1-games-game-info-hub-en/ea-sports%E2%84%A2-f1%C2%AE25-udp-specification/12187347).

The game's **UDP Format** setting (Settings → Telemetry) picks the format: `2025` is the base F1 25 output, `2026`
comes with the 2026 Season Pack. Both are supported and the format is read from every packet header, so nothing needs
configuring here. Everything is little-endian and packed, with no padding.

Cross-checked against two independent reference implementations: [`volodymyr-fed/F1Game.UDP`](https://github.com/volodymyr-fed/F1Game.UDP)
v25.1.1 (2025) and v26.0.0 (2026), and [`MacManley/f1-26-udp`](https://github.com/MacManley/f1-26-udp) for 2026.
Layouts live in `f1telemetry/packets.py` (`FORMATS`) and are checked against real recordings in `tests/test_fixtures.py`.

## Header

29 bytes, identical in both formats. `packetId` at byte 6 is what the dispatcher routes on, and `packetFormat` at
byte 0 selects the layout.

| Offset | Type | Field |
|---|---|---|
| 0 | u16 | `packetFormat` (2025 or 2026) |
| 2 | u8 | `gameYear` (25) |
| 3 | u8 | `gameMajorVersion` |
| 4 | u8 | `gameMinorVersion` |
| 5 | u8 | `packetVersion` |
| 6 | u8 | `packetId` |
| 7 | u64 | `sessionUID` |
| 15 | f32 | `sessionTime` |
| 19 | u32 | `frameIdentifier` |
| 23 | u32 | `overallFrameIdentifier` (keeps counting through a flashback) |
| 27 | u8 | `playerCarIndex` |
| 28 | u8 | `secondaryPlayerCarIndex` (255 when unused) |

## Packet sizes

A packet whose length doesn't match its format exactly is dropped, so these sizes are load-bearing. Per-car packets
hold one slot per car (22 in 2025, 24 in 2026) and this project only ever unpacks the player's slot, found at
`29 + playerCarIndex * slot`. Slot sizes are listed only for the packets this project parses; the others are
recognised by size but never unpacked.

| Id | Packet | 2025 | 2026 | Slot 2025 | Slot 2026 | Used |
|---|---|---|---|---|---|---|
| 0 | Motion | 1349 | 1325 | | | |
| 1 | Session | 753 | 926 | — | — | yes |
| 2 | LapData | 1285 | 1399 | 57 | 57 | yes |
| 3 | Event | 45 | 45 | — | — | yes |
| 4 | Participants | 1284 | 1470 | | | |
| 5 | CarSetups | 1133 | 1233 | | | |
| 6 | CarTelemetry | 1352 | 1448 | 60 | 59 | yes |
| 7 | CarStatus | 1239 | 1445 | 55 | 59 | yes |
| 8 | FinalClassification | 1042 | 1134 | | | |
| 9 | LobbyInfo | 954 | 1062 | | | |
| 10 | CarDamage | 1041 | 1133 | 46 | 46 | yes |
| 11 | SessionHistory | 1460 | 1460 | — | — | |
| 12 | TyreSets | 231 | 231 | — | — | |
| 13 | MotionEx | 273 | 273 | — | — | |
| 14 | TimeTrial | 101 | 104 | — | — | |
| 15 | LapPositions | 1131 | 1231 | — | — | |
| 16 | CarTelemetry2 | — | 269 | — | 10 | yes |

Tyre and brake arrays are always ordered **RL, RR, FL, FR**.

## What each used packet gives us

- **Session (1):** track id, session type, `formula` (series), total laps, track length, weather, temperatures, pit
  speed limit, sector 2 and 3 start distances. In 2026 it also carries active aero zones as lap fractions, DRS zones
  and assist settings. Parsed in `f1telemetry/session.py`.
- **LapData (2):** last and current lap time, sector times, lap and total distance, position, lap number, pit status,
  driver status, the lap-invalid flag, penalties and warnings. Sector times and deltas arrive split into a
  millisecond part and a minutes part, which the parser recombines. See `f1telemetry/lap_data.py`.
- **Event (3):** a 4-character code at byte 29 with an optional payload. Used: `SSTA`, `SEND`, `FTLP`, `FLBK`.
  See `f1telemetry/event.py`.
- **CarTelemetry (6):** speed, throttle, brake, steer, clutch, gear, RPM, DRS, rev lights, brake and tyre
  temperatures, tyre pressures. See `f1telemetry/car_telemetry.py`.
- **CarStatus (7):** fuel, tyre compound and age, ERS store and deploy mode, max RPM and gears, FIA flag, engine
  power. See `f1telemetry/car_status.py`.
- **CarDamage (10):** tyre wear and damage, brake damage, blisters, wing, floor, diffuser and sidepod damage,
  gearbox and engine damage. See `f1telemetry/car_damage.py`.
- **CarTelemetry2 (16), 2026 only:** active aero mode and availability, overtake mode, `regulations2026Applicable`
  and `isDrivingWrongWay`. See `f1telemetry/car_telemetry2.py`.

## 2025 vs 2026

- **24 cars instead of 22**, so every per-car packet grows.
- **CarTelemetry:** `engineTemperature` shrinks from u16 to u8, making the slot 59 bytes instead of 60.
- **CarStatus:** `ersHarvestLimitPerLap` (f32) is inserted before `ersDeployedThisLap`, making the slot 59 instead
  of 55. The field is `None` in 2025.
- **ERS deploy mode 3** means Overtake in 2025 and Boost in 2026.
- **Session** appends active aero status and zones, DRS zones, a reaction time and assist flags (753 → 926 bytes).
- **CarTelemetry2 (16) is new in 2026.** The base game never sends it.
- **`formula` 13 (F1 26) is new.** 0 is F1 Modern and 2 is F2, in both formats.

## Game behaviour worth knowing

Observed in real recordings (F1 25 v1.26, `packetVersion` 1), and the reason several backend rules exist. The
committed fixtures in `tests/fixtures/` pin the ones the parsers can show.

- **Time Trial sends no `SSTA` or `SEND` event**, so session detection can't rely on events alone; a UID change or a
  packet timeout has to end a session. Time Trial also freezes tyre temperatures, engine temperature, fuel, ERS store
  and tyre wear, so those fields need a race session to verify.
- **At the chequered flag `currentLapNum` does not increment**; only `lastLapTimeInMS` changes. Lap segmentation has
  to close a lap on that change too. `resultStatus` becomes 3 (finished) at the same moment.
- **Menus emit a few packets with `sessionUID` 0.** Ignore them.
- **Flashbacks:** the `FLBK` event carries the target frame and is sent with the pre-rewind frame id in its header.
  After the game resumes, `frameIdentifier` restarts from the target while `overallFrameIdentifier` keeps counting.
  The game is paused in between, so there's a gap in the stream with no telemetry. Flashbacks can be chained, sending
  decreasing frame ids, and they also undo damage (a 44% wing became 0%).
- **`lapDistance` is negative before the start line** (−1333 at the start of a Monza Time Trial lap), but on a race
  grid it can be either sign (+297.9 at Monza, −60 at Melbourne).
- **Pit stops:** `pitStatus` goes 1 (lane) → 2 (box) → 1 → 0 and `driverStatus` 2 (in lap) → 3 (out lap) → 4 (on
  track). The compound change, tyre age reset and wing repairs all happen while `pitStatus` is 2. New tyres come on
  cold, around 32 °C.
- **F2 (`formula` 2):** ERS and overtake data are meaningless, `regulations2026Applicable` is false, and the top gear
  is 6 at 8750 RPM. The 2026 Session packet **still lists active aero zones for F2**, so the UI must gate 2026
  widgets on the `regulations2026Applicable` flag, never on zone presence.
- **Active aero zones can wrap the start/finish line**, so a zone's start fraction may be greater than its end
  (0.954 → 0.152 at Monza).
- **`maxGears` reads one above the top usable gear** (9 for F1, 7 for F2).
- **`BUTN` events spam** 2 to 3 per second while any button is held. Other codes seen: `STLG`, `LGOT`, `OVTK`,
  `SPTP`, `COLL`, `PENA`, `DRSE`, `CHQF`, `RCWN`, `OVEN`. The `SEND` event arrives with `frameIdentifier` 0.

## Parsing cost

`tools/bench_parse.py` times `PacketDispatcher.parse` per packet type. On the committed fixtures and on full
recordings it stays between 1.1 and 2.7 µs for a parsed packet, and about 0.15 µs for one the dispatcher drops on
`packetId` — roughly 6 µs of work per 60 Hz frame, against a 50 µs per-packet budget.

```sh
uv run python tools/bench_parse.py                          # committed fixtures
uv run python tools/bench_parse.py recordings/race-2026.f1raw --rounds 3
```
