"""Register every packet parser on one dispatcher, so tools and tests decode the same packets as the app."""

from __future__ import annotations

from f1telemetry import (
    car_damage,
    car_status,
    car_telemetry,
    car_telemetry2,
    event,
    lap_data,
    session,
    session_history,
)
from f1telemetry.packets import PacketDispatcher

PARSER_MODULES = (session, event, lap_data, car_telemetry, car_status, car_damage, car_telemetry2, session_history)


def make_dispatcher() -> PacketDispatcher:
    dispatcher = PacketDispatcher()
    for module in PARSER_MODULES:
        module.register(dispatcher)
    return dispatcher
