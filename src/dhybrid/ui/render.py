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

    Di TTY: buffer baris-belum-lengkap (untuk pewarnaan) & flush per baris.
    Di non-TTY (pipe/CI): buffer per-baris — cegah output pecah karakter
    demi karakter (misal 'H\\nai!\\n👋...' jadi 'Hai! 👋...').
    """

    def __init__(self) -> None:
        self._buf = ""
        self._in_tty = False
        self._pending = ""  # TTY: bagian baris yang belum berakhiran newline

    def __call__(self, text: str) -> None:
        # Deteksi mode TTY di setiap call (bisa berubah di runtime)
        is_tty_now = is_tty() and not os.environ.get("NO_COLOR")

        if is_tty_now:
            # TTY mode: warna baris lengkap + tulis langsung (streaming halus)
            if not self._in_tty:
                # Pertama kali switch ke TTY — flush buffer lama
                if self._buf:
                    sys.stdout.write(self._buf + "\n")
                    sys.stdout.flush()
                    self._buf = ""
                self._in_tty = True

            tail_nl = text.endswith("\n")
            lines = (self._pending + text).split("\n")
            self._pending = lines.pop()  # bagian tak lengkap ditahan utk pewarnaan
            if lines:
                sys.stdout.write(_colorize_lines("\n".join(lines)))
                if tail_nl:
                    sys.stdout.write("\n")
                sys.stdout.flush()
            # baris sangat panjang tanpa newline (mis. kode satu-baris) → emit
            # apa adanya agar layar tidak terasa membeku; warna dilewati.
            if len(self._pending) > 512:
                sys.stdout.write(self._pending)
                sys.stdout.flush()
                self._pending = ""
            return

        # Non-TTY mode (pipe/CI): buffer hingga ada newline
        if self._in_tty:
            # Switch dari TTY ke non-TTY — flush buffer
            if self._buf:
                sys.stdout.write(self._buf + "\n")
                sys.stdout.flush()
                self._buf = ""
            if self._pending:
                sys.stdout.write(self._pending)
                sys.stdout.flush()
                self._pending = ""
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
        if self._pending:
            sys.stdout.write(_colorize_lines(self._pending) + "\n")
            sys.stdout.flush()
            self._pending = ""


# Singleton instance — state buffer persisten tiap delta
_streamer = _BufferedStreamPrint()


def stream_print(text: str) -> None:
    """Stream output model ke terminal.

    Di TTY: tulis per-baris (lengkap) + warna error/peringatan.
    Di non-TTY (pipe/CI): buffer per-baris agar output tidak pecah
    karakter demi karakter.
    """
    _streamer(text)


def _colorize_lines(text: str) -> str:
    """Warna baris error/peringatan saat stream (hanya dipanggil saat TTY)."""
    if not text:
        return text
    return "\n".join(_colorize_line(l) for l in text.split("\n"))


def _colorize_line(line: str) -> str:
    if not line:
        return line
    if line.startswith(("ERROR", "[ERROR", "Traceback (most recent", "  File \"", "!pip install", "Error:")):
        return style(line, "31")
    if line.startswith(("[exit ", "[stderr]", "[timeout", "[job #", "WARNING:", "warning:")):
        return style(line, "33")
    return line


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
