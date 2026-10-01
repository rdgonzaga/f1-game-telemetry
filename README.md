# F1 Game Telemetry

A free telemetry dashboard for **F1 25** and the **2026 Season Pack**. It runs on your own PC, reads the game's UDP
telemetry and shows it in the browser. Nothing is uploaded anywhere.

<!-- screenshots: Live, Sessions, Lap and Compare -->

## Features

- **Live:** speed, gear, revs and inputs, tyre and brake temperatures with wear, lap and sector timing with a delta
  to your best lap, ERS, overtake and active aero, and safety car or red flag status.
- **Sessions:** every session is saved with its laps. Flashbacks and mid-race save reloads are undone, so a lap
  holds what you actually drove.
- **Lap analysis:** speed, throttle, brake, steering and gear traces for any saved lap.
- **Compare:** two laps overlaid by distance, with the running delta and 25 minisectors.
- **Record and replay:** keep the raw packets of a session and play them back without the game running.

Works with UDP format 2026 and 2025, F1 and F2, on PC. PS5 and Xbox work too, with the PC on the same network.

## Quick start

You need [Python 3.12+](https://www.python.org/downloads/), [uv](https://docs.astral.sh/uv/) and
[Node.js 22](https://nodejs.org/) (Node only builds the dashboard once).

```sh
git clone https://github.com/rdgonzaga/f1-game-telemetry.git
cd f1-game-telemetry
uv sync
cd frontend && npm ci && npm run build && cd ..
uv run f1telemetry
```

The dashboard opens at <http://127.0.0.1:20778>. In the game, open **Settings → Telemetry Settings** and set:

| Setting | Value |
|---|---|
| UDP Telemetry | On |
| UDP Broadcast Mode | Off |
| UDP IP Address | 127.0.0.1 |
| UDP Port | 20777 |
| UDP Send Rate | 60Hz |
| UDP Format | 2026 (or 2025 without the Season Pack) |

Start a session and the Live page fills in. The **Setup** page in the dashboard shows the same values and whether
packets are arriving.

Consoles, command-line options, where your data is kept and troubleshooting are in the
[setup guide](docs/setup.md).

## Roadmap

- A Windows app that opens in its own window, with no Python or Node to install.
- `pip install f1-game-telemetry` / `uvx f1telemetry`.
- A small website with docs and a demo.

Progress is tracked on the [roadmap board](https://github.com/users/rdgonzaga/projects/3).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Packet layouts and the game behaviour the app relies on are in
[docs/udp-spec.md](docs/udp-spec.md).

## License

[MIT](LICENSE). Not affiliated with Formula 1, the FIA or Electronic Arts.
