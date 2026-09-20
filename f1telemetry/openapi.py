"""Dump the OpenAPI document, for generating `frontend/src/api/schema.ts`.

    uv run python -m f1telemetry.openapi [path]

Writes to stdout when no path is given. FastAPI builds the REST half; the `/ws/live` message models are added
here, because a WebSocket route has no place in an OpenAPI document and the frontend still needs those types.

Nothing is started: this only walks the routes, so it needs no UDP port, no data directory and no game.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from pydantic.json_schema import models_json_schema

from f1telemetry.app import Telemetry, create_app
from f1telemetry.schemas import WEBSOCKET_MODELS
from f1telemetry.settings import Settings

REF_TEMPLATE = "#/components/schemas/{model}"


def _websocket_schemas() -> dict[str, Any]:
    """The `/ws/live` message models, keyed the same way FastAPI keys its own components."""
    _, schemas = models_json_schema([(model, "validation") for model in WEBSOCKET_MODELS], ref_template=REF_TEMPLATE)
    definitions: dict[str, Any] = schemas.get("$defs", {})
    return definitions


def document() -> dict[str, Any]:
    telemetry = Telemetry(Settings(), Path("."))
    try:
        schema: dict[str, Any] = create_app(telemetry).openapi()
    finally:
        telemetry.recorder.close()
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    for name, definition in _websocket_schemas().items():
        # A live model that reuses a REST one (SessionDocument, LapSummary) must not be written twice.
        components.setdefault(name, definition)
    return schema


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    text = json.dumps(document(), indent=2) + "\n"
    if args:
        Path(args[0]).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
