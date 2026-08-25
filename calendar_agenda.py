#!/usr/bin/env python3
"""Stable executable entry point used by QML and the systemd user service."""

from sync.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
