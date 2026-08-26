"""Strict configuration loading for the calendar synchronizer."""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = (
    Path.home() / ".config" / "omarchy" / "calendar-agenda" / "config.json"
)
DEFAULT_CACHED_CONFIG_PATH = (
    Path.home() / ".local" / "state" / "omarchy" / "calendar-agenda" / "oauth-client.json"
)
REMOTE_CONFIG_URL = "https://calendar.alexinslc.com/oauth/client-config"
REMOTE_CONFIG_MAX_AGE_SECONDS = 24 * 60 * 60
REMOTE_CONFIG_MAX_BYTES = 4096
CONFIG_SCHEMA_VERSION = 1
ACCOUNT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
GOOGLE_CLIENT_ID_RE = re.compile(r"^[^/\s]+\.apps\.googleusercontent\.com$")


class ConfigError(ValueError):
    """Raised when the synchronizer configuration is missing or invalid."""


@dataclass(frozen=True)
class GoogleConfig:
    client_id: str
    client_secret: str
    accounts: tuple[str, ...]


def _object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{name} must be an object")
    return value


def _parse_config(
    raw: Any, *, require_secret: bool = False, allow_accounts: bool = True
) -> GoogleConfig:
    root = _object(raw, "configuration")
    google = _object(root.get("google"), "google")
    unknown_root = set(root) - {"schemaVersion", "google"}
    unknown_google = set(google) - {"client_id", "client_secret", "accounts"}
    if unknown_root or unknown_google:
        names = sorted(unknown_root | unknown_google)
        raise ConfigError(f"unsupported configuration key(s): {', '.join(names)}")

    schema_version = root.get("schemaVersion")
    if schema_version is not None and schema_version != CONFIG_SCHEMA_VERSION:
        raise ConfigError(f"unsupported configuration schema: {schema_version!r}")
    if not allow_accounts and "accounts" in google:
        raise ConfigError("production OAuth configuration must not contain accounts")

    client_id = google.get("client_id")
    if not isinstance(client_id, str) or not GOOGLE_CLIENT_ID_RE.fullmatch(client_id):
        raise ConfigError(
            "google.client_id must be a Google OAuth client ID ending "
            "in .apps.googleusercontent.com"
        )

    client_secret = google.get("client_secret", "")
    if not isinstance(client_secret, str):
        raise ConfigError("google.client_secret must be a string when provided")
    if require_secret and not client_secret:
        raise ConfigError("production OAuth configuration is missing client_secret")

    accounts_value = google.get("accounts", [])
    if not isinstance(accounts_value, list):
        raise ConfigError("google.accounts must be a list of account IDs")
    accounts: list[str] = []
    for account_id in accounts_value:
        if not isinstance(account_id, str) or not ACCOUNT_ID_RE.fullmatch(account_id):
            raise ConfigError(
                "google.accounts entries must match "
                "[A-Za-z0-9][A-Za-z0-9._-]{0,63}"
            )
        if account_id in accounts:
            raise ConfigError(f"duplicate Google account ID: {account_id}")
        accounts.append(account_id)
    return GoogleConfig(
        client_id=client_id,
        client_secret=client_secret,
        accounts=tuple(accounts),
    )


def _read_config(
    path: Path, *, require_secret: bool = False, allow_accounts: bool = True
) -> GoogleConfig:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ConfigError(f"configuration does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise ConfigError(f"configuration is not valid JSON: {path}") from error
    except OSError as error:
        raise ConfigError(f"cannot read configuration: {path}") from error
    return _parse_config(
        raw, require_secret=require_secret, allow_accounts=allow_accounts
    )


def fetch_remote_config() -> dict[str, Any]:
    """Fetch the fixed production public-client configuration endpoint."""
    request = urllib.request.Request(
        REMOTE_CONFIG_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "Calendar-Agenda-for-Omarchy/0.2",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            final_url = response.geturl()
            content_type = response.headers.get_content_type()
            raw = response.read(REMOTE_CONFIG_MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        raise ConfigError(
            f"production OAuth configuration returned HTTP {error.code}"
        ) from error
    except urllib.error.URLError as error:
        raise ConfigError(
            f"production OAuth configuration request failed: {error.reason}"
        ) from error
    except OSError as error:
        raise ConfigError(
            f"production OAuth configuration request failed: {error}"
        ) from error
    if final_url != REMOTE_CONFIG_URL:
        raise ConfigError("production OAuth configuration redirected unexpectedly")
    if content_type != "application/json":
        raise ConfigError("production OAuth configuration is not JSON")
    if len(raw) > REMOTE_CONFIG_MAX_BYTES:
        raise ConfigError("production OAuth configuration is unexpectedly large")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConfigError("production OAuth configuration returned invalid JSON") from error
    _parse_config(payload, require_secret=True, allow_accounts=False)
    return payload


def _write_cached_config(payload: dict[str, Any], path: Path) -> None:
    temporary_path: Path | None = None
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(path.parent, 0o700)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), 0o600)
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        directory_fd = os.open(
            path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        )
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError as error:
        raise ConfigError(f"cannot cache production OAuth configuration: {error}") from error
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError as error:
                raise ConfigError(
                    f"cannot clean up production OAuth configuration: {error}"
                ) from error


def _cache_is_fresh(path: Path) -> bool:
    try:
        age = time.time() - path.stat().st_mtime
    except OSError:
        return False
    return 0 <= age < REMOTE_CONFIG_MAX_AGE_SECONDS


def load_config(path: Path | None = None) -> GoogleConfig:
    """Load a private override or the validated cached production config."""
    if path is not None:
        return _read_config(Path(path))
    if DEFAULT_CONFIG_PATH.is_file():
        return _read_config(DEFAULT_CONFIG_PATH)
    if _cache_is_fresh(DEFAULT_CACHED_CONFIG_PATH):
        try:
            return _read_config(
                DEFAULT_CACHED_CONFIG_PATH,
                require_secret=True,
                allow_accounts=False,
            )
        except ConfigError:
            pass
    try:
        payload = fetch_remote_config()
        _write_cached_config(payload, DEFAULT_CACHED_CONFIG_PATH)
        return _parse_config(payload, require_secret=True, allow_accounts=False)
    except ConfigError:
        if DEFAULT_CACHED_CONFIG_PATH.is_file():
            return _read_config(
                DEFAULT_CACHED_CONFIG_PATH,
                require_secret=True,
                allow_accounts=False,
            )
        raise
