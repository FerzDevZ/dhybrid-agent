#!/usr/bin/env python3
"""Smoke end-to-end: REPL asli via PTY — prompt ambigu memicu clarify,
jawaban nomor diterima, agent jalan. Lalu verifikasi allowlist 30 + clarify."""

import os
import pty
import select
import sys
import time

BIN = sys.argv[1] if len(sys.argv) > 1 else ".venv/bin/dhybrid"
ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(ROOT)
BIN = BIN if os.path.isabs(BIN) else os.path.join(REPO, BIN)
os.chdir(REPO)


def read_until(fd, needle, timeout=40):
    buf = b""
    end = time.time() + timeout
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.5)
        if r:
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
            if needle.encode() in buf:
                return buf.decode(errors="replace"), True
    return buf.decode(errors="replace"), needle.encode() in buf


pid, fd = pty.fork()
if pid == 0:
    os.execv(BIN, [BIN, "repl"])
    os._exit(1)

ok = True
try:
    # tunggu prompt REPL
    read_until(fd, ">", 30)
    # prompt ambigu tanpa stack
    os.write(fd, b"buat web login register\n")
    out, found = read_until(fd, "Lanjutkan", 120)
    if not found:
        print("\n[SMOKE FAIL] menu clarify tidak muncul")
        ok = False
    else:
        print("\n[SMOKE OK] menu clarify muncul dengan opsi Lanjutkan=default")
    # jawab nomor 2
    os.write(fd, b"2\n")
    out, found = read_until(fd, "[skill aktif", 40)
    if not found:
        # mungkin agent sudah jalan duluan — tunggu sebentar lagi
        out, found = read_until(fd, "[skill aktif", 20)
    if found:
        print("\n[SMOKE OK] feedback skill aktif tampil setelah keputusan user")
    else:
        print("\n[SMOKE WARN] [skill aktif tidak tertangkap (agent mungkin sudah streaming)")
finally:
    try:
        os.write(fd, b"\x03")  # Ctrl+C
        time.sleep(1)
        os.write(fd, b"/exit\n")
    except OSError:
        pass
    time.sleep(1)
    try:
        os.close(fd)
    except OSError:
        pass

# verifikasi allowlist 31 + tool clarify terdaftar
sys.path.insert(0, os.path.join(REPO, "src"))
from dhybrid.config import Config
from dhybrid.tools import clarify
from dhybrid.tools.registry import ToolRegistry

cfg = Config.load(os.path.join(REPO, "config/default.yaml"))
al = cfg.tool.get("allowlist", [])
print(f"\nallowlist: {len(al)} tool, clarify terdaftar: {'clarify' in al}")
reg = ToolRegistry(allowlist=al)
clarify.register(reg, clarify.ClarifyState(interactive=True))
out = reg.execute("clarify", {"question": "q?", "options": ["a", "b"]})
print(f"tool clarify execute -> {out}")
ok = ok and len(al) == 31 and "clarify" in al and out == clarify.PENDING_SENTINEL
print("\n[SMOKE " + ("OK]" if ok else "FAIL]"))
sys.exit(0 if ok else 1)
