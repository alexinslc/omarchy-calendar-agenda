"""Command-line entry point for onboarding and Google Calendar sync."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
import shutil
import sys

from .cache import CacheError, DEFAULT_CACHE_PATH, purge_account, write_events
from .config import ConfigError, GoogleConfig, load_config
from .google import (
    GoogleCalendarClient,
    GoogleError,
    SecretToolStore,
    authorize,
    normalize_event,
    refresh_access_token,
    revoke_token,
    user_info,
)
from .locking import OperationLockError, operation_lock
from .registry import (
    DEFAULT_REGISTRY_PATH,
    Account,
    RegistryError,
    add_account,
    load_accounts,
    migrate_legacy_accounts,
    new_account,
    remove_account,
    replace_account,
)
from .scheduler import SchedulerError, install_timer, remove_timer
from .status import DEFAULT_STATUS_PATH, load_sync_status, write_sync_status


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Connect and synchronize Google Calendar accounts"
    )
    parser.add_argument("--config", type=Path, help="private OAuth configuration JSON")
    parser.add_argument("--account", help="one connected account ID")
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="remove local access even when Google revocation is unavailable",
    )
    parser.add_argument("--json", action="store_true", help="emit structured output")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--status", action="store_true", help="show onboarding status")
    actions.add_argument("--doctor", action="store_true", help="check local prerequisites")
    actions.add_argument("--add-account", action="store_true", help="connect a Google account")
    actions.add_argument(
        "--remove-account", metavar="ID", help="revoke and remove a connected account"
    )
    actions.add_argument(
        "--reconnect-account", metavar="ID", help="replace access for a connected account"
    )
    actions.add_argument(
        "--authorize",
        action="store_true",
        help="legacy authorization for one configured account ID",
    )
    actions.add_argument("--sync", action="store_true", help="refresh the local event cache")
    actions.add_argument(
        "--disconnect",
        action="store_true",
        help="legacy alias for removing --account",
    )
    return parser


def _registry_accounts(config: GoogleConfig) -> tuple[Account, ...]:
    return migrate_legacy_accounts(config.accounts, DEFAULT_REGISTRY_PATH)


def _selected_accounts(
    accounts: tuple[Account, ...], selected: str | None
) -> tuple[Account, ...]:
    if selected is None:
        return accounts
    matches = tuple(account for account in accounts if account.id == selected)
    if not matches:
        raise RegistryError(f"account is not connected: {selected}")
    return matches


def _revoke_best_effort(refresh_token: str) -> None:
    try:
        revoke_token(refresh_token)
    except GoogleError:
        pass


def _authorized_identity(config: GoogleConfig) -> tuple[str, dict[str, str]]:
    refresh_token, access_token = authorize(config.client_id, config.client_secret)
    try:
        return refresh_token, user_info(access_token.access_token)
    except GoogleError:
        _revoke_best_effort(refresh_token)
        raise


def _sync_accounts(
    config: GoogleConfig | None,
    accounts: tuple[Account, ...],
    store: SecretToolStore,
    *,
    known_accounts: tuple[Account, ...] | None = None,
) -> dict[str, object]:
    if accounts and config is None:
        raise ConfigError("Google OAuth configuration is required to synchronize accounts")
    events: list[dict[str, object]] = []
    cache_accounts: list[dict[str, object]] = []
    cache_calendars: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    known = known_accounts if known_accounts is not None else accounts
    known_ids = {account.id for account in known}
    health = {
        account_id: value
        for account_id, value in load_sync_status(DEFAULT_STATUS_PATH).items()
        if account_id in known_ids
    }
    now = datetime.now(timezone.utc)
    time_min = now.isoformat().replace("+00:00", "Z")
    time_max = (now + timedelta(days=28)).isoformat().replace("+00:00", "Z")

    for account in accounts:
        account_events: list[dict[str, object]] = []
        account_calendars: list[dict[str, str]] = []
        try:
            assert config is not None
            token = refresh_access_token(
                config.client_id,
                config.client_secret,
                store.load(account.id),
            )
            client = GoogleCalendarClient(token.access_token)
            calendars = client.list_calendars()
            for calendar in calendars:
                calendar_id = calendar.get("id")
                if not isinstance(calendar_id, str) or not calendar_id:
                    raise GoogleError("Google calendar list contained an invalid calendar ID")
                calendar_name = calendar.get("summary", calendar_id)
                if not isinstance(calendar_name, str) or not calendar_name:
                    calendar_name = calendar_id
                calendar_color = calendar.get("backgroundColor", "")
                if not isinstance(calendar_color, str):
                    calendar_color = ""
                account_calendars.append(
                    {
                        "accountId": account.id,
                        "id": calendar_id,
                        "name": calendar_name,
                        "color": calendar_color,
                    }
                )
                for event in client.list_events(
                    calendar_id,
                    time_min=time_min,
                    time_max=time_max,
                ):
                    normalized = normalize_event(
                        event,
                        account_id=account.id,
                        calendar_id=calendar_id,
                        calendar_name=calendar_name,
                        calendar_color=calendar_color,
                    )
                    if normalized is not None:
                        account_events.append(normalized)
            cache_accounts.append(
                {
                    "id": account.id,
                    "email": account.email,
                    "displayName": account.display_name,
                }
            )
            cache_calendars.extend(account_calendars)
            events.extend(account_events)
            health[account.id] = {"ok": True, "error": ""}
        except GoogleError as error:
            errors.append({"accountId": account.id, "message": str(error)})
            health[account.id] = {"ok": False, "error": str(error)}

    if not accounts or cache_accounts:
        write_events(
            events,
            generated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            range_start=time_min,
            range_end=time_max,
            accounts=cache_accounts,
            calendars=cache_calendars,
        )
    write_sync_status(health, DEFAULT_STATUS_PATH)
    return {
        "ok": not errors,
        "eventCount": len(events),
        "accountCount": len(cache_accounts),
        "calendarCount": len(cache_calendars),
        "errors": errors,
    }


def _status(config_error: str = "") -> dict[str, object]:
    accounts = load_accounts(DEFAULT_REGISTRY_PATH)
    health = load_sync_status(DEFAULT_STATUS_PATH)
    public_accounts = []
    for account in accounts:
        value = account.public_dict()
        account_health = health.get(account.id, {})
        value["state"] = (
            "needs-attention" if account_health.get("ok") is False else "connected"
        )
        value["lastError"] = str(account_health.get("error", ""))
        public_accounts.append(value)
    return {
        "ok": not config_error,
        "configured": not config_error,
        "configurationError": config_error,
        "secretServiceAvailable": shutil.which("secret-tool") is not None,
        "accounts": public_accounts,
        "cacheAvailable": DEFAULT_CACHE_PATH.is_file(),
    }


def _connect_account(config: GoogleConfig, store: SecretToolStore) -> dict[str, object]:
    refresh_token, identity = _authorized_identity(config)
    account = new_account(identity["sub"], identity["email"], identity["name"])
    existing_accounts = load_accounts(DEFAULT_REGISTRY_PATH)
    if any(existing.legacy for existing in existing_accounts):
        _revoke_best_effort(refresh_token)
        raise RegistryError("reconnect migrated accounts before adding another account")
    if any(
        existing.provider_subject == account.provider_subject
        for existing in existing_accounts
    ):
        _revoke_best_effort(refresh_token)
        raise RegistryError(f"Google account is already connected: {account.email}")
    store.save(account.id, refresh_token)
    try:
        add_account(account, DEFAULT_REGISTRY_PATH)
    except Exception:
        try:
            store.delete(account.id)
        except GoogleError:
            pass
        raise
    warnings: list[str] = []
    try:
        install_timer()
    except SchedulerError as error:
        warnings.append(f"background sync could not be enabled: {error}")
    connected_accounts = load_accounts(DEFAULT_REGISTRY_PATH)
    sync_result = _sync_accounts(
        config, connected_accounts, store, known_accounts=connected_accounts
    )
    if not sync_result["ok"]:
        warnings.append("account connected, but the first calendar sync failed")
    return {
        "ok": True,
        "message": f"Connected {account.email}",
        "account": account.public_dict(),
        "warnings": warnings,
        "sync": sync_result,
    }


def _reconnect_account(
    account_id: str, config: GoogleConfig, store: SecretToolStore
) -> dict[str, object]:
    accounts = load_accounts(DEFAULT_REGISTRY_PATH)
    existing = next((account for account in accounts if account.id == account_id), None)
    if existing is None:
        raise RegistryError(f"account is not connected: {account_id}")
    refresh_token, identity = _authorized_identity(config)
    replacement = Account(
        id=existing.id,
        provider_subject=identity["sub"],
        email=identity["email"],
        display_name=identity["name"],
    )
    if not existing.legacy and existing.provider_subject != replacement.provider_subject:
        _revoke_best_effort(refresh_token)
        raise RegistryError(
            f"reconnect {existing.email or existing.display_name} using the same Google account"
        )
    if existing.legacy:
        try:
            purge_account(existing.id)
        except CacheError:
            _revoke_best_effort(refresh_token)
            raise
    try:
        previous_token = store.load(existing.id)
    except GoogleError:
        previous_token = ""
    store.save(existing.id, refresh_token)
    try:
        replace_account(replacement, DEFAULT_REGISTRY_PATH)
    except Exception:
        if previous_token:
            store.save(existing.id, previous_token)
        else:
            try:
                store.delete(existing.id)
            except GoogleError:
                pass
        _revoke_best_effort(refresh_token)
        raise
    connected_accounts = load_accounts(DEFAULT_REGISTRY_PATH)
    result = _sync_accounts(
        config, connected_accounts, store, known_accounts=connected_accounts
    )
    warnings = [] if result["ok"] else [
        "account reconnected, but calendar synchronization failed"
    ]
    return {
        "ok": True,
        "message": f"Reconnected {replacement.email}",
        "account": replacement.public_dict(),
        "warnings": warnings,
        "sync": result,
    }


def _remove_connected_account(
    account_id: str,
    config: GoogleConfig | None,
    store: SecretToolStore,
    *,
    local_only: bool,
) -> dict[str, object]:
    accounts = load_accounts(DEFAULT_REGISTRY_PATH)
    existing = next((account for account in accounts if account.id == account_id), None)
    if existing is None:
        raise RegistryError(f"account is not connected: {account_id}")
    if not local_only:
        revoke_token(store.load(account_id))
    store.delete(account_id)
    purge_account(account_id)
    removed = remove_account(account_id, DEFAULT_REGISTRY_PATH)
    remaining = load_accounts(DEFAULT_REGISTRY_PATH)
    warnings: list[str] = []
    if remaining and config is not None:
        result = _sync_accounts(
            config, remaining, store, known_accounts=remaining
        )
        if not result["ok"]:
            warnings.append("account removed, but remaining accounts did not fully sync")
    elif not remaining:
        result = _sync_accounts(config, (), store, known_accounts=())
        try:
            remove_timer()
        except SchedulerError as error:
            warnings.append(f"background sync could not be disabled: {error}")
    else:
        result = {"ok": False, "errors": []}
        warnings.append(
            "account removed; remaining accounts will sync after OAuth configuration is repaired"
        )
    return {
        "ok": True,
        "message": f"Removed {removed.email or removed.display_name}",
        "localOnly": local_only,
        "warnings": warnings,
        "sync": result,
    }


def _emit(payload: dict[str, object], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        return
    message = payload.get("message")
    if isinstance(message, str) and message:
        print(message)


def _main_locked(args: argparse.Namespace) -> int:
    structured = bool(
        args.json
        or args.status
        or args.doctor
        or args.add_account
        or args.remove_account
        or args.reconnect_account
    )
    try:
        if args.status or args.doctor:
            try:
                config = load_config(args.config)
                _registry_accounts(config)
                config_error = ""
            except ConfigError as error:
                config_error = str(error)
            payload = _status(config_error)
            _emit(payload, json_output=True)
            return 0 if payload["ok"] else 1

        store = SecretToolStore()
        if args.remove_account or args.disconnect:
            try:
                config = load_config(args.config)
                accounts = _registry_accounts(config)
            except ConfigError:
                config = None
                accounts = load_accounts(DEFAULT_REGISTRY_PATH)
        else:
            config = load_config(args.config)
            accounts = _registry_accounts(config)
        if args.add_account:
            assert config is not None
            payload = _connect_account(config, store)
        elif args.reconnect_account:
            assert config is not None
            payload = _reconnect_account(args.reconnect_account, config, store)
        elif args.remove_account:
            payload = _remove_connected_account(
                args.remove_account,
                config,
                store,
                local_only=args.local_only,
            )
        elif args.authorize:
            assert config is not None
            selected = _selected_accounts(accounts, args.account)
            if not selected:
                raise RegistryError("no account is configured for legacy authorization")
            for account in selected:
                refresh_token, _ = authorize(config.client_id, config.client_secret)
                store.save(account.id, refresh_token)
            payload = {"ok": True, "message": "Google authorization completed"}
        elif args.disconnect:
            if not args.account:
                raise RegistryError("--disconnect requires --account")
            payload = _remove_connected_account(
                args.account, config, store, local_only=args.local_only
            )
        else:
            assert config is not None
            if args.account:
                raise RegistryError("--account is only supported with --authorize")
            selected = _selected_accounts(accounts, args.account)
            payload = _sync_accounts(
                config, selected, store, known_accounts=accounts
            )
            payload["message"] = (
                "Calendar sync completed"
                if payload["ok"]
                else "Calendar sync completed with account errors"
            )
        _emit(payload, json_output=structured)
        return 0 if payload.get("ok") else 1
    except (
        CacheError,
        ConfigError,
        GoogleError,
        OperationLockError,
        RegistryError,
        SchedulerError,
    ) as error:
        if structured:
            _emit({"ok": False, "error": str(error)}, json_output=True)
        else:
            print(f"calendar sync failed: {error}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.WARNING)
    try:
        with operation_lock():
            return _main_locked(args)
    except OperationLockError as error:
        structured = bool(
            args.json
            or args.status
            or args.doctor
            or args.add_account
            or args.remove_account
            or args.reconnect_account
        )
        if structured:
            _emit({"ok": False, "error": str(error)}, json_output=True)
        else:
            print(f"calendar sync failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
