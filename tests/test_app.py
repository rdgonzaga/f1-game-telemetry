"""The app server: API endpoints, frontend serving, start and stop from code, and packets end to end."""

from __future__ import annotations

import json
import socket
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from f1telemetry.app import ServerThread, Telemetry, create_app, make_server
from f1telemetry.rawfile import read_records
from f1telemetry.settings import Settings
from f1telemetry.store import SessionStore, write_json_atomic

FIXTURES = Path(__file__).parent / "fixtures"
# Port 0 everywhere: the OS picks free ports, so tests never collide with a running app or each other.
SETTINGS = Settings(udp_port=0, http_port=0)


def client(data_dir: Path, web_dir: Path | None = None) -> tuple[TestClient, Telemetry]:
    telemetry = Telemetry(SETTINGS, data_dir)
    app = create_app(telemetry) if web_dir is None else create_app(telemetry, web_dir)
    return TestClient(app), telemetry


def send(port: int, packets: list[bytes]) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as tx:
        for data in packets:
            tx.sendto(data, ("127.0.0.1", port))


def wait_for(condition: Callable[[], bool], timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.01)


def test_health_and_setup_before_any_packets(tmp_path: Path) -> None:
    test_client, telemetry = client(tmp_path)
    with test_client:
        assert test_client.get("/api/health").json() == {"status": "ok"}
        setup = test_client.get("/api/setup").json()

    assert setup["listen_mode"] == "local"
    assert setup["udp_host"] == "127.0.0.1"
    assert setup["udp_port"] == telemetry.udp_port != 0
    assert (setup["connected"], setup["packet_format"], setup["packet_warning"], setup["packet_errors"]) == (
        False,
        None,
        None,
        0,
    )
    assert isinstance(setup["lan_addresses"], list)


def test_packets_reach_live_state_and_the_session_is_saved_on_shutdown(tmp_path: Path) -> None:
    packets = [data for _, data in read_records(FIXTURES / "race-2026-monza-finish.f1raw")]
    test_client, telemetry = client(tmp_path)
    with test_client:
        send(telemetry.udp_port, packets)
        wait_for(lambda: telemetry.state.packets_seen == len(packets))
        setup = test_client.get("/api/setup").json()
        assert (setup["connected"], setup["packet_format"]) == (True, 2026)

    # Leaving the client runs the shutdown: tracker closed, then the recorder's writes flushed.
    [saved] = SessionStore(tmp_path).list_sessions()
    assert [(lap["number"], lap["lap_time_ms"]) for lap in saved["laps"]] == [(3, 83561)]


def test_wrong_udp_format_shows_on_setup(tmp_path: Path) -> None:
    test_client, telemetry = client(tmp_path)
    with test_client:
        send(telemetry.udp_port, [(2024).to_bytes(2, "little") + bytes(40)])
        wait_for(lambda: telemetry.state.packets_seen == 1)
        warning = test_client.get("/api/setup").json()["packet_warning"]

    assert "2024" in warning and "2025 or 2026" in warning


def test_open_session_is_closed_when_the_app_stops(tmp_path: Path) -> None:
    records = list(read_records(FIXTURES / "race-2026-monza-finish.f1raw"))
    # Everything before the flag, so a lap is still in progress when the app stops.
    before_flag = [data for t, data in records if t < 600_000_000]
    test_client, telemetry = client(tmp_path)
    with test_client:
        send(telemetry.udp_port, before_flag)
        wait_for(lambda: telemetry.state.packets_seen == len(before_flag))
        assert telemetry.recorder.active_session_id is not None

    assert telemetry.tracker.session is None
    assert telemetry.recorder.active_session_id is None
    # No lap completed, so nothing is kept.
    assert SessionStore(tmp_path).list_sessions() == []


def save_session(data_dir: Path, session_id: str, *, ended: bool = True) -> Path:
    folder = SessionStore(data_dir).root / session_id
    ended_at = "2026-09-18T23:30:00" if ended else None
    write_json_atomic(folder / "session.json", {"id": session_id, "ended_at": ended_at, "laps": [{"number": 1}]})
    write_json_atomic(folder / "laps" / "lap_01.json", {"number": 1, "columns": {"speed": [250, 251]}})
    return folder


def test_sessions_are_listed_newest_first_with_their_status(tmp_path: Path) -> None:
    save_session(tmp_path, "20260918-231502_monza_race")
    save_session(tmp_path, "20260919-101500_jeddah_race", ended=False)
    test_client, _ = client(tmp_path)
    with test_client:
        sessions = test_client.get("/api/sessions").json()
        one = test_client.get("/api/sessions/20260918-231502_monza_race").json()

    assert [(s["id"], s["status"]) for s in sessions] == [
        ("20260919-101500_jeddah_race", "interrupted"),
        ("20260918-231502_monza_race", "complete"),
    ]
    assert one == {**sessions[1]}


def test_a_lap_is_served_as_saved(tmp_path: Path) -> None:
    folder = save_session(tmp_path, "20260918-231502_monza_race")
    test_client, _ = client(tmp_path)
    with test_client:
        response = test_client.get("/api/sessions/20260918-231502_monza_race/laps/1")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.content == (folder / "laps" / "lap_01.json").read_bytes()


