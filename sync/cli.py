"""Command-line entry point for one-shot Google Calendar synchronization."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .cache import write_events
from .config import ConfigError, load_config
from .google import (
    GoogleCalendarClient,
    GoogleError,
    SecretToolStore,
    authorize,
    normalize_event,
    refresh_access_token,
    revoke_token,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync Google Calendar into the agenda cache")
    parser.add_argument("--config", type=Path, help="configuration JSON path")
    parser.add_argument("--account", help="one configured account ID; default is all accounts")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--authorize", action="store_true", help="connect an account in a browser")
    actions.add_argument("--sync", action="store_true", help="fetch all calendars and write the cache")
    actions.add_argument("--disconnect", action="store_true", help="revoke and remove an account token")
    return parser


def _accounts(config_accounts: tuple[str, ...], selected: str | None) -> tuple[str, ...]:
    if selected is None:
        if not config_accounts:
            raise ConfigError("google.accounts is empty; add an account ID to the config")
        return config_accounts
    if selected not in config_accounts:
        raise ConfigError(f"account is not configured: {selected}")
    return (selected,)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.WARNING)
    try:
        config = load_config(args.config) if args.config else load_config()
        accounts = _accounts(config.accounts, args.account)
        store = SecretToolStore()
        if args.authorize:
            for account_id in accounts:
                refresh_token, _ = authorize(config.client_id, config.client_secret)
                store.save(account_id, refresh_token)
            return 0
        if args.disconnect:
            for account_id in accounts:
                token = store.load(account_id)
                revoke_token(token)
                store.delete(account_id)
            return 0

        events: list[dict[str, object]] = []
        for account_id in accounts:
            token = refresh_access_token(
                config.client_id,
                config.client_secret,
                store.load(account_id),
            )
            client = GoogleCalendarClient(token.access_token)
            for calendar in client.list_calendars():
                calendar_id = calendar.get("id")
                if not isinstance(calendar_id, str) or not calendar_id:
                    raise GoogleError("Google calendar list contained an invalid calendar ID")
                for event in client.list_events(calendar_id):
                    normalized = normalize_event(event)
                    if normalized is not None:
                        events.append(normalized)
        write_events(events)
        return 0
    except (ConfigError, GoogleError) as error:
        print(f"calendar sync failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
