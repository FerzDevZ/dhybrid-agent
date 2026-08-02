import os

import pytest

from dhybrid.config import Config
from dhybrid.dotenv import load_dotenv
from dhybrid.llm.registry import ModelRegistry


def test_load_defaults_and_env_override(monkeypatch):
    monkeypatch.setenv("DHYBRID_MODEL", "test-model")
    cfg = Config.load("config/default.yaml")
    assert cfg.model.model == "test-model"
    assert cfg.budget["soft"] == 60000
    assert cfg.workspace.expanduser().name == ".dhybrid"


def test_presets_loaded():
    cfg = Config.load("config/default.yaml")
    assert "anthropic-big" in cfg.presets
    assert "openrouter-fast" in cfg.presets
    assert "ollama" not in str(cfg.presets)  # keputusan: cloud-only


def test_opencode_zen_route_preset():
    """Route opencode zen (https://opencode.ai/zen/v1) harus ter-resolve
    sebagai OpenAI-compatible client dengan base_url yang benar."""
    from dhybrid.llm.providers import OpenAICompatClient, make_client

    cfg = Config.load("config/default.yaml")
    reg = ModelRegistry(cfg)
    zen = reg.resolve("opencode-zen-fast")
    assert zen.model == "deepseek-v4-flash-free"
    assert zen.base_url == "https://opencode.ai/zen/v1"
    client = make_client(zen)
    assert isinstance(client, OpenAICompatClient)
    assert client.base_url == "https://opencode.ai/zen/v1"
    # tanpa key → tidak ada header Authorization (endpoint gratis)
    assert "Authorization" not in client._headers()
    # default config: SATU model saja (tanpa model kecil)
    assert cfg.small_model is None


def test_resolve_preset_and_inline():
    reg = ModelRegistry(Config.load("config/default.yaml"))
    assert reg.resolve("openrouter-fast").model == "deepseek/deepseek-chat"
    assert reg.resolve("anthropic:claude-haiku").provider == "anthropic"
    with pytest.raises(KeyError):
        reg.resolve("nope-preset")


def test_load_dotenv(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("# komentar\nFOO=bar\nBAZ=\"qux\"\n")
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("BAZ", raising=False)
    load_dotenv(tmp_path / ".env")
    assert os.environ["FOO"] == "bar"
    assert os.environ["BAZ"] == "qux"


def test_model_cost():
    from dhybrid.config import ModelConfig

    mc = ModelConfig(cost_per_1k_input=2.0, cost_per_1k_output=10.0)
    assert mc.cost(1000, 500) == pytest.approx(2.0 + 5.0)


def test_set_env_key_appends_and_replaces(tmp_path, monkeypatch):
    from dhybrid.dotenv import set_env_key

    envf = tmp_path / ".env"
    envf.write_text("# komentar\nOPENAI_API_KEY=old\nOTHER=x\n")
    p = set_env_key("OPENAI_API_KEY", "new-key", path=envf)
    assert p == envf
    content = envf.read_text()
    assert "OPENAI_API_KEY=new-key" in content
    assert "OPENAI_API_KEY=old" not in content
    assert "OTHER=x" in content          # baris lain utuh
    assert monkeypatch  # env di-set langsung
    assert os.environ.get("OPENAI_API_KEY") == "new-key"


def test_set_env_key_appends_new(tmp_path):
    from dhybrid.dotenv import set_env_key

    envf = tmp_path / ".env"
    envf.write_text("FOO=1\n")
    set_env_key("BAR_API_KEY", "v", path=envf)
    assert "BAR_API_KEY=v" in envf.read_text()
