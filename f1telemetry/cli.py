"""The `f1telemetry` command: run the app (the default), or record and replay raw game packets.

f1telemetry                      start the app and open the dashboard in the browser
f1telemetry serve --network      also take packets from a PS5 or Xbox on the same network
f1telemetry record --out lap.f1raw
f1telemetry replay lap.f1raw --speed 2
"""

from __future__ import annotations

import argparse
import logging
import signal
import socket
import sys
import threading
import time
import webbrowser
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import uvicorn

from f1telemetry import recorder, replayer
from f1telemetry.settings import LOCAL_HOST, lan_ipv4_addresses, load_settings, with_overrides
from f1telemetry.store import default_data_dir

log = logging.getLogger("f1telemetry")

COMMANDS = ("serve", "record", "replay")
BROWSER_WAIT_S = 10.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="f1telemetry", description="Telemetry dashboard for F1 25.")
    commands = parser.add_subparsers(dest="command", metavar="{serve,record,replay}")

    serve = commands.add_parser("serve", help="start the app (the default command)")
    serve.add_argument("--data-dir", type=Path, help="where sessions and settings.json live")
    mode = serve.add_mutually_exclusive_group()
    mode.add_argument(
        "--network",
        dest="listen_mode",
        action="store_const",
        const="network",
        help="take packets from other devices on the network, such as a PS5 or Xbox",
    )
    mode.add_argument(
        "--local", dest="listen_mode", action="store_const", const="local", help="take packets from this PC only"
    )
    serve.add_argument("--udp-port", type=int, help="port the game sends to (default 20777)")
    serve.add_argument("--host", dest="http_host", help=f"dashboard address (default {LOCAL_HOST})")
    serve.add_argument("--port", dest="http_port", type=int, help="dashboard port (default 20778)")
    serve.add_argument("--no-browser", action="store_true", help="don't open the dashboard in a browser")

    record = commands.add_parser("record", help="record raw game packets to an .f1raw file")
    record.add_argument("--out", type=Path, help="output file (default recordings/<timestamp>.f1raw)")
    record.add_argument("--host", default=recorder.DEFAULT_HOST)
    record.add_argument("--port", type=int, default=recorder.DEFAULT_PORT)
    record.add_argument("--force", action="store_true", help="replace the output file if it exists")

    replay = commands.add_parser("replay", help="send an .f1raw recording to a UDP port with its original timing")
    replay.add_argument("path", type=Path)
    replay.add_argument("--host", default=replayer.DEFAULT_HOST)
    replay.add_argument("--port", type=int, default=replayer.DEFAULT_PORT)
    replay.add_argument("--speed", type=float, default=1.0, help="playback multiplier (2 = twice as fast)")
    return parser


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    args = list(argv)
    # No command, or only options, means `serve`.
    if not args or (args[0] not in COMMANDS and args[0] not in ("-h", "--help")):
        args.insert(0, "serve")
    return build_parser().parse_args(args)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if args.command == "record":
        run_record(args)
    elif args.command == "replay":
        run_replay(args)
    else:
        run_serve(args)


def run_serve(args: argparse.Namespace) -> None:
    # Imported here so `record` and `replay` start without loading FastAPI.
    from f1telemetry.app import Telemetry, create_app, make_server, server_port

    data_dir: Path = args.data_dir or default_data_dir()
    try:
        settings = with_overrides(
            load_settings(data_dir),
            listen_mode=args.listen_mode,
            udp_port=args.udp_port,
            http_host=args.http_host,
            http_port=args.http_port,
        )
    except ValueError as error:
        sys.exit(f"f1telemetry: {error}")

    # Checked up front so a taken port gives one clear line instead of a traceback from the server.
    problem = port_problem(socket.SOCK_DGRAM, settings.udp_host, settings.udp_port)
    if problem:
        sys.exit(
            f"f1telemetry: can't listen for game packets on UDP port {settings.udp_port} ({problem}). "
            "Is another telemetry app running? Close it or pick another port with --udp-port."
        )
    problem = port_problem(socket.SOCK_STREAM, settings.http_host, settings.http_port)
    if problem:
        sys.exit(
            f"f1telemetry: can't serve the dashboard on {settings.http_host}:{settings.http_port} ({problem}). "
            "Is the app already running? Close it or pick another port with --port."
        )

    server = make_server(create_app(Telemetry(settings, data_dir)), settings)
    log.info("Saving sessions to %s", data_dir)
    if settings.listen_mode == "network":
        addresses = ", ".join(lan_ipv4_addresses()) or "no network address found"
        log.info("Network mode: in the game, set the UDP IP address to %s and port %d", addresses, settings.udp_port)

    def announce() -> None:
        if not _wait_until_started(server):
            return
        url = f"http://{settings.http_host}:{server_port(server)}"
        log.info("Dashboard: %s (Ctrl+C to stop)", url)
        if not args.no_browser:
            webbrowser.open(url)

    threading.Thread(target=announce, name="announce", daemon=True).start()
    server.run()
    if not server.started:
        sys.exit(1)


def port_problem(kind: socket.SocketKind, host: str, port: int) -> str | None:
    """Why a UDP (SOCK_DGRAM) or TCP (SOCK_STREAM) port can't be bound, or None when it's free."""
    with socket.socket(socket.AF_INET, kind) as probe:
        if kind == socket.SOCK_STREAM and sys.platform != "win32":
            # Match uvicorn, so a port left in TIME_WAIT by a restart doesn't read as taken. Not on Windows,
            # where SO_REUSEADDR would let the probe share a port another process is listening on.
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
        except OSError as error:
            return error.strerror or str(error)
    return None


def _wait_until_started(server: uvicorn.Server) -> bool:
    deadline = time.monotonic() + BROWSER_WAIT_S
    while not server.started:
        if server.should_exit or time.monotonic() > deadline:
            return False
        time.sleep(0.05)
    return True


def run_record(args: argparse.Namespace) -> None:
    out: Path = args.out or Path("recordings") / f"{datetime.now():%Y%m%d-%H%M%S}.f1raw"
    if out.exists() and not args.force:
        sys.exit(f"f1telemetry: {out} already exists; pick another --out or pass --force to replace it")
    if hasattr(signal, "SIGBREAK"):
        # Ctrl+Break on Windows stops the recording cleanly too, like Ctrl+C.
        signal.signal(signal.SIGBREAK, signal.default_int_handler)
    print(f"Recording {args.host}:{args.port} -> {out} (Ctrl+C to stop)")
    try:
        count = recorder.record(out, args.host, args.port, overwrite=args.force)
    except FileExistsError:
        sys.exit(f"f1telemetry: {out} already exists; pick another --out or pass --force to replace it")
    print(f"Saved {count} packets to {out}")


def run_replay(args: argparse.Namespace) -> None:
    if args.speed <= 0:
        sys.exit("f1telemetry: --speed must be > 0")
    print(f"Replaying {args.path} -> {args.host}:{args.port} at {args.speed}x (Ctrl+C to stop)")
    try:
        count = replayer.replay(args.path, args.host, args.port, args.speed)
    except KeyboardInterrupt:
        print("Stopped")
        return
    print(f"Sent {count} packets")
