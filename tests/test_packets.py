from __future__ import annotations

import logging

import pytest

from f1telemetry.packets import FORMATS, HEADER, PacketDispatcher, PacketHeader, PacketId

WARNING_LOGGER = "f1telemetry.packets"


def make_header(packet_format: int = 2026, packet_id: int = PacketId.CAR_TELEMETRY, player: int = 3) -> PacketHeader:
    return PacketHeader(
        packet_format=packet_format,
        game_year=25,
        game_major_version=1,
        game_minor_version=15,
        packet_version=1,
        packet_id=packet_id,
        session_uid=0xDEADBEEFCAFEF00D,
        session_time=12.5,
        frame_identifier=100,
        overall_frame_identifier=120,
        player_car_index=player,
        secondary_player_car_index=255,
    )


def make_packet(packet_format: int = 2026, packet_id: int = PacketId.CAR_TELEMETRY, size: int | None = None) -> bytes:
    if size is None:
        size = FORMATS[packet_format].packet_sizes[packet_id]
    head = HEADER.pack(*make_header(packet_format, packet_id))
    return head + bytes(size - len(head))


def echo(header: PacketHeader, data: bytes) -> tuple[int, int]:
    return header.packet_format, len(data)


def test_header_decodes_every_field() -> None:
    expected = make_header(2025, PacketId.LAP_DATA)
    dispatcher = PacketDispatcher()
    dispatcher.register(PacketId.LAP_DATA, echo)
    packet = dispatcher.parse(make_packet(2025, PacketId.LAP_DATA))
    assert packet is not None
    assert packet.header == expected
    assert packet.data == (2025, 1285)


def test_routes_by_format() -> None:
    dispatcher = PacketDispatcher()
    dispatcher.register(PacketId.CAR_TELEMETRY, lambda h, d: "2025", formats=[2025])
    dispatcher.register(PacketId.CAR_TELEMETRY, lambda h, d: "2026", formats=[2026])
    p25 = dispatcher.parse(make_packet(2025))
    p26 = dispatcher.parse(make_packet(2026))
    assert p25 is not None and p25.data == "2025"
    assert p26 is not None and p26.data == "2026"


def test_unused_packet_dropped_before_size_check(caplog: pytest.LogCaptureFixture) -> None:
    dispatcher = PacketDispatcher()
    dispatcher.register(PacketId.CAR_TELEMETRY, echo)
    with caplog.at_level(logging.WARNING, logger=WARNING_LOGGER):
        assert dispatcher.parse(make_packet(2026, PacketId.MOTION, size=40)) is None
    assert caplog.records == []


def test_car_telemetry2_is_2026_only(caplog: pytest.LogCaptureFixture) -> None:
    dispatcher = PacketDispatcher()
    dispatcher.register(PacketId.CAR_TELEMETRY_2, echo)
    with caplog.at_level(logging.WARNING, logger=WARNING_LOGGER):
        assert dispatcher.parse(make_packet(2025, PacketId.CAR_TELEMETRY_2, size=269)) is None
        assert dispatcher.parse(make_packet(2026, PacketId.CAR_TELEMETRY_2)) is not None
    assert caplog.records == []
    with pytest.raises(ValueError):
        dispatcher.register(PacketId.CAR_TELEMETRY_2, echo, formats=[2025])


def test_unknown_format_warns_once(caplog: pytest.LogCaptureFixture) -> None:
    dispatcher = PacketDispatcher()
    dispatcher.register(PacketId.CAR_TELEMETRY, echo)
    packet = HEADER.pack(*make_header(2024)) + bytes(1323)
    with caplog.at_level(logging.WARNING, logger=WARNING_LOGGER):
        assert dispatcher.parse(packet) is None
        assert dispatcher.parse(packet) is None
    assert len(caplog.records) == 1
    assert "2024" in caplog.records[0].getMessage()
    # Kept for the setup screen, which tells the player to change the game's UDP Format.
    assert dispatcher.last_warning == caplog.records[0].getMessage()


def test_wrong_size_warns_once_then_valid_packets_still_parse(caplog: pytest.LogCaptureFixture) -> None:
    dispatcher = PacketDispatcher()
    dispatcher.register(PacketId.CAR_TELEMETRY, echo)
    with caplog.at_level(logging.WARNING, logger=WARNING_LOGGER):
        assert dispatcher.parse(make_packet(2026, size=1352)) is None
        assert dispatcher.parse(make_packet(2026, size=1400)) is None
        assert dispatcher.parse(make_packet(2026)) is not None
    assert len(caplog.records) == 1
    assert "expected 1448 bytes, got 1352" in caplog.records[0].getMessage()


def test_short_datagram_warns_once(caplog: pytest.LogCaptureFixture) -> None:
    dispatcher = PacketDispatcher()
    with caplog.at_level(logging.WARNING, logger=WARNING_LOGGER):
        assert dispatcher.parse(b"\x00" * 5) is None
        assert dispatcher.parse(b"") is None
    assert len(caplog.records) == 1
