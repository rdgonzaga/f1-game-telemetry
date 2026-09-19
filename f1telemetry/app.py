"""The app server: FastAPI on the same asyncio loop as the UDP listener, session tracker, recorder and live feed.

Endpoints: `/ws/live` (see `live_feed`), `/api/sessions` to list, load and delete saved sessions and laps, and
`/api/setup` for the connection screen.

`create_app` builds the app and `make_server` wraps it in a uvicorn server. The CLI runs that server on the main
thread; `ServerThread` runs it on a background thread and stops it from code, which the desktop window app needs.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from pydantic import BaseModel

from f1telemetry.listener import TelemetryProtocol, open_listener
from f1telemetry.live import LiveState
from f1telemetry.live_feed import FeedClient, LiveFeed
from f1telemetry.parsers import make_dispatcher
from f1telemetry.settings import ListenMode, Settings, lan_ipv4_addresses
from f1telemetry.store import Json, SessionRecorder, SessionStore
from f1telemetry.tracker import SessionTracker, TrackerEvent

log = logging.getLogger(__name__)

# `npm run build` writes the dashboard here; a missing folder means the API runs alone (development).
WEB_DIR = Path(__file__).parent / "web"
# The Vite dev server, which calls the API from another origin while the frontend is being worked on.
DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


class Telemetry:
    """The UDP side: listener, live state, session tracker, recorder and live feed. The app's lifespan runs it."""

    def __init__(self, settings: Settings, data_dir: Path) -> None:
        self.settings = settings
        self.state = LiveState()
        self.store = SessionStore(data_dir)
        self.recorder = SessionRecorder(self.store)
        self.feed = LiveFeed(self.state, self.recorder)
        self.tracker = SessionTracker(self._on_tracker_event)
        self.dispatcher = make_dispatcher()
        self.protocol: TelemetryProtocol | None = None
        self.udp_port = settings.udp_port  # the bound port once started; differs when settings ask for port 0
        self._transport: asyncio.DatagramTransport | None = None
        self._feed_task: asyncio.Task[None] | None = None

    def _on_tracker_event(self, event: TrackerEvent) -> None:
        # Recorder first: the feed sends the session summary the recorder just built.
        self.recorder.on_event(event)
        self.feed.on_event(event)

    async def start(self) -> None:
        host = self.settings.udp_host
        try:
            transport = await open_listener(
                self.state, host, self.settings.udp_port, self.dispatcher, tracker=self.tracker
            )
        except OSError as error:
            log.error(
                "Can't listen for game packets on UDP %s:%d (%s). Is another telemetry app using that port?",
                host,
                self.settings.udp_port,
                error,
            )
            raise
        self._transport = transport
        protocol = transport.get_protocol()
        assert isinstance(protocol, TelemetryProtocol)
        self.protocol = protocol
        self.udp_port = transport.get_extra_info("sockname")[1]
        log.info("Listening for game telemetry on UDP %s:%d", host, self.udp_port)
        self._feed_task = asyncio.create_task(self.feed.run(), name="live-feed")

    async def stop(self) -> None:
        """Stop listening, then close the open session before the recorder so its final write isn't lost."""
        if self._transport is not None:
            self._transport.close()
            self._transport = None
        self.tracker.close()
        if self._feed_task is not None:
            self._feed_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._feed_task
            self._feed_task = None
        await asyncio.to_thread(self.recorder.close)


class SetupInfo(BaseModel):
    listen_mode: ListenMode
    udp_host: str
    udp_port: int
    lan_addresses: list[str]  # what a console on the same network should send to, in network mode
    connected: bool
    packet_format: int | None
    packet_warning: str | None  # e.g. an unsupported UDP format selected in the game
    packet_errors: int


def create_app(telemetry: Telemetry, web_dir: Path = WEB_DIR) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await telemetry.start()
        try:
            yield
        finally:
            await telemetry.stop()

    app = FastAPI(title="F1 Game Telemetry", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=DEV_ORIGINS, allow_methods=["*"], allow_headers=["*"])

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/setup")
    async def setup() -> SetupInfo:
        state = telemetry.state
        protocol = telemetry.protocol
        return SetupInfo(
            listen_mode=telemetry.settings.listen_mode,
            udp_host=telemetry.settings.udp_host,
            udp_port=telemetry.udp_port,
            # Resolving the host name can block, so it runs off the loop.
            lan_addresses=await asyncio.to_thread(lan_ipv4_addresses),
            connected=state.connected(time.monotonic_ns()),
            packet_format=state.packet_format,
            packet_warning=telemetry.dispatcher.last_warning,
            packet_errors=protocol.errors if protocol is not None else 0,
        )

    _add_sessions(app, telemetry)
    _add_live(app, telemetry.feed)
    _add_frontend(app, web_dir)
    return app


