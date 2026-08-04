"""Async file I/O wrapper — aiofiles (fallback sync bila tak tersedia).

Helper ini selundupnya Task 7: skill dump, debug export, semua I/O jadi
non-blocking (async) agar agent loop tidak terganggu I/O disk.
"""
from __future__ import annotations

import asyncio

try:
    import aiofiles  # type: ignore

    _HAS_AIOFILES = True
except ImportError:  # pragma: no cover
    aiofiles = None  # type: ignore
    _HAS_AIOFILES = False


async def async_write_text(path: str, content: str) -> int:
    """Tulis file secara async (aiofiles) — non-blocking."""
    if _HAS_AIOFILES:
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            return await f.write(content)
    # fallback sync di dalam thread pool biar tetap async interface
    return await asyncio.get_event_loop().run_in_executor(
        None, lambda: _sync_write(path, content)
    )


def _sync_write(path: str, content: str) -> int:
    with open(path, "w", encoding="utf-8") as f:
        return f.write(content)


def write_text(path: str, content: str) -> None:
    """Sync wrapper — pakai asyncio.run bila perlu (untuk caller sync seperti repl.py).

    Fallback ke _sync_write langsung bila aiofiles tak tersedia (lebih cepat).
    """
    if _HAS_AIOFILES:
        asyncio.run(async_write_text(path, content))
    else:
        _sync_write(path, content)


async def async_read_text(path: str) -> str:
    if _HAS_AIOFILES:
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            return await f.read()
    return await asyncio.get_event_loop().run_in_executor(None, lambda: _sync_read(path))


def _sync_read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