@pytest.mark.parametrize(
    "path",
    [
        "/api/sessions/20260101-000000_nowhere_race",
        "/api/sessions/20260918-231502_monza_race/laps/2",
        "/api/sessions/20260101-000000_nowhere_race/laps/1",
        "/api/sessions/..%2F..%2Fsecret",
    ],
)
def test_missing_sessions_and_laps_are_404(tmp_path: Path, path: str) -> None:
    save_session(tmp_path, "20260918-231502_monza_race")
    test_client, _ = client(tmp_path)
    with test_client:
        assert test_client.get(path).status_code == 404


def test_delete_a_session(tmp_path: Path) -> None:
    folder = save_session(tmp_path, "20260918-231502_monza_race")
    test_client, _ = client(tmp_path)
    with test_client:
        assert test_client.delete("/api/sessions/20260918-231502_monza_race").status_code == 204
        assert not folder.exists()
        assert test_client.delete("/api/sessions/20260918-231502_monza_race").status_code == 404
        assert test_client.get("/api/sessions").json() == []


def test_the_session_being_recorded_cant_be_deleted(tmp_path: Path) -> None:
    records = list(read_records(FIXTURES / "race-2026-monza-finish.f1raw"))
    before_flag = [data for t, data in records if t < 600_000_000]
    test_client, telemetry = client(tmp_path)
    with test_client:
        send(telemetry.udp_port, before_flag)
        wait_for(lambda: telemetry.state.packets_seen == len(before_flag))
        active = telemetry.recorder.active_session_id
        assert active is not None
        response = test_client.delete(f"/api/sessions/{active}")

    assert response.status_code == 409


def test_live_feed_streams_snapshots_and_session_events(tmp_path: Path) -> None:
    packets = [data for _, data in read_records(FIXTURES / "race-2026-monza-finish.f1raw")]
    test_client, telemetry = client(tmp_path)
    with test_client, test_client.websocket_connect("/ws/live") as live:
        hello, first = live.receive_json(), live.receive_json()
        assert hello == {"type": "hello", "session": None}
        assert (first["type"], first["connected"], first["telemetry"]) == ("snapshot", False, None)

        send(telemetry.udp_port, packets)
        events: list[dict[str, Any]] = []
        # The burst can be handled within one tick, so the events may all come before the next snapshot.
        while not events or events[-1]["type"] != "session_ended":
            message = live.receive_json()
            if message["type"] != "snapshot":
                events.append(message)
        snapshot = live.receive_json()
        while snapshot["type"] != "snapshot":
            snapshot = live.receive_json()

    assert [m["type"] for m in events] == ["session_started", "lap_completed", "session_ended"]
    assert (events[1]["lap"]["number"], events[1]["lap"]["lap_time_ms"]) == (3, 83561)
    assert events[2]["session"]["id"] == events[0]["session"]["id"]
    assert (snapshot["connected"], snapshot["packet_format"], snapshot["lap"]["current_lap_num"]) == (True, 2026, 3)
    # The client left, so the feed stops sending to it.
    assert telemetry.feed.clients == set()


def test_without_a_built_frontend_the_root_explains(tmp_path: Path) -> None:
    test_client, _ = client(tmp_path, web_dir=tmp_path / "missing")
    with test_client:
        response = test_client.get("/")
    assert response.status_code == 200
    assert "isn't built yet" in response.text


