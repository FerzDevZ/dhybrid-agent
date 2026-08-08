"""Streaming filter — sembunyikan blok panggilan tool dari tampilan user.

Model mode-teks menulis panggilan tool sebagai blok:
- ```tool {JSON} ```          (format dhybrid)
- <invoke name="x">...</invoke>  (format gaya Claude Code)
- <tool_calls>...</tool_calls>    (pembungkus Anthropic)

Blok itu TIDAK boleh tampil mentah di layar; teks lain tetap ter-stream live.
PENTING: delta LLM datang dalam potongan kecil (bisa '```' lalu 'tool' terpisah)
→ buffer harus menahan ekor yang berpotensi jadi awal marker.
"""

from __future__ import annotations

from collections.abc import Callable

# (start_marker, end_marker)
BLOCK_PAIRS: list[tuple[str, str]] = [
    ("<tool_calls>", "</tool_calls>"),
    ("<tool_call>", "</tool_call>"),
    ("```tool", "```"),
    ("<invoke name=", "</invoke>"),
    ('{"name": "', "\n"),  # JSON telanjang satu-baris: {"name": "x", ...}
]

# panjang marker awal terpanjang; simpan KEEP karakter terakhir buffer
_KEEP = max(len(s) for s, _ in BLOCK_PAIRS) - 1

# Flush threshold: hanya flush saat buffer cukup besar ATAU ada newline
# Mencegah flush per-karakter yang bikin output berhamburan
_FLUSH_THRESHOLD = 256


class ToolBlockFilter:
    def __init__(self, emit: Callable[[str], None]):
        self._emit = emit
        self._buf = ""
        self._end: str | None = None  # end-marker saat berada di dalam blok

    def _out(self, text: str) -> None:
        self._emit(text)

    def feed(self, chunk: str) -> None:
        self._buf += chunk
        while True:
            if self._end is None:
                best: tuple[int, str, str] | None = None
                for start, end in BLOCK_PAIRS:
                    idx = self._buf.find(start)
                    if idx != -1 and (best is None or idx < best[0]):
                        best = (idx, start, end)
                if best is None:
                    # Tidak ada marker: flush hanya jika buffer besar ATAU mengandung newline
                    # Cari newline di bagian yang bisa di-flush (kecuali _KEEP ekor)
                    flushable_len = max(0, len(self._buf) - _KEEP)
                    if flushable_len == 0:
                        return  # buffer masih kecil, tunggu lagi
                    
                    # Cek apakah ada newline di bagian yang bisa di-flush
                    flushable_part = self._buf[:flushable_len]
                    nl_idx = flushable_part.rfind("\n")
                    if nl_idx != -1:
                        # Ada newline: flush hingga newline (inklusif)
                        self._out(self._buf[:nl_idx + 1])
                        self._buf = self._buf[nl_idx + 1:]
                        continue  # loop lagi, mungkin masih ada newline lain
                    
                    # Tidak ada newline: flush hanya jika buffer melebihi threshold
                    if flushable_len >= _FLUSH_THRESHOLD:
                        self._out(self._buf[:flushable_len])
                        self._buf = self._buf[flushable_len:]
                        return
                    return  # buffer belum cukup, tunggu lebih banyak data
                
                idx, start, end = best
                if idx:
                    # Flush teks sebelum marker (bisa mengandung newline)
                    self._out(self._buf[:idx])
                self._buf = self._buf[idx + len(start):]
                self._end = end
            else:
                idx = self._buf.find(self._end)
                if idx == -1:
                    return  # tunggu penutup (buffer ditahan penuh)
                self._buf = self._buf[idx + len(self._end):]
                self._end = None
                self._out("\n")

    def flush(self) -> None:
        if self._end is None and self._buf:
            self._out(self._buf)
        self._buf = ""
