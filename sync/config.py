"""Strict configuration loading for the calendar synchronizer."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = (
    Path.home() / ".config" / "omarchy" / "calendar-agenda" / "config.json"
)
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


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> GoogleConfig:
    """Load the documented JSON config without accepting unknown shapes."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ConfigError(f"configuration file not found: {path}") from error
    except json.JSONDecodeError as error:
        raise ConfigError(f"configuration is not valid JSON: {path}") from error
    except OSError as error:
        raise ConfigError(f"cannot read configuration: {path}") from error

    root = _object(raw, "configuration")
    google = _object(root.get("google"), "google")
    unknown_root = set(root) - {"google"}
    unknown_google = set(google) - {"client_id", "client_secret", "accounts"}
    if unknown_root or unknown_google:
        names = sorted(unknown_root | unknown_google)
        raise ConfigError(f"unsupported configuration key(s): {', '.join(names)}")

    client_id = google.get("client_id")
    if not isinstance(client_id, str) or not GOOGLE_CLIENT_ID_RE.fullmatch(client_id):
        raise ConfigError(
            "google.client_id must be a Google OAuth client ID ending "
            "in .apps.googleusercontent.com"
        )

    client_secret = google.get("client_secret")
    if not isinstance(client_secret, str) or not client_secret.strip():
        raise ConfigError("google.client_secret must be a non-empty string")

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
