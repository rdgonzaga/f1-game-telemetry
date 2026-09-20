"""Response shapes, declared for the OpenAPI document only.

The API hands back the columnar dictionaries the store already built, and a lap file is served as the bytes on
disk. Running those through `response_model` would revalidate and re-encode hundreds of KB on every request, so
the routes keep their `dict[str, Any]` returns and point `responses=` at the models here instead. FastAPI then
documents the shape without touching the payload, and `frontend/src/api/schema.ts` is generated from it.

The live models are built from the packet `NamedTuple`s rather than written out again, because `/ws/live` sends
exactly their fields (see `live_feed.snapshot`). Add a field to `CarTelemetry` and the TypeScript type follows;
there is nothing to keep in sync by hand.

Nothing here runs at request time. It exists so the frontend fails to compile when the backend changes shape.
"""

from __future__ import annotations

from typing import Any, Literal, get_type_hints

from pydantic import BaseModel, Field, create_model

from f1telemetry.car_damage import CarDamage
from f1telemetry.car_status import CarStatus
from f1telemetry.car_telemetry import CarTelemetry
from f1telemetry.car_telemetry2 import CarTelemetry2
from f1telemetry.lap_data import LapData
from f1telemetry.session import Session


class Track(BaseModel):
    id: int
    name: str
    length: int = Field(description="metres")


class SessionType(BaseModel):
    id: int
    name: str


class Formula(BaseModel):
    id: int
    name: str = Field(description="ERS and active aero are gated on the series, not the packet format")


class LapSummary(BaseModel):
    number: int
    lap_time_ms: int
    invalid: bool
    partial: bool = Field(description="the lap was not driven end to end, e.g. an out lap or a flashback")
    samples: int


class SessionDocument(BaseModel):
    """A saved `session.json`, which is also what every `/ws/live` event carries."""

    version: int
    id: str
    uid: str
    started_at: str
    ended_at: str | None
    end_reason: str | None
    packet_format: int
    player_index: int
    track: Track
    session_type: SessionType
    formula: Formula
    total_laps: int
    best_lap: int | None = Field(description="fastest lap that is valid and complete")
    laps: list[LapSummary]


class SessionSummary(SessionDocument):
    """A session over the REST API, which adds how the recording ended."""

    status: Literal["recording", "complete", "interrupted"] = Field(
        description="`interrupted` when the app stopped writing without the session ending"
    )


class LapColumns(BaseModel):
    """One array per channel, all the same length. Column-major so a chart can hand an array straight to uPlot."""

    session_time: list[float] = Field(description="seconds")
    lap_distance: list[float] = Field(description="metres; negative before the start line")
    lap_time_ms: list[int]
    speed: list[int] = Field(description="km/h")
    throttle: list[float] = Field(description="0-1")
    brake: list[float] = Field(description="0-1")
    steer: list[float] = Field(description="-1 full left to 1 full right")
    gear: list[int] = Field(description="-1 reverse, 0 neutral, 1-8")
    engine_rpm: list[int]
    drs: list[int] = Field(description="0 or 1")


class LapDocument(LapSummary):
    version: int
    columns: LapColumns


class CompareColumns(BaseModel):
    """The traces worth overlaying, resampled onto the shared distance grid."""

    speed: list[float]
    throttle: list[float]
    brake: list[float]
    steer: list[float]


class CompareLapSession(BaseModel):
    """Which session a compared lap came from. The track is reported once, on the result, for both."""

    id: str | None
    started_at: str | None
    session_type: SessionType | None


class CompareLap(BaseModel):
    number: int
    lap_time_ms: int
    invalid: bool
    partial: bool
    columns: CompareColumns
    session: CompareLapSession


class Minisector(BaseModel):
    start: float = Field(description="metres")
    end: float
    delta: float = Field(description="seconds gained or lost inside this slice alone, not a running total")


