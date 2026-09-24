"""The OpenAPI document the frontend's types are generated from.

These are drift guards, not schema tests. `frontend/src/api/schema.ts` is generated from this document, and the
routes declare their models without validating against them, so a payload that stops matching its declared shape
would otherwise surface as a silently wrong TypeScript type rather than a failure here.

The payloads come from a real recording driven through the app, so the models are checked against what the game
actually produces rather than against a hand-written sample that could be wrong in the same way.
"""

from __future__ import annotations

import json
import re
import socket
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple, get_type_hints

import pytest
from fastapi.testclient import TestClient

from f1telemetry.app import Telemetry, create_app
from f1telemetry.car_damage import CarDamage
from f1telemetry.car_status import CarStatus
from f1telemetry.car_telemetry import CarTelemetry
from f1telemetry.car_telemetry2 import CarTelemetry2
from f1telemetry.lap_data import LapData
from f1telemetry.live import LiveState
from f1telemetry.live_feed import snapshot
from f1telemetry.openapi import document
from f1telemetry.rawfile import read_records
from f1telemetry.schemas import (
    CompareResult,
    LapColumns,
    LapDocument,
    LiveSnapshot,
    SessionSummary,
)
from f1telemetry.session import Session
from f1telemetry.settings import Settings

FIXTURES = Path(__file__).parent / "fixtures"
RECORDING = FIXTURES / "race-2026-monza-finish.f1raw"
SETTINGS = Settings(udp_port=0, http_port=0)

# Every live model and the packet payload whose fields `live_feed` sends verbatim.
LIVE_PAYLOADS: list[tuple[str, type[NamedTuple]]] = [
    ("LiveSession", Session),
    ("LiveLap", LapData),
    ("LiveTelemetry", CarTelemetry),
    ("LiveStatus", CarStatus),
    ("LiveDamage", CarDamage),
    ("LiveTelemetry2", CarTelemetry2),
]


def _wait_for(condition: Callable[[], bool], timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.01)


class Recorded(NamedTuple):
    """What one recording, played into the app and saved, looks like over the API."""

    session: dict[str, Any]
    lap: dict[str, Any]
    compare: dict[str, Any]


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    return document()


@pytest.fixture(scope="module")
def recorded(tmp_path_factory: pytest.TempPathFactory) -> Recorded:
    data_dir = tmp_path_factory.mktemp("openapi")
    packets = [data for _, data in read_records(RECORDING)]
    telemetry = Telemetry(SETTINGS, data_dir)
    test_client = TestClient(create_app(telemetry))
    with test_client:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as tx:
            for data in packets:
                tx.sendto(data, ("127.0.0.1", telemetry.udp_port))
        # Nothing reaches disk until a lap completes, so wait for every packet: a dropped datagram under
        # load would otherwise leave an open session that saves nothing, and the reads below find no session.
        _wait_for(lambda: telemetry.state.packets_seen == len(packets))
    with TestClient(create_app(Telemetry(SETTINGS, data_dir))) as reader:
        sessions = reader.get("/api/sessions").json()
        assert sessions, "the recording saved no session"
        session = sessions[0]
        number = session["laps"][0]["number"]
        lap = reader.get(f"/api/sessions/{session['id']}/laps/{number}").json()
        query = f"session_a={session['id']}&lap_a={number}&session_b={session['id']}&lap_b={number}"
        compare = reader.get(f"/api/compare?{query}").json()
    return Recorded(session=session, lap=lap, compare=compare)


def test_every_reference_resolves(schema: dict[str, Any]) -> None:
    """A live model merged in by hand could point at a component FastAPI never emitted."""
    names = set(schema["components"]["schemas"])
    referenced = set(re.findall(r'"#/components/schemas/([A-Za-z0-9_]+)"', json.dumps(schema)))
    assert referenced - names == set()


def test_no_leftover_pydantic_refs(schema: dict[str, Any]) -> None:
    """Pydantic writes `#/$defs/...` unless the ref template is applied, and OpenAPI cannot resolve those."""
    assert "#/$defs/" not in json.dumps(schema)


def test_the_live_messages_are_documented(schema: dict[str, Any]) -> None:
    """A WebSocket has no place in an OpenAPI document, so these are merged in and could be dropped unnoticed."""
    names = set(schema["components"]["schemas"])
    expected = {
        "LiveSnapshot",
        "LiveHello",
        "LiveSessionStarted",
        "LiveLapCompleted",
        "LiveLapReopened",
        "LiveSessionEnded",
    }
    assert expected <= names


@pytest.mark.parametrize(("model", "payload"), LIVE_PAYLOADS)
def test_live_model_matches_its_packet(schema: dict[str, Any], model: str, payload: type[NamedTuple]) -> None:
    properties = schema["components"]["schemas"][model]["properties"]
    assert list(properties) == list(get_type_hints(payload))


def test_snapshot_matches_what_the_feed_sends() -> None:
    """Checked against a real encoded snapshot, not against the model the snapshot was declared from."""
    assert set(snapshot(LiveState(), connected=False)) == set(LiveSnapshot.model_fields)


def test_session_matches_the_declared_summary(recorded: Recorded) -> None:
    assert set(recorded.session) == set(SessionSummary.model_fields)


def test_lap_matches_the_declared_document(recorded: Recorded) -> None:
    assert set(recorded.lap) == set(LapDocument.model_fields)
    assert set(recorded.lap["columns"]) == set(LapColumns.model_fields)


def test_compare_matches_the_declared_result(recorded: Recorded) -> None:
    assert set(recorded.compare) == set(CompareResult.model_fields)
