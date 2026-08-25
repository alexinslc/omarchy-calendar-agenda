"""Private status record for per-account synchronization health."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


STATUS_SCHEMA_VERSION = 1
DEFAULT_STATUS_PATH = (
    Path.home()
    / ".local"
    / "state"
    / "omarchy"
    / "calendar-agenda"
    / "sync-status.json"
)


def load_sync_status(path: Path = DEFAULT_STATUS_PATH) -> dict[str, dict[str, object]]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    if (
        not isinstance(payload, dict)
        or payload.get("schemaVersion") != STATUS_SCHEMA_VERSION
        or not isinstance(payload.get("accounts"), dict)
    ):
        return {}
    result: dict[str, dict[str, object]] = {}
    for account_id, value in payload["accounts"].items():
        if not isinstance(account_id, str) or not isinstance(value, dict):
            continue
        ok = value.get("ok")
        error = value.get("error", "")
        if isinstance(ok, bool) and isinstance(error, str):
            result[account_id] = {"ok": ok, "error": error}
    return result


def write_sync_status(
    values: dict[str, dict[str, Any]], path: Path = DEFAULT_STATUS_PATH
) -> None:
    destination = Path(path)
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(destination.parent, 0o700)
    payload = (
        json.dumps(
            {"schemaVersion": STATUS_SCHEMA_VERSION, "accounts": values},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
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
        directory_fd = os.open(
            destination.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        )
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
