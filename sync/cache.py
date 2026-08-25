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


def _write_payload(payload: dict[str, Any], path: Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(destination.parent, 0o700)
    encoded = json.dumps(
        payload,
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
            temporary.write(encoded)
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
    _write_payload(
        {
            "schemaVersion": CACHE_SCHEMA_VERSION,
            "generatedAt": generated_at,
            "rangeStart": range_start,
            "rangeEnd": range_end,
            "accounts": list(accounts),
            "calendars": list(calendars),
            "events": list(events),
        },
        Path(path),
    )


def purge_account(account_id: str, path: Path = DEFAULT_CACHE_PATH) -> None:
    """Immediately remove one account's private data from an existing cache."""
    cache_path = Path(path)

    def discard_unusable_cache() -> None:
        try:
            cache_path.unlink()
        except FileNotFoundError:
            pass

    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return
    except json.JSONDecodeError:
        discard_unusable_cache()
        return
    except OSError:
        return
    if not isinstance(payload, dict) or payload.get("schemaVersion") != CACHE_SCHEMA_VERSION:
        discard_unusable_cache()
        return
    for key in ("accounts", "calendars", "events"):
        if not isinstance(payload.get(key), list):
            discard_unusable_cache()
            return
    payload["accounts"] = [
        value
        for value in payload["accounts"]
        if isinstance(value, dict) and value.get("id") != account_id
    ]
    payload["calendars"] = [
        value
        for value in payload["calendars"]
        if isinstance(value, dict) and value.get("accountId") != account_id
    ]
    payload["events"] = [
        value
        for value in payload["events"]
        if isinstance(value, dict) and value.get("accountId") != account_id
    ]
    _write_payload(payload, cache_path)
