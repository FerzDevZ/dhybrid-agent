"""TDD tests for session checkpoint save/load (SQLite persistence of counters)..

> Jalankan: pytest tests/unit/test_session_checkpoint.py -v
"""
from __future__ import annotations

from pathlib import Path

from dhybrid.config import Config, ModelConfig
from dhybrid.session.context import SessionContext
from dhybrid.session.store import SessionStore


def _ctx(tmp_path: Path, sid: str | None = None) -> SessionContext:
    cfg = Config(
        workspace=Path(tmp_path / "ws"),
        model=ModelConfig(provider="openai", model="gpt-4o-mini"),
    )
    store = SessionStore(db_path=tmp_path / "sess.sqlite")
    return SessionContext(
        cfg=cfg,
        store=store,
        cwd=str(tmp_path),
        sid=sid,
    )


def test_checkpoint_roundtrip_counters(tmp_path):
    """Simpan counter (steps, run_count, fallback_uses) → reload → sama."""
    ctx = _ctx(tmp_path)
    ctx.steps = 42
    ctx.run_count = 5
    ctx.fallback_uses = 3
    ctx.save_checkpoint()

    # buat SessionContext baru pakai sid yang sama → load state
    sid = ctx.sid
    ctx2 = _ctx(tmp_path, sid=sid)
    assert ctx2.run_count == 5
    assert ctx2.fallback_uses == 3


def test_checkpoint_skill_candidates(tmp_path):
    """skill_candidates (list[dict]) persisten."""
    ctx = _ctx(tmp_path)
    ctx.skill_candidates = [{"skill": "foo", "confidence": 0.85}]
    ctx.save_checkpoint()

    ctx2 = _ctx(tmp_path, sid=ctx.sid)
    assert len(ctx2.skill_candidates) == 1
    assert ctx2.skill_candidates[0]["skill"] == "foo"


def test_checkpoint_missing_returns_none(tmp_path):
    """load_checkpoint tidak ada return None (bukan crash)."""
    ctx = _ctx(tmp_path)
    state = ctx.store.load_checkpoint(ctx.sid)
    assert state is None
