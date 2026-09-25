from __future__ import annotations

import socket
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from f1telemetry.packets import HEADER, PACKET_ID_OFFSET, PacketId
from f1telemetry.rawfile import RawWriter, read_records
from f1telemetry.recorder import record
from f1telemetry.replayer import replay
from trim_raw import trim

PACKETS = [(0, b"\x01" * 29), (5_000_000, b"\x02" * 1448), (40_000_000, b"\x03" * 269)]


def free_udp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def write_file(path: Path, packets: list[tuple[int, bytes]] = PACKETS) -> Path:
    with RawWriter(path) as w:
        for t, data in packets:
            w.write(t, data)
    return path


def test_truncated_tail_is_ignored(tmp_path: Path) -> None:
    path = write_file(tmp_path / "a.f1raw")
    path.write_bytes(path.read_bytes()[:-10])
    assert list(read_records(path)) == PACKETS[:2]


def test_replay_preserves_order_and_scaled_timing(tmp_path: Path) -> None:
    path = write_file(tmp_path / "a.f1raw", [(0, b"a"), (100_000_000, b"b"), (200_000_000, b"c")])
    port = free_udp_port()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as rx:
        rx.bind(("127.0.0.1", port))
        rx.settimeout(2)
        start = time.perf_counter()
        assert replay(path, port=port, speed=2.0) == 3
        elapsed = time.perf_counter() - start
        assert [rx.recv(64) for _ in range(3)] == [b"a", b"b", b"c"]
    assert 0.08 <= elapsed < 0.5


def test_record_then_replay_roundtrip(tmp_path: Path) -> None:
    source = write_file(tmp_path / "source.f1raw")
    out = tmp_path / "nested" / "out.f1raw"
    port = free_udp_port()
    stop, ready = threading.Event(), threading.Event()
    result: list[int] = []
    thread = threading.Thread(target=lambda: result.append(record(out, port=port, stop=stop, ready=ready)))
    thread.start()
    assert ready.wait(2)

    replay(source, port=port, speed=4.0)
    time.sleep(0.1)
    stop.set()
    thread.join(2)

    recorded = list(read_records(out))
    assert result == [3]
    assert [data for _, data in recorded] == [data for _, data in PACKETS]
    assert recorded[0][0] == 0
    assert [t for t, _ in recorded] == sorted(t for t, _ in recorded)


def fake_packet(packet_id: int, tag: int) -> bytes:
    data = bytearray([tag]) * HEADER.size
    data[PACKET_ID_OFFSET] = packet_id
    return bytes(data)


def test_trim_keeps_parsed_packets_in_window_and_rebases_time(tmp_path: Path) -> None:
    s = 1_000_000_000
    source = write_file(
        tmp_path / "source.f1raw",
        [
            (0, fake_packet(PacketId.LAP_DATA, 1)),
            (2 * s, fake_packet(PacketId.MOTION, 2)),
            (2 * s + 5, fake_packet(PacketId.CAR_TELEMETRY, 3)),
            (3 * s, b"short"),
            (3 * s, fake_packet(PacketId.EVENT, 4)),
            (4 * s, fake_packet(PacketId.SESSION, 5)),
        ],
    )
    out = tmp_path / "nested" / "out.f1raw"
    assert trim(source, out, 1.5, 3.0) == 2
    assert list(read_records(out)) == [
        (0, fake_packet(PacketId.CAR_TELEMETRY, 3)),
        (s - 5, fake_packet(PacketId.EVENT, 4)),
    ]
