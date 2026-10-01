# Setup guide

Install and first run are in the [README](../README.md#quick-start). This page covers the rest.

## Game settings

In F1 25, open **Settings → Telemetry Settings**:

| Setting | Value | Notes |
|---|---|---|
| UDP Telemetry | On | |
| UDP Broadcast Mode | Off | |
| UDP IP Address | 127.0.0.1 | On a console, this PC's network address instead (below). |
| UDP Port | 20777 | Must match the app's UDP port. |
| UDP Send Rate | 60Hz | 20Hz works, with coarser traces. |
| UDP Format | 2026 | 2025 works too, for F1 25 without the 2026 Season Pack. |

The dashboard's **Setup** page shows these values for your setup, and its dot turns green once packets arrive.
You can change the UDP port there too.

## PS5 and Xbox

The console sends to the PC over your home network, so both have to be on the same network.

1. Start the app in network mode:

   ```sh
   uv run f1telemetry --network
   ```

   Or pick PS5 or Xbox on the Setup page and turn network mode on there. The app remembers the choice.
2. The app prints this PC's address (`Network mode: in the game, set the UDP IP address to 192.168.x.x ...`). The
   Setup page shows it too.
3. On the console, set **UDP IP Address** to that address and the rest as in the table above.
4. Windows asks whether to let the app through the firewall. Allow it on **private networks**.

## Options

```sh
uv run f1telemetry [options]
```

| Option | What it does |
|---|---|
| `--network` / `--local` | Take packets from other devices on the network, or from this PC only (the default). |
| `--udp-port N` | The port the game sends to. Default 20777. |
| `--port N` | The dashboard port. Default 20778. |
| `--no-browser` | Don't open the dashboard on start. |
| `--record` | Also keep every raw packet in `<data dir>/recordings`, about 1-2.5 GB per hour driven. |
| `--data-dir PATH` | Keep sessions and settings somewhere else. |

Options you pass on the command line win over `settings.json`.

## Your data

Sessions, raw recordings and `settings.json` live in:

- Windows: `%LOCALAPPDATA%\F1Telemetry`
- macOS and Linux: `~/.local/share/f1telemetry` (or `$XDG_DATA_HOME/f1telemetry`)

Each session is a folder with a `session.json` and a `laps` folder holding one file per lap. Delete a session from its page in the
dashboard, or delete the folder.

## Record and replay

Replay sends a recording to the app as if the game were running, which is handy for trying the dashboard
without driving:

```sh
uv run f1telemetry record --out recordings/monza.f1raw      # while the game is running, with the app closed
uv run f1telemetry replay recordings/monza.f1raw --speed 2  # with the app running
```

`record` and the app both need UDP port 20777, so run one at a time. To record while using the dashboard, start
the app with `--record` instead.

## Troubleshooting

**The dashboard says "Waiting for game".** Nothing has arrived on the UDP port yet.

- UDP Telemetry is On and you're on track in a session, not in a menu.
- The IP address and port in the game match the Setup page exactly.
- Broadcast Mode is Off.
- On a console: the app runs with `--network`, the address is this PC's, and the firewall allows the app.

**"Paused" with "no packets for Ns".** The game stopped sending: it's paused, in a menu or the session ended. The
last values stay on screen until it sends again.

**`can't listen for game packets on UDP port 20777`.** Another app is using the port, often another telemetry
tool or a second copy of this one. Close it, or use another port in both the app (`--udp-port 20787`) and the game.

**`can't serve the dashboard on 127.0.0.1:20778`.** The app is probably already running, so open
<http://127.0.0.1:20778>. Or start it with `--port 20788`.

**Console packets never arrive.** Check the firewall: Windows Security → Firewall & network protection → Allow an
app through firewall, and allow Python on private networks. Make sure the network is set to Private in Windows,
not Public.

**The page is blank or says Not Found.** The dashboard hasn't been built. Run `npm ci && npm run build` in
`frontend/`, then restart the app.

Still stuck? [Open an issue](https://github.com/rdgonzaga/f1-game-telemetry/issues) with the app's console output.
