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


class _BufferedStreamPrint:
    """Buffer delta kecil di non-TTY mode & hanya emit baris penuh.

    Di TTY: buffer ringan (flush per 50ms atau newline) agar output rapi.
    Di non-TTY (pipe/CI): buffer per-baris — cegah output pecah karakter
    demi karakter (misal 'H\\nai!\\n👋...' jadi 'Hai! 👋...').
    """

    def __init__(self) -> None:
        self._buf = ""
        self._in_tty = False

    def __call__(self, text: str) -> None:
        # Deteksi mode TTY di setiap call (bisa berubah di runtime)
        is_tty_now = is_tty() and not os.environ.get("NO_COLOR")

        if is_tty_now:
            # TTY mode: write langsung untuk streaming real-time
            if not self._in_tty:
                # Pertama kali switch ke TTY — flush buffer lama
                if self._buf:
                    sys.stdout.write(self._buf + "\n")
                    sys.stdout.flush()
                    self._buf = ""
                self._in_tty = True

            # Di TTY, write langsung tanpa buffer untuk streaming halus
            sys.stdout.write(text)
            sys.stdout.flush()
            return

        # Non-TTY mode (pipe/CI): buffer hingga ada newline
        if self._in_tty:
            # Switch dari TTY ke non-TTY — flush buffer
            if self._buf:
                sys.stdout.write(self._buf + "\n")
                sys.stdout.flush()
                self._buf = ""
            self._in_tty = False

        # non-TTY: buffer hingga ada newline
        self._buf += text
        lines = self._buf.split("\n")
        # simpan sisa yang belum lengkap di buffer
        self._buf = lines[-1]
        for line in lines[:-1]:
            sys.stdout.write(line + "\n")
        sys.stdout.flush()

    def flush(self) -> None:
        if self._buf:
            sys.stdout.write(self._buf)
            sys.stdout.flush()
            self._buf = ""


# Singleton instance — state buffer persisten tiap delta
_streamer = _BufferedStreamPrint()


def stream_print(text: str) -> None:
    """Stream output model ke terminal.

    Di TTY: tulis langsung (stream progres, cursor management).
    Di non-TTY (pipe/CI): buffer per-baris agar output tidak pecah
    karakter demi karakter.
    """
    _streamer(text)


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


def flush_stream() -> None:
    """Flush buffer sisa di non-TTY mode — panggil sebelum DONE/render akhir."""
    _streamer.flush()
