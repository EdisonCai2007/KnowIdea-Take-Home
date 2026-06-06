from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .settings import OpenRouterSettings


def log_event(
    *,
    settings: OpenRouterSettings | None,
    event: str,
    payload: dict[str, Any] | None = None,
    console_message: str | None = None,
) -> None:
    if settings is None or not settings.log_enabled:
        return

    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "payload": payload or {},
    }
    _append_jsonl(settings.log_file, record)

    if settings.log_console:
        message = console_message or event
        print(f"[decision-prover] {message}", file=sys.stderr)


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str, sort_keys=True))
            handle.write("\n")
    except OSError:
        # Logging must not break product behavior.
        return
