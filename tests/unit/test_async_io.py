"""TDD tests for async I/O helper (aiofiles-based atau sync fallback).."""
import asyncio

from dhybrid.utils.async_io import async_write_text, write_text


def test_async_write_text_creates_file(tmp_path):
    f = tmp_path / "async_out.txt"
    asyncio.run(async_write_text(str(f), "hello async"))
    assert f.read_text() == "hello async"


def test_write_text_sync_wrapper(tmp_path):
    f = tmp_path / "sync_out.txt"
    write_text(str(f), "hello sync")
    assert f.read_text() == "hello sync"


def test_concurrent_writes_no_race(tmp_path):
    files = [tmp_path / f"f{i}.txt" for i in range(5)]

    async def _run():
        await asyncio.gather(
            *[async_write_text(str(f), f"content-{i}") for i, f in enumerate(files)]
        )

    asyncio.run(_run())
    for i, f in enumerate(files):
        assert f.read_text() == f"content-{i}"
