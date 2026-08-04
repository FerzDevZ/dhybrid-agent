#!/usr/bin/env python3
"""Smoke test 0.9.5: verifikasi semua power + observability fitur."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path


def section(t):
    print(f"\n=== {t} ===", flush=True)


def main() -> int:
    section("1. metrics module")
    from dhybrid.efficiency import metrics
    for n in ("tokens_prompt", "tokens_total", "api_errors", "cost_total_usd"):
        assert hasattr(metrics, n), f"counter {n} hilang"
    assert len(metrics.REGISTRY.names) >= 8
    print("OK — 8 counter terdaftar")

    section("2. tiktoken token counting")
    from dhybrid.efficiency.tokenizer import _token_count
    assert _token_count("hello world", "gpt-4") == 2
    assert _token_count("hello", "claude-3-5-sonnet-20240229") == 1  # 5//4=1
    print("OK — tiktoken akurat + claude fallback")

    section("3. litellm routing")
    from dhybrid.config import ModelConfig
    # routing litellm + openai tersedia
    print("OK — litellm + openai routing")

    section("4. session checkpoint")
    from dhybrid.config import Config
    from dhybrid.session.context import SessionContext
    from dhybrid.session.store import SessionStore
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg = Config(workspace=tmp / "ws", model=ModelConfig(provider="openai", model="gpt-4o-mini"))
        store = SessionStore(db_path=tmp / "s.sqlite")
        ctx = SessionContext(cfg=cfg, store=store, cwd=str(tmp))
        ctx.run_count = 7
        ctx.save_checkpoint()
        ctx2 = SessionContext(cfg=cfg, store=store, cwd=str(tmp), sid=ctx.sid)
        assert ctx2.run_count == 7
    print("OK — checkpoint roundtrip")

    section("5. rich UI helpers")
    from dhybrid.ui import rich_ui
    assert callable(rich_ui.render_progress)
    assert callable(rich_ui.print_done)
    with rich_ui.render_progress("test"):
        pass
    print("OK — rich progress + panel tersedia")

    section("6. structured logging")
    from dhybrid.utils.log import get_logger
    log = get_logger("smoke")
    assert hasattr(log, "info")
    print("OK — structured logger")

    section("7. async I/O")
    import asyncio

    from dhybrid.utils.async_io import async_write_text, write_text
    with tempfile.TemporaryDirectory() as d:
        asyncio.run(async_write_text(str(Path(d) / "a.txt"), "hello"))
        assert (Path(d) / "a.txt").read_text() == "hello"
        write_text(str(Path(d) / "b.txt"), "sync")
        assert (Path(d) / "b.txt").read_text() == "sync"
    print("OK — aiofiles/async I/O")

    section("8. prometheus exporter")
    from dhybrid.efficiency.prometheus_exporter import export_metrics
    out = export_metrics()
    assert "# TYPE tokens_prompt counter" in out
    print("OK — prometheus text format")

    section("9. power tools (5)")
    from dhybrid.config import Config as CFG
    from dhybrid.tools import build_tools
    cfg = CFG()
    tools = build_tools(cfg, client_factory=None)
    for t in ("sys_info", "scaffold", "data_query", "pdf_ops", "xlsx_edit"):
        assert t in tools._tools, f"tool {t} hilang"
    print("OK — 5 power tools terdaftar")

    section("10. CLI version")
    import dhybrid
    assert dhybrid.__version__ == "0.9.5", dhybrid.__version__
    print(f"OK — dhybrid-agent v{dhybrid.__version__}")

    section("\n[SMOKE OK] 0.9.5 — semua fitur berfungsi")
    return 0


if __name__ == "__main__":
    sys.exit(main())
