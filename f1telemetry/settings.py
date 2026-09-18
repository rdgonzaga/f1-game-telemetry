"""App settings from `settings.json` in the data directory, plus LAN address detection for console players.

Precedence: defaults, then `settings.json`, then command-line flags. A missing file means defaults; a broken file
or value is logged and replaced by its default, so a bad edit never stops the app from starting.
"""

from __future__ import annotations

import json
import logging
import socket
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any, Literal

log = logging.getLogger(__name__)

SETTINGS_FILE = "settings.json"
LOCAL_HOST = "127.0.0.1"
# Network mode binds every interface so a console on the LAN can reach the listener.
ANY_HOST = "0.0.0.0"
# A TEST-NET-1 address: connecting a UDP socket to it picks the outgoing interface without sending anything.
ROUTE_PROBE = ("192.0.2.1", 9)

type ListenMode = Literal["local", "network"]
LISTEN_MODES: tuple[ListenMode, ...] = ("local", "network")


@dataclass(frozen=True, slots=True)
class Settings:
    # "local" takes UDP from this PC only; "network" also from a PS5 or Xbox on the same network.
    listen_mode: ListenMode = "local"
    udp_port: int = 20777
    # The dashboard stays on this PC unless `http_host` is changed on purpose: it can delete sessions.
    http_host: str = LOCAL_HOST
    http_port: int = 20778

    @property
    def udp_host(self) -> str:
        return ANY_HOST if self.listen_mode == "network" else LOCAL_HOST


def _valid(name: str, value: Any) -> bool:
    if name == "listen_mode":
        return value in LISTEN_MODES
    if name in ("udp_port", "http_port"):
        # Port 0 asks the OS for a free port, which tests and the desktop app use.
        return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 65535
    return isinstance(value, str) and bool(value)


def load_settings(data_dir: Path) -> Settings:
    path = data_dir / SETTINGS_FILE
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Settings()
    except (OSError, ValueError) as error:
        log.warning("ignoring unreadable %s: %s", path, error)
        return Settings()
    if not isinstance(raw, dict):
        log.warning("ignoring %s: expected a JSON object", path)
        return Settings()
    values = {}
    for item in fields(Settings):
        if item.name not in raw:
            continue
        value = raw[item.name]
        if _valid(item.name, value):
            values[item.name] = value
        else:
            log.warning("ignoring %s = %r in %s", item.name, value, path)
    return Settings(**values)


def with_overrides(settings: Settings, **overrides: Any) -> Settings:
    """Apply command-line values; None means the flag wasn't given."""
    given = {name: value for name, value in overrides.items() if value is not None}
    for name, value in given.items():
        if not _valid(name, value):
            raise ValueError(f"invalid {name}: {value!r}")
    return replace(settings, **given)


def lan_ipv4_addresses() -> list[str]:
    """This PC's IPv4 addresses a console on the same network could send to; the default route's first."""
    found: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(ROUTE_PROBE)
            found.append(probe.getsockname()[0])
    except OSError:
        pass  # no network route at all
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        infos = []
    found.extend(str(info[4][0]) for info in infos)
    usable = [ip for ip in found if not ip.startswith(("127.", "169.254.", "0."))]
    return list(dict.fromkeys(usable))
