"""Manage the plugin-owned systemd user timer without invoking a shell."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Callable


UNIT_NAMES = (
    "omarchy-calendar-agenda-sync.service",
    "omarchy-calendar-agenda-sync.timer",
)
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = PLUGIN_ROOT / "systemd"
DEFAULT_UNIT_DIRECTORY = Path.home() / ".config" / "systemd" / "user"


class SchedulerError(RuntimeError):
    """Raised when the systemd user timer cannot be managed."""


def _run(
    args: list[str],
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    try:
        result = runner(args, text=True, capture_output=True, check=False)
    except (FileNotFoundError, OSError) as error:
        raise SchedulerError(f"cannot run systemctl: {error}") from error
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "unknown systemctl error").strip()
        raise SchedulerError(detail)


def install_timer(
    unit_directory: Path = DEFAULT_UNIT_DIRECTORY,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    unit_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    for name in UNIT_NAMES:
        source = SOURCE_DIRECTORY / name
        destination = unit_directory / name
        content = source.read_bytes()
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=unit_directory,
                prefix=f".{name}.",
                suffix=".tmp",
                mode="wb",
                delete=False,
            ) as temporary:
                temporary_name = temporary.name
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.chmod(temporary_name, 0o600)
            os.replace(temporary_name, destination)
        finally:
            if temporary_name is not None:
                try:
                    os.unlink(temporary_name)
                except FileNotFoundError:
                    pass
    directory_fd = os.open(
        unit_directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    )
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    _run(["systemctl", "--user", "daemon-reload"], runner)
    _run(
        [
            "systemctl",
            "--user",
            "enable",
            "--now",
            "omarchy-calendar-agenda-sync.timer",
        ],
        runner,
    )


def remove_timer(
    unit_directory: Path = DEFAULT_UNIT_DIRECTORY,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    _run(
        [
            "systemctl",
            "--user",
            "disable",
            "--now",
            "omarchy-calendar-agenda-sync.timer",
        ],
        runner,
    )
    for name in UNIT_NAMES:
        try:
            (unit_directory / name).unlink()
        except FileNotFoundError:
            pass
    directory_fd = os.open(
        unit_directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    )
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    _run(["systemctl", "--user", "daemon-reload"], runner)
