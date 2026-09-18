"""The f1telemetry command: argument parsing, port checks and the record/replay subcommands."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from f1telemetry import cli


def test_no_command_means_serve() -> None:
    args = cli.parse_args([])
    assert args.command == "serve"
    assert (args.listen_mode, args.no_browser, args.data_dir) == (None, False, None)


def test_serve_options_work_without_the_command_name() -> None:
    args = cli.parse_args(["--network", "--udp-port", "20800", "--no-browser"])
    assert (args.command, args.listen_mode, args.udp_port, args.no_browser) == ("serve", "network", 20800, True)


def test_network_and_local_are_exclusive() -> None:
    with pytest.raises(SystemExit):
        cli.parse_args(["--network", "--local"])


def test_record_and_replay_commands() -> None:
    record = cli.parse_args(["record", "--out", "lap.f1raw", "--force"])
    assert (record.command, record.out, record.force) == ("record", Path("lap.f1raw"), True)

    replay = cli.parse_args(["replay", "lap.f1raw", "--speed", "2"])
    assert (replay.command, replay.path, replay.speed) == ("replay", Path("lap.f1raw"), 2.0)


def test_port_problem_reports_a_taken_port() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as taken:
        taken.bind(("127.0.0.1", 0))
        port = taken.getsockname()[1]
        assert cli.port_problem(socket.SOCK_DGRAM, "127.0.0.1", port)
    assert cli.port_problem(socket.SOCK_DGRAM, "127.0.0.1", 0) is None


def test_serve_exits_with_one_line_when_the_udp_port_is_taken(tmp_path: Path) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as taken:
        taken.bind(("127.0.0.1", 0))
        port = str(taken.getsockname()[1])
        with pytest.raises(SystemExit) as exit_info:
            cli.main(["--data-dir", str(tmp_path), "--udp-port", port, "--port", "0", "--no-browser"])
    assert "Is another telemetry app running?" in str(exit_info.value.code)


def test_invalid_flag_value_exits_cleanly(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--data-dir", str(tmp_path), "--udp-port", "70000"])
    assert str(exit_info.value.code) == "f1telemetry: invalid udp_port: 70000"


def test_record_refuses_an_existing_file_before_listening(tmp_path: Path) -> None:
    out = tmp_path / "earlier.f1raw"
    out.write_bytes(b"keep me")
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["record", "--out", str(out)])
    assert "already exists" in str(exit_info.value.code)
    assert out.read_bytes() == b"keep me"


def test_replay_rejects_a_non_positive_speed(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        cli.main(["replay", str(tmp_path / "x.f1raw"), "--speed", "0"])
