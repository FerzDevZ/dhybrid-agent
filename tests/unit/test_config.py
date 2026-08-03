import os

import pytest

from dhybrid.config import Config
from dhybrid.dotenv import load_dotenv
from dhybrid.llm.registry import ModelRegistry


@pytest.fixture(autouse=True)
def _all_providers_enabled(tmp_path, monkeypatch):
    """Isolasi dari setting user nyata (~/.dhybrid/provider_enable.json):
    paksa semua provider enabled supaya resolve/names deterministik."""
    import dhybrid.ui.commands as cmds

    monkeypatch.setattr(cmds, "PROVIDER_ENABLE_FILE", tmp_path / "provider_enable.json")


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


def test_names_returns_preset_names_not_provider_names():
    """Regresi: loop dalam `for ..., env in PROVIDERS` dulu menimpa variabel
    `name` sehingga names() mengembalikan nama provider ("Anthropic", dst)
    → resolve() crash KeyError saat /settings. Harus nama preset murni."""
    reg = ModelRegistry(Config.load("config/default.yaml"))
    names = reg.names()
    # semua nama harus bisa di-resolve tanpa exception (bukan nama provider)
    for n in names:
        assert reg.resolve(n).model, f"preset {n!r} gagal resolve"
    # pastikan TIDAK ada label provider yang bocor sebagai preset
    from dhybrid.ui.commands import PROVIDERS
    provider_labels = {p[0].split()[0] for p in PROVIDERS}
    assert not (set(names) & provider_labels), f"nama provider bocor: {names}"
    # preset gemini yang dikenal harus ada
    assert "gemini-fast" in names
    assert "gemini-big" in names


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
