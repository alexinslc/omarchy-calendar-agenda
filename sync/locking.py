"""Serialize synchronization and account lifecycle changes across processes."""

from __future__ import annotations

import fcntl
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


DEFAULT_LOCK_PATH = (
    Path.home()
    / ".local"
    / "state"
    / "omarchy"
    / "calendar-agenda"
    / "operations.lock"
)


class OperationLockError(RuntimeError):
    """Raised when the process-wide operation lock cannot be acquired."""


@contextmanager
def operation_lock(path: Path = DEFAULT_LOCK_PATH) -> Iterator[None]:
    lock_path = Path(path)
    descriptor: int | None = None
    try:
        lock_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(lock_path.parent, 0o700)
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        os.fchmod(descriptor, 0o600)
    except OSError as error:
        if descriptor is not None:
            os.close(descriptor)
        raise OperationLockError(f"cannot open calendar operation lock: {error}") from error
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
        except OSError as error:
            raise OperationLockError(
                f"cannot acquire calendar operation lock: {error}"
            ) from error
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)
