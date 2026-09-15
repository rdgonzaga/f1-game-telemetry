from __future__ import annotations

import socket
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from f1telemetry.rawfile import FILE_HEADER, MAGIC, RawFileError, RawWriter, read_records
from record_raw import record
from replay_raw import replay

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


def test_roundtrip(tmp_path: Path) -> None:
    path = write_file(tmp_path / "a.f1raw")
    assert list(read_records(path)) == PACKETS


def test_truncated_tail_is_ignored(tmp_path: Path) -> None:
    path = write_file(tmp_path / "a.f1raw")
    path.write_bytes(path.read_bytes()[:-10])
    assert list(read_records(path)) == PACKETS[:2]


def test_empty_recording(tmp_path: Path) -> None:
    path = write_file(tmp_path / "a.f1raw", [])
    assert path.stat().st_size == FILE_HEADER.size
    assert list(read_records(path)) == []


@pytest.mark.parametrize(
    "content",
    [b"", b"NOPE\x00\x00\x01\x00", MAGIC + b"\x63\x00"],
    ids=["short", "magic", "version"],
)
def test_invalid_header(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "bad.f1raw"
    path.write_bytes(content)
    with pytest.raises(RawFileError):
        list(read_records(path))


def test_oversized_datagram_rejected(tmp_path: Path) -> None:
    with RawWriter(tmp_path / "a.f1raw") as w, pytest.raises(RawFileError):
        w.write(0, b"\x00" * 0x10000)


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


def test_replay_rejects_non_positive_speed(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        replay(write_file(tmp_path / "a.f1raw"), speed=0)


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
