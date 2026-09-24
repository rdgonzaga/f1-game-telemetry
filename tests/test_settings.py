"""Settings from settings.json and flags, and LAN address detection."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from f1telemetry.settings import Settings, load_settings, with_overrides


def write(data_dir: Path, content: object) -> None:
    text = content if isinstance(content, str) else json.dumps(content)
    (data_dir / "settings.json").write_text(text, encoding="utf-8")


def test_missing_file_means_defaults(tmp_path: Path) -> None:
    settings = load_settings(tmp_path)
    assert settings == Settings()
    assert (settings.udp_host, settings.udp_port, settings.http_host, settings.http_port) == (
        "127.0.0.1",
        20777,
        "127.0.0.1",
        20778,
    )


def test_file_values_override_defaults(tmp_path: Path) -> None:
    write(tmp_path, {"listen_mode": "network", "udp_port": 20800, "unknown": True})
    settings = load_settings(tmp_path)

    assert (settings.listen_mode, settings.udp_port) == ("network", 20800)
    # Network mode opens UDP to the LAN; the dashboard stays on this PC.
    assert (settings.udp_host, settings.http_host) == ("0.0.0.0", "127.0.0.1")


@pytest.mark.parametrize("content", ["{not json", "[1, 2]"])
def test_broken_file_falls_back_to_defaults(tmp_path: Path, content: str, caplog: pytest.LogCaptureFixture) -> None:
    write(tmp_path, content)
    with caplog.at_level(logging.WARNING):
        assert load_settings(tmp_path) == Settings()
    assert "ignoring" in caplog.text


def test_bad_values_are_replaced_by_defaults(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    write(tmp_path, {"listen_mode": "everywhere", "udp_port": 70000, "http_port": True, "http_host": "0.0.0.0"})
    with caplog.at_level(logging.WARNING):
        settings = load_settings(tmp_path)

    assert settings == Settings(http_host="0.0.0.0")
    assert caplog.text.count("ignoring") == 3


def test_flags_override_the_file_and_are_validated() -> None:
    settings = with_overrides(Settings(listen_mode="network"), listen_mode=None, udp_port=0, http_port=None)
    assert (settings.listen_mode, settings.udp_port) == ("network", 0)

    with pytest.raises(ValueError, match="udp_port"):
        with_overrides(Settings(), udp_port=-1)