def test_built_frontend_is_served_with_client_side_routes(tmp_path: Path) -> None:
    web = tmp_path / "web"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text("<html>app</html>", encoding="utf-8")
    (web / "assets" / "main.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("outside the web folder", encoding="utf-8")

    test_client, _ = client(tmp_path / "data", web_dir=web)
    with test_client:
        assert test_client.get("/").text == "<html>app</html>"
        assert test_client.get("/assets/main.js").text == "console.log(1)"
        # A route the SPA handles itself gets the index page.
        assert test_client.get("/sessions/20260918-231502_monza_race").text == "<html>app</html>"
        # Unknown API paths stay 404s instead of turning into the index page.
        assert test_client.get("/api/nope").status_code == 404
        # Paths can't climb out of the web folder.
        assert "outside" not in test_client.get("/..%2Fsecret.txt").text
        assert "outside" not in test_client.get("/assets/..%2F..%2Fsecret.txt").text


def test_cors_allows_the_vite_dev_server_only(tmp_path: Path) -> None:
    test_client, _ = client(tmp_path)
    with test_client:
        allowed = test_client.get("/api/health", headers={"Origin": "http://localhost:5173"})
        other = test_client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-origin" not in other.headers


def test_server_thread_starts_serves_and_stops(tmp_path: Path) -> None:
    telemetry = Telemetry(SETTINGS, tmp_path)
    server = ServerThread(make_server(create_app(telemetry), SETTINGS))
    server.start()
    try:
        with urllib.request.urlopen(server.url + "/api/health", timeout=5) as response:
            assert json.loads(response.read()) == {"status": "ok"}
    finally:
        server.stop()
    with pytest.raises(OSError):
        urllib.request.urlopen(server.url + "/api/health", timeout=1)


def test_server_thread_reports_a_failed_start(tmp_path: Path) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as taken:
        taken.bind(("127.0.0.1", 0))
        settings = Settings(udp_port=taken.getsockname()[1], http_port=0)
        server = ServerThread(make_server(create_app(Telemetry(settings, tmp_path)), settings))
        with pytest.raises(RuntimeError, match="failed to start"):
            server.start()


def save_comparable(
    data_dir: Path,
    session_id: str,
    *,
    number: int = 1,
    speed_ms: float = 50.0,
    start: float = 0.0,
    end: float = 1000.0,
    track: int = 7,
) -> None:
    """A saved session holding one lap driven at a constant speed, so its compared delta is known exactly."""
    folder = SessionStore(data_dir).root / session_id
    distance = [start + (end - start) * i / 100 for i in range(101)]
    write_json_atomic(
        folder / "session.json",
        {
            "id": session_id,
            "started_at": "2026-09-18T23:15:02",
            "ended_at": "2026-09-18T23:30:00",
            "track": {"id": track, "name": "Monza", "length": 5793},
            "session_type": {"id": 10, "name": "Race"},
            "laps": [{"number": number}],
        },
    )
    write_json_atomic(
        folder / "laps" / f"lap_{number:02d}.json",
        {
            "number": number,
            "lap_time_ms": round(end / speed_ms * 1000),
            "invalid": False,
            "partial": False,
            "samples": len(distance),
            "columns": {
                "lap_distance": distance,
                "lap_time_ms": [round(d / speed_ms * 1000) for d in distance],
                "speed": [round(speed_ms * 3.6)] * len(distance),
                "throttle": [1.0] * len(distance),
                "brake": [0.0] * len(distance),
                "steer": [0.0] * len(distance),
            },
        },
    )


COMPARE = "/api/compare?session_a=20260918-231502_monza_race&lap_a=1&session_b=20260919-101500_monza_race&lap_b=2"


def test_two_laps_from_different_sessions_are_compared_on_one_grid(tmp_path: Path) -> None:
    save_comparable(tmp_path, "20260918-231502_monza_race", number=1, speed_ms=50.0)
    save_comparable(tmp_path, "20260919-101500_monza_race", number=2, speed_ms=40.0)
    test_client, _ = client(tmp_path)
    with test_client:
        result = test_client.get(COMPARE).json()

    assert result["track"] == {"id": 7, "name": "Monza", "length": 5793}
    assert (result["step"], result["distance"][0], result["distance"][-1]) == (5.0, 0.0, 1000.0)
    first, second = result["laps"]
    assert (first["session"]["id"], first["number"]) == ("20260918-231502_monza_race", 1)
    assert (second["session"]["id"], second["number"]) == ("20260919-101500_monza_race", 2)
    assert len(first["columns"]["speed"]) == len(result["delta"]) == len(result["distance"])
    # 1000 m at 40 m/s instead of 50 m/s: 5 s lost, spread evenly over 25 minisectors.
    assert result["delta"][-1] == pytest.approx(5.0, abs=0.01)
    assert len(result["minisectors"]) == 25
    assert result["minisectors"][0]["delta"] == pytest.approx(0.2, abs=0.01)


def test_laps_from_two_tracks_are_not_compared(tmp_path: Path) -> None:
    save_comparable(tmp_path, "20260918-231502_monza_race", number=1)
    save_comparable(tmp_path, "20260919-101500_monza_race", number=2, track=3)
    test_client, _ = client(tmp_path)
    with test_client:
        response = test_client.get(COMPARE)

    assert response.status_code == 400
    assert "track" in response.json()["detail"]


def test_laps_that_never_cover_the_same_ground_are_not_compared(tmp_path: Path) -> None:
    save_comparable(tmp_path, "20260918-231502_monza_race", number=1, start=0.0, end=400.0)
    save_comparable(tmp_path, "20260919-101500_monza_race", number=2, start=600.0, end=1000.0)
    test_client, _ = client(tmp_path)
    with test_client:
        response = test_client.get(COMPARE)

    assert response.status_code == 400
    assert "no distance in common" in response.json()["detail"]


@pytest.mark.parametrize(
    "query",
    [
        "session_a=20260101-000000_nowhere_race&lap_a=1&session_b=20260918-231502_monza_race&lap_b=1",
        "session_a=20260918-231502_monza_race&lap_a=9&session_b=20260918-231502_monza_race&lap_b=1",
        "session_a=..%2F..%2Fsecret&lap_a=1&session_b=20260918-231502_monza_race&lap_b=1",
    ],
)
def test_comparing_something_that_is_not_there_is_404(tmp_path: Path, query: str) -> None:
    save_comparable(tmp_path, "20260918-231502_monza_race", number=1)
    test_client, _ = client(tmp_path)
    with test_client:
        assert test_client.get(f"/api/compare?{query}").status_code == 404
