"""Render terminal — ANSI style (non-tty & NO_COLOR aman)."""

from __future__ import annotations

import os
import re
import sys


def is_tty() -> bool:
    return sys.stdout.isatty()


def style(text: str, code: str = "36") -> str:
    # NO_COLOR (standar https://no-color.org) atau non-tty → teks polos,
    # jangan bocorkan escape code literal ke output/pipeline.
    if os.environ.get("NO_COLOR") or not is_tty():
        return text
    return f"\x1b[{code}m{text}\x1b[0m"


def stream_print(text: str) -> None:
    """Stream output model ke terminal.

    Di TTY: tulis langsung (stream progres, cursor management).
    Di non-TTY (pipe/CI): tulis langsung juga — model yang mengatur
    format outputnya sendiri (strip_tool_block).
    """
    sys.stdout.write(text)
    sys.stdout.flush()


# Tag-tag markup yang perlu dibersihkan dari output streaming
_TOOLBLOCK_RE = re.compile(r"```tool\n.*?```", re.DOTALL)
_INVOKE_RE = re.compile(r"</?invoke\b[^>]*>", re.IGNORECASE)
_FUNC_RE = re.compile(r"</?function\b[^>]*>", re.IGNORECASE)
_TOOLCALLS_RE = re.compile(r"</?tool_calls\b[^>]*>", re.IGNORECASE)
_ARGKEY_RE = re.compile(r"<arg_key>.*?</arg_key>", re.DOTALL)
_ARGVALUE_OPEN_RE = re.compile(r"<arg" + "value>")
_ARGVALUE_CLOSE_RE = re.compile(r"</arg" + "value>")


def _clean_stream(text: str) -> str:
    """Hapus markup tool-call & whitespace ekstram dari output streaming."""
    text = _TOOLBLOCK_RE.sub("", text)
    text = _INVOKE_RE.sub("", text)
    text = _FUNC_RE.sub("", text)
    text = _TOOLCALLS_RE.sub("", text)
    text = _ARGKEY_RE.sub("", text)
    text = _ARGVALUE_OPEN_RE.sub("", text)
    text = _ARGVALUE_CLOSE_RE.sub("", text)
    return text
