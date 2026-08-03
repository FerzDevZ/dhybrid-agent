"""Test pengaturan: input model manual, /settings, set small model."""

import pytest

from dhybrid.config import Config
from dhybrid.session.context import SessionContext
from dhybrid.session.store import SessionStore


@pytest.fixture(autouse=True)
def _all_providers_enabled(tmp_path, monkeypatch):
    """Isolasi dari setting user nyata (~/.dhybrid/provider_enable.json)."""
    import dhybrid.ui.commands as cmds

    monkeypatch.setattr(cmds, "PROVIDER_ENABLE_FILE", tmp_path / "provider_enable.json")


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    import dhybrid.session.userconfig as uc

    monkeypatch.setattr(uc, "user_config_path", lambda: tmp_path / "config.yaml")
    cfg = Config.load("config/default.yaml")
    cfg.workspace = tmp_path
    return SessionContext(cfg, SessionStore(tmp_path / "s.sqlite"), cwd=str(tmp_path))


def test_resolve_model_input_preset(ctx):
    mc = ctx.resolve_model_input("openai-fast")
    assert mc.model == "gpt-4o-mini"
    assert mc.provider == "openai"


def test_resolve_model_input_provider_colon(ctx):
    mc = ctx.resolve_model_input("anthropic:claude-opus-5")
    assert mc.provider == "anthropic"
    assert mc.model == "claude-opus-5"


def test_resolve_model_input_manual_uses_active_route(ctx):
    """Model manual memakai route/provider yang sedang aktif (zen)."""
    ctx.set_model("opencode-zen-fast")
    mc = ctx.resolve_model_input("gpt-5.6-luna")
    assert mc.model == "gpt-5.6-luna"
    assert mc.base_url == "https://opencode.ai/zen/v1"
    assert mc.provider == "openai"


def test_set_model_manual_and_label(ctx):
    out = ctx.set_model("gpt-5.6-luna")
    assert "gpt-5.6-luna" in out
    assert ctx.model_cfg.model == "gpt-5.6-luna"


def test_set_small_model_off(ctx):
    out = ctx.set_small_model("-")
    assert "nonaktif" in out
    assert ctx.small_model_name is None
    assert ctx.router is None


def test_set_small_model_preset(ctx):
    out = ctx.set_small_model("opencode-zen-fast")
    assert "opencode-zen-fast" in out
    assert ctx.router is not None


def test_default_single_model_no_router(ctx):
    """Default config: SATU model, tanpa router/model kecil — semua tugas
    memakai model utama."""
    assert ctx.small_model_name is None
    assert ctx.router is None


def test_set_model_persists(ctx, tmp_path):
    import dhybrid.session.userconfig as uc

    ctx.set_model("opencode-zen-big")
    data = uc.load_user_config()
    assert data["model"]["model"] == "claude-sonnet-5"
    assert (tmp_path / "config.yaml").exists()
