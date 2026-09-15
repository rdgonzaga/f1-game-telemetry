# AGENTS.md

Guidance for AI coding agents working in this repository. Humans should start with [CONTRIBUTING.md](CONTRIBUTING.md).

## Project

Free, MIT-licensed localhost telemetry dashboard for **F1 25 with the 2026 Season Pack** (UDP formats 2025 and 2026).
Backend: Python >= 3.12, uv, FastAPI. Frontend (planned): Vite, React, TypeScript, Tailwind, uPlot. The frontend must stay a static SPA.

## Setup and checks

```sh
uv sync                  # install Python deps
uv run pytest            # tests
uv run ruff check .      # lint
uv run ruff format .     # format
uv run mypy              # strict type check
```

Record and replay game UDP without the game running:

```sh
uv run python tools/record_raw.py --out recordings/lap.f1raw
uv run python tools/replay_raw.py recordings/lap.f1raw --speed 2
```

## Layout

- `f1telemetry/` backend package (`rawfile.py` = `.f1raw` recording format)
- `tools/` developer scripts (UDP recorder and replayer)
- `tests/` pytest suite; small committed recordings go in `tests/fixtures/`
- `recordings/`, `data/` local, gitignored

## Performance rules

Efficiency is a hard requirement; the dashboard must never feel laggy.

- Parse only the player car with precompiled `struct.Struct` objects; no per-packet allocations you can avoid.
- Keep blocking disk I/O off the asyncio loop.
- Throttle live WebSocket snapshots (30 Hz).
- Frontend: never trigger a React re-render per telemetry frame; write live gauges through refs and `requestAnimationFrame`.

## Conventions

- Branches: `<type>/<issue#>-slug` off `main`.
- Commits and PR titles: semantic subject only, no body (`feat(parser): parse CarTelemetry2 packet`). CI enforces this.
- PRs follow `.github/pull_request_template.md`, include `closes #N`, and copy the issue labels. Squash merge only.
- Issues use `[CATEGORY] Title Case` with Description, Requirements, Acceptance Criteria sections.
