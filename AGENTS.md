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

Frontend, run from `frontend/`: `npm ci`, `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`.
`npm run dev` serves the SPA on 5173 against the API on 20778; `npm run build` writes into `f1telemetry/web/`.
`npm run gen:api` regenerates `frontend/src/api/schema.ts` from the backend; run it after changing a response shape.
CI (`.github/workflows/ci.yml`) runs every command above and skips a side whose directory doesn't exist yet.

Run the app (UDP listener, session tracking and saving, API) and open the dashboard:

```sh
uv run f1telemetry                    # --no-browser, --network for PS5/Xbox, --data-dir, --udp-port, --port
```

Sessions and `settings.json` live in `%LOCALAPPDATA%\F1Telemetry` (Windows) or `~/.local/share/f1telemetry`.

Record and replay game UDP without the game running:

```sh
uv run f1telemetry record --out recordings/lap.f1raw
uv run f1telemetry replay recordings/lap.f1raw --speed 2
uv run python tools/inspect_raw.py recordings/lap.f1raw     # sizes, sessions, events, lap/pit/tyre timeline
uv run python tools/trim_raw.py recordings/lap.f1raw tests/fixtures/x.f1raw --start 60 --end 61
uv run python tools/bench_parse.py                            # parse time per packet type
```

## Layout

- `f1telemetry/` backend package (`cli.py` = the `f1telemetry` command, `app.py` = FastAPI server, `settings.py`, `rawfile.py` = `.f1raw` recording format, `recorder.py` + `replayer.py`, `listener.py` + `live.py` = UDP intake and live state, `live_feed.py` = `/ws/live` snapshots and events, `tracker.py` = session and lap tracking, `store.py` = saved sessions, `compare.py` = distance resampling, lap delta and minisectors)
- `f1telemetry/schemas.py` response shapes for the OpenAPI document only, and `openapi.py` which dumps it; the routes keep their `dict` returns, so nothing here runs per request
- `frontend/` the SPA (`src/api/` generated types and the typed client, `src/styles/tokens.css` the values and `theme.css` the Tailwind and shadcn aliases onto them, `src/routes/` one file per route)
- `tools/` developer scripts (inspector, trimmer and parse benchmark)
- `docs/udp-spec.md` packet layouts, format differences and real-game behaviour the backend relies on
- `docs/design.md` the design direction, colour semantics and state rules the tokens encode; if a component seems to need a new design decision, it belongs there or in `tokens.css`, not in the component
- `tests/` pytest suite; small committed recordings go in `tests/fixtures/` (see its README); what belongs there is under Testing below
- `recordings/`, `data/` local, gitignored

## Performance rules

Efficiency is a hard requirement; the dashboard must never feel laggy.

- Parse only the player car with precompiled `struct.Struct` objects; no per-packet allocations you can avoid.
- Keep blocking disk I/O off the asyncio loop.
- Throttle live WebSocket snapshots (30 Hz).
- Frontend: never trigger a React re-render per telemetry frame; write live gauges through refs and `requestAnimationFrame`.

## Testing

- Never write unit tests after you write code.
- Highly prefer E2E tests as the sole testing mechanism, and use them to verify complex features work. Here that means replaying a real `.f1raw` from `tests/fixtures/` through the app (`tests/test_app.py`, `tests/test_fixtures.py`). An E2E test ends in a verifiable, repeatable artifact: a committed fixture plus the saved session, lap or feed output asserted from it.
- If you must test a system in isolation, first write down all the ways it could fail, then write the code. The performance rules above and measured game behaviour no recording contains are the usual reasons to.

## Conventions

- Branches: `<type>/<issue#>-slug` off `main`.
- Commits and PR titles: semantic subject only, no body (`feat(parser): parse CarTelemetry2 packet`). CI enforces this.
- PRs follow `.github/pull_request_template.md`, include `closes #N`, and copy the issue labels. Squash merge only.
- Issues use `[CATEGORY] Title Case` with Description, Requirements, Acceptance Criteria sections.
