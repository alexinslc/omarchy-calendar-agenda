"""Private, atomic event-cache writes."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable


DEFAULT_CACHE_PATH = (
    Path.home()
    / ".local"
    / "state"
    / "omarchy"
    / "calendar-agenda"
    / "events.json"
)
CACHE_SCHEMA_VERSION = 1


def write_events(
    events: Iterable[dict[str, Any]],
    path: Path = DEFAULT_CACHE_PATH,
    *,
    generated_at: str,
    range_start: str,
    range_end: str,
    accounts: Iterable[dict[str, Any]],
    calendars: Iterable[dict[str, Any]],
) -> None:
    """Replace the versioned cache atomically and keep it user-private."""
    destination = Path(path)
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(destination.parent, 0o700)
    payload = json.dumps(
        {
            "schemaVersion": CACHE_SCHEMA_VERSION,
            "generatedAt": generated_at,
            "rangeStart": range_start,
            "rangeEnd": range_end,
            "accounts": list(accounts),
            "calendars": list(calendars),
            "events": list(events),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            mode="wb",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, destination)
        directory_fd = os.open(destination.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