class CompareResult(BaseModel):
    track: Track
    step: float = Field(description="metres between grid points")
    distance: list[float]
    laps: list[CompareLap] = Field(description="exactly two, in the order asked for", min_length=2, max_length=2)
    delta: list[float] = Field(description="seconds lap B has taken more than lap A; positive means B is slower")
    minisectors: list[Minisector]


class ErrorDetail(BaseModel):
    detail: str


def _model_from_namedtuple(payload: type[tuple[Any, ...]], name: str, doc: str) -> type[BaseModel]:
    """A model with the same fields as a packet payload, which is how `live_feed` encodes one."""
    hints = get_type_hints(payload)
    fields: dict[str, Any] = {field: (annotation, ...) for field, annotation in hints.items()}
    model: type[BaseModel] = create_model(name, **fields)
    model.__doc__ = doc
    return model


LiveSession = _model_from_namedtuple(Session, "LiveSession", "The latest Session packet.")
LiveLap = _model_from_namedtuple(LapData, "LiveLap", "The latest LapData packet for the player's car.")
LiveTelemetry = _model_from_namedtuple(CarTelemetry, "LiveTelemetry", "The latest CarTelemetry packet.")
LiveStatus = _model_from_namedtuple(CarStatus, "LiveStatus", "The latest CarStatus packet.")
LiveDamage = _model_from_namedtuple(CarDamage, "LiveDamage", "The latest CarDamage packet.")
LiveTelemetry2 = _model_from_namedtuple(
    CarTelemetry2,
    "LiveTelemetry2",
    "The latest CarTelemetry2 packet; absent in format 2025. `regulations_2026_applicable` is what active aero "
    "gates on, and it is False for F2 even though the Session packet still lists four aero zones.",
)


class LiveDelta(BaseModel):
    best_lap: int
    seconds: float = Field(description="gap to the session's best lap at this distance; positive means slower")


# Built rather than written, because its packet slots are the models above and a model made at runtime cannot be
# used as an annotation. The slot names are `live.PACKET_SLOTS`, in the order `live_feed.snapshot` writes them.
LiveSnapshot: type[BaseModel] = create_model(
    "LiveSnapshot",
    type=(Literal["snapshot"], ...),
    connected=(bool, Field(description="a datagram arrived within the last second")),
    packet_format=(int | None, ...),
    player_index=(int | None, ...),
    packets_per_second=(float, ...),
    session=(LiveSession | None, ...),
    lap=(LiveLap | None, ...),
    telemetry=(LiveTelemetry | None, ...),
    status=(LiveStatus | None, ...),
    damage=(LiveDamage | None, ...),
    telemetry2=(LiveTelemetry2 | None, ...),
    delta=(LiveDelta | None, ...),
)
LiveSnapshot.__doc__ = (
    "Sent at 30 Hz while the picture changes. Every packet slot is null until one of that kind has arrived."
)


class LiveHello(BaseModel):
    """Sent once on connect, with the open session or null."""

    type: Literal["hello"]
    session: SessionDocument | None


class LiveSessionStarted(BaseModel):
    type: Literal["session_started"]
    session: SessionDocument | None


class LiveLapCompleted(BaseModel):
    type: Literal["lap_completed"]
    lap: LapSummary
    session: SessionDocument | None


class LiveLapReopened(BaseModel):
    """A flashback took a finished lap back; the client should drop it and wait for it again."""

    type: Literal["lap_reopened"]
    lap_number: int
    session: SessionDocument | None


class LiveSessionEnded(BaseModel):
    type: Literal["session_ended"]
    reason: str
    session: SessionDocument | None


# `/ws/live` is a WebSocket, so FastAPI cannot document it; `openapi.py` adds these to the schema by hand.
WEBSOCKET_MODELS: tuple[type[BaseModel], ...] = (
    LiveSnapshot,
    LiveHello,
    LiveSessionStarted,
    LiveLapCompleted,
    LiveLapReopened,
    LiveSessionEnded,
)
