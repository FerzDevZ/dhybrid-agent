"""Test Task 5 (inject memori jangka panjang ke konteks awal) & Task 6 (auto-resume sesi)."""

from pathlib import Path

import pytest

from dhybrid.config import Config
from dhybrid.session.memory import MemoryStore
from dhybrid.session.store import SessionStore


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    import dhybrid.session.userconfig as uc

    # isolasi — jangan sentuh config user sungguhan
    monkeypatch.setattr(uc, "user_config_path", lambda: tmp_path / "userconfig.yaml")
    c = Config.load("config/default.yaml")
    c.workspace = tmp_path
    return c


def _memory_path(workspace, cwd) -> Path:
    import hashlib

    h = hashlib.sha256(Path(cwd).resolve().as_posix().encode()).hexdigest()[:12]
    return Path(workspace) / "projects" / h / "memory.sqlite"


# ---- Task 5: fakta memori jangka panjang di-inject ke system prompt ----


def test_memory_facts_injected_into_system_prompt(tmp_path, cfg):
    from dhybrid.session.context import SessionContext

    cwd = str(tmp_path / "proj")
    (tmp_path / "proj").mkdir(exist_ok=True)

    # isi memori proyek SEBELUM sesi dibuat (sama seperti sepanjang proyek dipakai)
    mem = MemoryStore(_memory_path(cfg.workspace, cwd))
    mem.remember("stack", "php 8 + composer + node tersedia")
    mem.remember("deploy", "pakai Koyeb via git push")

    ctx = SessionContext(cfg, SessionStore(tmp_path / "s.sqlite"), cwd=cwd, resume=False)

    assert "php 8 + composer + node tersedia" in ctx.system_prompt
    assert "pakai Koyeb via git push".lower() in ctx.system_prompt.lower()
    # penanda bahwa ini memori proyek (bukan sekedar prompt bawaan)
    assert "punya catatan" in ctx.system_prompt


def test_no_memory_no_extra_block(tmp_path, cfg):
    from dhybrid.session.context import SessionContext

    ctx = SessionContext(cfg, SessionStore(tmp_path / "s.sqlite"), cwd=str(tmp_path))
    assert "[JANGAN DICARI ULANG]" not in ctx.system_prompt


# ---- Task 6: repl auto-resume sesi terakhir di proyek yang sama ----


def test_auto_resume_loads_last_session_for_cwd(tmp_path, cfg):
    from dhybrid.session.context import SessionContext

    store = SessionStore(tmp_path / "s.sqlite")
    cwd = str(tmp_path / "proj")
    (tmp_path / "proj").mkdir(exist_ok=True)

    # sesi pertama (tanpa resume) → sid "a"
    ctx1 = SessionContext(cfg, store, cwd=cwd, resume=False)
    assert ctx1.resumed_id is None
    store.append_message(ctx1.sid, "user", "bagaimana struktur repo ini?")
    store.append_message(ctx1.sid, "assistant", "daftar file: src/dhybrid/…")
    store.set_summary(ctx1.sid, "repo dhybrid-agent, package Python CLI", "")

    # sesi berikutnya (repl default = resume) → lanjutkan sid yang sama
    ctx2 = SessionContext(cfg, store, cwd=cwd, resume=True)
    assert ctx2.sid == ctx1.sid
    assert ctx2.resumed_id == ctx1.sid
    assert ctx2.ctx.summary == "repo dhybrid-agent, package Python CLI"
    contents = [m.content for m in ctx2.ctx.messages]
    assert any("bagaimana struktur repo ini?" in (c or "") for c in contents)


def test_fresh_resume_false_starts_new_session(tmp_path, cfg):
    from dhybrid.session.context import SessionContext

    store = SessionStore(tmp_path / "s.sqlite")
    cwd = str(tmp_path / "proj")
    (tmp_path / "proj").mkdir(exist_ok=True)

    ctx1 = SessionContext(cfg, store, cwd=cwd, resume=False)
    (tmp_path / "lain").mkdir(exist_ok=True)
    # sesi berbeda cwd → auto-resume tidak boleh nyabet sesi proyek lain
    other = SessionContext(cfg, store, cwd=str(tmp_path / "lain"), resume=False)
    store.append_message(other.sid, "user", "konteks proyek lain")

    ctx2 = SessionContext(cfg, store, cwd=str(tmp_path / "lain"), resume=True)
    assert ctx2.resumed_id == other.sid      # resume proyek-nya sendiri
    assert ctx2.sid != ctx1.sid


def test_explicit_sid_reuses_session_without_orphan(tmp_path, cfg):
    """Fix cmd_resume: bila sid diteruskan eksplisit, SessionContext TIDAK boleh
    membuat sesi baru (sebelumnya ada baris sesi 'yatim' terbuang tiap resume)."""
    from dhybrid.session.context import SessionContext

    store = SessionStore(tmp_path / "s.sqlite")
    sid = store.new_session(cwd="/x")
    before = len(store.sessions(limit=1000))
    ctx = SessionContext(cfg, store, cwd="/x", sid=sid)
    assert ctx.sid == sid
    assert ctx.resumed_id is None
    assert len(store.sessions(limit=1000)) == before  # tidak ada orphan