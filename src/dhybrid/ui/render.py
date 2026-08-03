"""Render terminal — ANSI style (non-tty & NO_COLOR aman)."""

from __future__ import annotations

import os
import sys


def stream_print(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


def is_tty() -> bool:
    return sys.stdout.isatty()


def style(text: str, code: str = "36") -> str:
    # NO_COLOR (standar https://no-color.org) atau non-tty → teks polos,
    # jangan bocorkan escape code literal ke output/pipeline.
    if os.environ.get("NO_COLOR") or not is_tty():
        return text
    return f"\x1b[{code}m{text}\x1b[0m"
