"""Reader and writer for `.f1raw` raw UDP recordings.

Layout: 8-byte header (`F1RAW\\0` magic + u16 version), then records of
`<u64 nanoseconds since recording start><u16 length><datagram bytes>`.
All integers are little-endian.
"""

from __future__ import annotations

import struct
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO, Self

MAGIC = b"F1RAW\x00"
VERSION = 1
FILE_HEADER = struct.Struct("<6sH")
RECORD_HEADER = struct.Struct("<QH")
MAX_DATAGRAM = 0xFFFF


class RawFileError(ValueError):
    pass


class RawWriter:
    def __init__(self, path: str | Path) -> None:
        self._file: BinaryIO = open(path, "wb")  # noqa: SIM115
        self._file.write(FILE_HEADER.pack(MAGIC, VERSION))
        self.count = 0

    def write(self, t_ns: int, data: bytes) -> None:
        if len(data) > MAX_DATAGRAM:
            raise RawFileError(f"datagram too large: {len(data)} bytes")
        # One write per record so an interrupt never leaves a split header/body in the buffer.
        self._file.write(RECORD_HEADER.pack(t_ns, len(data)) + data)
        self.count += 1

    def close(self) -> None:
        self._file.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def read_records(path: str | Path) -> Iterator[tuple[int, bytes]]:
    """Yield `(t_ns, datagram)` pairs; a truncated trailing record is ignored."""
    with open(path, "rb") as f:
        header = f.read(FILE_HEADER.size)
        if len(header) < FILE_HEADER.size:
            raise RawFileError("not an .f1raw file: header too short")
        magic, version = FILE_HEADER.unpack(header)
        if magic != MAGIC:
            raise RawFileError("not an .f1raw file: bad magic")
        if version != VERSION:
            raise RawFileError(f"unsupported .f1raw version {version}")

        size = RECORD_HEADER.size
        unpack = RECORD_HEADER.unpack
        while True:
            head = f.read(size)
            if len(head) < size:
                return
            t_ns, length = unpack(head)
            data = f.read(length)
            if len(data) < length:
                return
            yield t_ns, data
