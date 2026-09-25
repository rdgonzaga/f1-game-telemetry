"""The f1telemetry command: argument parsing, port checks and the record/replay subcommands."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from f1telemetry import cli


def test_serve_options_work_without_the_command_name() -> None:
    args = cli.parse_args(["--network", "--udp-port", "20800", "--no-browser"])
    assert (args.command, args.listen_mode, args.udp_port, args.no_browser) == ("serve", "network", 20800, True)


def test_serve_exits_with_one_line_when_the_udp_port_is_taken(tmp_path: Path) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as taken:
        taken.bind(("127.0.0.1", 0))
        port = str(taken.getsockname()[1])
        with pytest.raises(SystemExit) as exit_info:
            cli.main(["--data-dir", str(tmp_path), "--udp-port", port, "--port", "0", "--no-browser"])
    assert "Is another telemetry app running?" in str(exit_info.value.code)


def test_record_refuses_an_existing_file_before_listening(tmp_path: Path) -> None:
    out = tmp_path / "earlier.f1raw"
    out.write_bytes(b"keep me")
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["record", "--out", str(out)])
    assert "already exists" in str(exit_info.value.code)
    assert out.read_bytes() == b"keep me"
