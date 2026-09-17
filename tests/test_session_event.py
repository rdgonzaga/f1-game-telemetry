from __future__ import annotations

import struct

import pytest

from f1telemetry import event, session
from f1telemetry.event import FastestLap, Flashback, SessionEnded, SessionStarted
from f1telemetry.names import formula_name, session_type_name, track_name
from f1telemetry.packets import FORMATS, HEADER, PacketDispatcher, PacketHeader, PacketId


def make_header(packet_format: int, packet_id: PacketId) -> bytes:
    return HEADER.pack(*PacketHeader(packet_format, 25, 1, 15, 1, packet_id, 1, 3.0, 10, 10, 0, 255))


def blank_packet(packet_format: int, packet_id: PacketId) -> bytearray:
    head = make_header(packet_format, packet_id)
    return bytearray(head + bytes(FORMATS[packet_format].packet_sizes[packet_id] - len(head)))


def make_dispatcher() -> PacketDispatcher:
    dispatcher = PacketDispatcher()
    session.register(dispatcher)
    event.register(dispatcher)
    return dispatcher


# weather, track temp, air temp, laps, length, type, track, formula, time left, duration, pit limit, paused, spectating
INFO = (3, 31, -2, 5, 5412, 18, 42, 2, 1800, 3600, 80, False, True)


def make_session(packet_format: int) -> bytearray:
    data = blank_packet(packet_format, PacketId.SESSION)
    session.SESSION_INFO.pack_into(data, HEADER.size, *INFO)
    session.SECTOR_STARTS.pack_into(data, session.SECTOR_STARTS_OFFSET, 1800.5, 3600.25)
    return data


def test_session_offsets_match_spec() -> None:
    # 29 header + 716 bytes of fields up to the weekend structure, then two sector floats ends the 2025 packet.
    assert session.SECTOR_STARTS_OFFSET == 745
    # 2026 tail: status, full count + 8 zones, partial count + 8 zones, DRS count + 4 zones, reaction time, 5 assists.
    tail = 2 + 64 + 1 + 64 + 1 + 32 + 4 + 5
    assert FORMATS[2026].packet_sizes[PacketId.SESSION] == session.AERO_STATUS_OFFSET + tail
    assert session.AERO_ZONES_PARTIAL_OFFSET == 820


@pytest.mark.parametrize("packet_format", [2025, 2026])
def test_session_decodes_shared_fields(packet_format: int) -> None:
    packet = make_dispatcher().parse(bytes(make_session(packet_format)))
    assert packet is not None
    data = packet.data
    assert isinstance(data, session.Session)
    assert data[: len(INFO)] == INFO
    assert (data.sector2_lap_distance_start, data.sector3_lap_distance_start) == (1800.5, 3600.25)


def test_session_2025_has_no_active_aero() -> None:
    packet = make_dispatcher().parse(bytes(make_session(2025)))
    assert packet is not None and isinstance(packet.data, session.Session)
    assert packet.data.active_aero_track_status is None
    assert packet.data.active_aero_zones_full == ()
    assert packet.data.active_aero_zones_partial == ()


def test_session_2026_active_aero_zones_respect_counts() -> None:
    data = make_session(2026)
    struct.pack_into("<BB", data, session.AERO_STATUS_OFFSET, 1, 2)
    struct.pack_into("<6f", data, session.AERO_ZONES_FULL_OFFSET, 0.125, 0.25, 0.5, 0.75, 0.875, 0.9375)
    data[session.AERO_ZONES_PARTIAL_COUNT_OFFSET] = 1
    struct.pack_into("<4f", data, session.AERO_ZONES_PARTIAL_OFFSET, 0.25, 0.5, 0.6, 0.7)
    packet = make_dispatcher().parse(bytes(data))
    assert packet is not None and isinstance(packet.data, session.Session)
    assert packet.data.active_aero_track_status == 1
    assert packet.data.active_aero_zones_full == ((0.125, 0.25), (0.5, 0.75))
    assert packet.data.active_aero_zones_partial == ((0.25, 0.5),)


def make_event(packet_format: int, code: bytes, details: bytes = b"") -> bytes:
    data = blank_packet(packet_format, PacketId.EVENT)
    data[event.CODE_OFFSET : event.DETAILS_OFFSET] = code
    data[event.DETAILS_OFFSET : event.DETAILS_OFFSET + len(details)] = details
    return bytes(data)


@pytest.mark.parametrize("packet_format", [2025, 2026])
def test_events_decode_in_both_formats(packet_format: int) -> None:
    dispatcher = make_dispatcher()
    cases = [
        (make_event(packet_format, b"SSTA"), SessionStarted()),
        (make_event(packet_format, b"SEND"), SessionEnded()),
        (make_event(packet_format, b"FTLP", event.FASTEST_LAP.pack(7, 88.5)), FastestLap(7, 88.5)),
        (make_event(packet_format, b"FLBK", event.FLASHBACK.pack(4321, 95.25)), Flashback(4321, 95.25)),
    ]
    for raw, expected in cases:
        packet = dispatcher.parse(raw)
        assert packet is not None
        assert packet.data == expected
        assert packet.data


def test_unhandled_event_code_returns_none() -> None:
    packet = make_dispatcher().parse(make_event(2026, b"BUTN", b"\x01\x00\x00\x00"))
    assert packet is not None
    assert packet.data is None


def test_readable_names() -> None:
    assert track_name(42) == "Madrid"
    assert track_name(-1) == "Unknown track (-1)"
    assert session_type_name(18) == "Time Trial"
    assert session_type_name(99) == "Unknown session (99)"
    assert formula_name(2) == "F2"
    assert formula_name(13) == "F1 26"
    assert formula_name(5) == "Unknown formula (5)"
