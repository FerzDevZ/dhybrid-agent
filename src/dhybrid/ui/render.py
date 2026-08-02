"""Render terminal — streaming & ANSI style (non-tty aman)."""

from __future__ import annotations

import sys


def stream_print(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


def is_tty() -> bool:
    return sys.stdout.isatty()


def style(text: str, code: str = "36") -> str:
    return f"\x1b[{code}m{text}\x1b[0m" if is_tty() else text