def _with_status(session: Json, active_session_id: str | None) -> Json:
    """Add `status`: `recording`, `complete`, or `interrupted` for one the app stopped writing without ending it."""
    if session.get("id") == active_session_id:
        status = "recording"
    elif session.get("ended_at") is None:
        status = "interrupted"
    else:
        status = "complete"
    return {**session, "status": status}


def _add_sessions(app: FastAPI, telemetry: Telemetry) -> None:
    store, recorder = telemetry.store, telemetry.recorder

    @app.get("/api/sessions")
    async def list_sessions() -> list[Json]:
        """Saved sessions, newest first."""
        sessions = await asyncio.to_thread(store.list_sessions)
        return [_with_status(session, recorder.active_session_id) for session in sessions]

    @app.get("/api/sessions/{session_id}")
    async def get_session(session_id: str) -> Json:
        try:
            session = await asyncio.to_thread(store.load_session, session_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="no such session") from None
        return _with_status(session, recorder.active_session_id)

    @app.get("/api/sessions/{session_id}/laps/{number}")
    async def get_lap(session_id: str, number: int) -> Response:
        """A lap's samples as columns, served as saved: laps run to hundreds of KB, so they aren't re-encoded."""
        try:
            data = await asyncio.to_thread(store.lap_bytes, session_id, number)
        except KeyError:
            raise HTTPException(status_code=404, detail="no such lap") from None
        return Response(data, media_type="application/json")

    @app.delete("/api/sessions/{session_id}", status_code=204)
    async def delete_session(session_id: str) -> None:
        if session_id == recorder.active_session_id:
            # The recorder would write it again with its next lap.
            raise HTTPException(status_code=409, detail="the session is still being recorded")
        try:
            await asyncio.wrap_future(recorder.delete(session_id))
        except KeyError:
            raise HTTPException(status_code=404, detail="no such session") from None


def _add_live(app: FastAPI, feed: LiveFeed) -> None:
    @app.websocket("/ws/live")
    async def live(websocket: WebSocket) -> None:
        await websocket.accept()
        client = feed.join()
        sender = asyncio.create_task(_send_feed(websocket, client))
        try:
            # Nothing is expected from the dashboard; receiving only notices when it goes away.
            while (await websocket.receive())["type"] != "websocket.disconnect":
                pass
        finally:
            feed.leave(client)
            sender.cancel()
            # A send to a closed socket may have failed first; either way the client is gone.
            await asyncio.gather(sender, return_exceptions=True)


async def _send_feed(websocket: WebSocket, client: FeedClient) -> None:
    while True:
        for message in await client.next_messages():
            await websocket.send_text(message)


def _add_frontend(app: FastAPI, web_dir: Path) -> None:
    """Serve the built single-page app; any path that isn't a file gets `index.html` so client routes work."""
    root = web_dir.resolve()
    index = root / "index.html"
    if not index.is_file():

        @app.get("/", include_in_schema=False)
        async def not_built() -> Response:
            return PlainTextResponse("The dashboard isn't built yet. The API is running: see /docs.")

        return

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend(path: str) -> Response:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = (root / path).resolve()
        if candidate.is_relative_to(root) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)


def make_server(app: FastAPI, settings: Settings) -> uvicorn.Server:
    config = uvicorn.Config(
        app,
        host=settings.http_host,
        port=settings.http_port,
        access_log=False,
        log_config=None,  # keep the app's own logging setup
        lifespan="on",
    )
    return uvicorn.Server(config)


def server_port(server: uvicorn.Server) -> int:
    """The HTTP port actually bound, once the server has started."""
    return int(server.servers[0].sockets[0].getsockname()[1])


class ServerThread:
    """Runs the app server on a background thread, so a desktop window can own the main thread."""

    def __init__(self, server: uvicorn.Server) -> None:
        self.server = server
        self.url = ""  # set once started
        self._thread = threading.Thread(target=self._run, name="app-server", daemon=True)

    def _run(self) -> None:
        # uvicorn exits when startup fails; `start()` reports that from `server.started`.
        with contextlib.suppress(SystemExit):
            self.server.run()

    def start(self, timeout: float = 10.0) -> None:
        """Start and wait until requests are accepted; raises RuntimeError if the server fails to start."""
        self._thread.start()
        deadline = time.monotonic() + timeout
        while not self.server.started:
            if not self._thread.is_alive():
                raise RuntimeError("the app server failed to start; see the log for why")
            if time.monotonic() > deadline:
                raise RuntimeError(f"the app server didn't start within {timeout:.0f} s")
            time.sleep(0.02)
        self.url = f"http://{self.server.config.host}:{server_port(self.server)}"

    def stop(self, timeout: float = 10.0) -> None:
        """Shut down gracefully: the lifespan closes the open session and waits for its files to be written."""
        self.server.should_exit = True
        self._thread.join(timeout)
