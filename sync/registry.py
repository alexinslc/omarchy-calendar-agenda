"""Private, atomic registry for connected calendar accounts."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterable


REGISTRY_SCHEMA_VERSION = 1
DEFAULT_REGISTRY_PATH = (
    Path.home()
    / ".local"
    / "state"
    / "omarchy"
    / "calendar-agenda"
    / "accounts.json"
)


class RegistryError(ValueError):
    """Raised when the local account registry cannot be read or updated."""


@dataclass(frozen=True)
class Account:
    id: str
    provider_subject: str
    email: str
    display_name: str
    legacy: bool = False

    def public_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "email": self.email,
            "displayName": self.display_name,
            "legacy": self.legacy,
        }


def _validate_string(value: Any, name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        qualifier = "a string" if allow_empty else "a non-empty string"
        raise RegistryError(f"{name} must be {qualifier}")
    return value


def _decode_account(value: Any) -> Account:
    if not isinstance(value, dict):
        raise RegistryError("account registry entries must be objects")
    unknown = set(value) - {
        "id",
        "providerSubject",
        "email",
        "displayName",
        "legacy",
    }
    if unknown:
        raise RegistryError(
            "unsupported account registry key(s): " + ", ".join(sorted(unknown))
        )
    legacy = value.get("legacy", False)
    if not isinstance(legacy, bool):
        raise RegistryError("account legacy marker must be boolean")
    return Account(
        id=_validate_string(value.get("id"), "account id"),
        provider_subject=_validate_string(
            value.get("providerSubject"), "account providerSubject"
        ),
        email=_validate_string(value.get("email", ""), "account email", allow_empty=True),
        display_name=_validate_string(
            value.get("displayName", ""), "account displayName", allow_empty=True
        ),
        legacy=legacy,
    )


def load_accounts(path: Path = DEFAULT_REGISTRY_PATH) -> tuple[Account, ...]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ()
    except json.JSONDecodeError as error:
        raise RegistryError(f"account registry is not valid JSON: {path}") from error
    except OSError as error:
        raise RegistryError(f"cannot read account registry: {path}") from error
    if not isinstance(raw, dict):
        raise RegistryError("account registry must be an object")
    if set(raw) != {"schemaVersion", "accounts"}:
        raise RegistryError("account registry has unsupported or missing keys")
    if raw["schemaVersion"] != REGISTRY_SCHEMA_VERSION:
        raise RegistryError("account registry schema is unsupported")
    values = raw["accounts"]
    if not isinstance(values, list):
        raise RegistryError("account registry accounts must be a list")
    accounts = tuple(_decode_account(value) for value in values)
    ids = [account.id for account in accounts]
    subjects = [account.provider_subject for account in accounts]
    if len(ids) != len(set(ids)):
        raise RegistryError("account registry contains duplicate account IDs")
    if len(subjects) != len(set(subjects)):
        raise RegistryError("account registry contains duplicate Google accounts")
    return accounts


def _payload(accounts: Iterable[Account]) -> bytes:
    values = []
    for account in accounts:
        encoded = asdict(account)
        values.append(
            {
                "id": encoded["id"],
                "providerSubject": encoded["provider_subject"],
                "email": encoded["email"],
                "displayName": encoded["display_name"],
                "legacy": encoded["legacy"],
            }
        )
    return (json.dumps(
        {"schemaVersion": REGISTRY_SCHEMA_VERSION, "accounts": values},
        ensure_ascii=False,
        indent=2,
    ) + "\n").encode("utf-8")


def save_accounts(
    accounts: Iterable[Account], path: Path = DEFAULT_REGISTRY_PATH
) -> None:
    destination = Path(path)
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(destination.parent, 0o700)
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
            temporary.write(_payload(accounts))
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


def new_account(provider_subject: str, email: str, display_name: str) -> Account:
    return Account(
        id=uuid.uuid4().hex,
        provider_subject=provider_subject,
        email=email,
        display_name=display_name or email,
    )


def migrate_legacy_accounts(
    account_ids: Iterable[str], path: Path = DEFAULT_REGISTRY_PATH
) -> tuple[Account, ...]:
    accounts = list(load_accounts(path))
    known_ids = {account.id for account in accounts}
    changed = False
    for account_id in account_ids:
        if account_id in known_ids:
            continue
        accounts.append(
            Account(
                id=account_id,
                provider_subject=f"legacy:{account_id}",
                email="",
                display_name=account_id,
                legacy=True,
            )
        )
        known_ids.add(account_id)
        changed = True
    if changed:
        save_accounts(accounts, path)
    return tuple(accounts)


def add_account(account: Account, path: Path = DEFAULT_REGISTRY_PATH) -> None:
    accounts = list(load_accounts(path))
    if any(existing.provider_subject == account.provider_subject for existing in accounts):
        raise RegistryError("that Google account is already connected")
    if any(existing.id == account.id for existing in accounts):
        raise RegistryError("generated account ID is already in use")
    accounts.append(account)
    save_accounts(accounts, path)


def replace_account(account: Account, path: Path = DEFAULT_REGISTRY_PATH) -> None:
    accounts = list(load_accounts(path))
    if any(
        existing.id != account.id
        and existing.provider_subject == account.provider_subject
        for existing in accounts
    ):
        raise RegistryError("that Google account is already connected")
    for index, existing in enumerate(accounts):
        if existing.id == account.id:
            accounts[index] = replace(account, legacy=False)
            save_accounts(accounts, path)
            return
    raise RegistryError(f"account is not connected: {account.id}")


def remove_account(account_id: str, path: Path = DEFAULT_REGISTRY_PATH) -> Account:
    accounts = list(load_accounts(path))
    for index, account in enumerate(accounts):
        if account.id == account_id:
            del accounts[index]
            save_accounts(accounts, path)
            return account
    raise RegistryError(f"account is not connected: {account_id}")
