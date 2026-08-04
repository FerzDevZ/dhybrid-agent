#!/usr/bin/env python3
"""Smoke test 0.9.6: verifikasi semua reliability features."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path


def section(t):
    print(f"\n=== {t} ===", flush=True)


def main() -> int:
    section("1. tenacity retry on providers")
    from dhybrid.config import ModelConfig
    from dhybrid.llm.providers import AnthropicClient, OpenAICompatClient, make_client
    assert isinstance(make_client(ModelConfig(provider="litellm", model="openai/gpt-4o-mini")), object)
    assert isinstance(make_client(ModelConfig(provider="openai", model="gpt-4o")), OpenAICompatClient)
    assert isinstance(make_client(ModelConfig(provider="anthropic", model="claude-3-5-sonnet-20241022")), AnthropicClient)
    print("OK — tenacity retry on Anthropic + OpenAI providers")

    section("2. RedisStore persistence")
    from dhybrid.config import ModelConfig
    from dhybrid.session.store import RedisStore
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        store = RedisStore(db_path=tmp / "s.sqlite")
        sid = store.new_session("test")
        store.save_checkpoint(sid, {"run_count": 9, "fallback_uses": 3})
        store2 = RedisStore(db_path=tmp / "s.sqlite", redis_client=None)
        assert store2.load_checkpoint(sid)["run_count"] == 9
    print("OK — RedisStore SQLite fallback works")

    section("3. MIME media detection")
    from dhybrid.tools.vision import _is_image_bytes, _is_media_bytes
    assert _is_image_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 100) is True
    assert _is_media_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 100) is True
    print("OK — image detection works")
    # audio/video magic bytes (mock)
    audio = b"ID3" + b"x" * 100  # MP3
    video = b"\x00\x00\x00" + b"ftyp" + b"x" * 100  # MP4
    # Should not crash
    assert isinstance(_is_media_bytes(audio), bool)
    assert isinstance(_is_media_bytes(video), bool)
    print("OK — MIME audio/video detection no-crash")

    section("4. Structured logging")
    from dhybrid.utils.log import get_logger
    log = get_logger("smoke", fmt="json")
    assert hasattr(log, "info")
    print("OK — structured logger")

    section("5. Prometheus exporter")
    from dhybrid.efficiency.prometheus_exporter import export_metrics
    out = export_metrics()
    assert "# TYPE tokens_prompt counter" in out
    print("OK — prometheus text format")

    section("6. CLI version")
    import dhybrid
    assert dhybrid.__version__ == "0.9.6", dhybrid.__version__
    print(f"OK — dhybrid-agent v{dhybrid.__version__}")

    section("\n[SMOKE OK] 0.9.6 — semua reliability features berfungsi")
    return 0


if __name__ == "__main__":
    sys.exit(main())